/**
 * Periodically fetches new tasks from the Flamenco Server, and sends updates back.
 */
package flamenco

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
	"sync"
	"time"

	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

// Max. nr of tasks that's allowed to be buffered in the channel.
const MAX_OUTSTANDING_TASKS = 5

// Gives the system some time to start up (and open listening HTTP port)
const STARTUP_NOTIFICATION_INITIAL_DELAY = 500 * time.Millisecond

// Duration between consecutive retries of sending the startup notification.
const STARTUP_NOTIFICATION_RETRY = 30 * time.Second

type SetTaskStatusPatch struct {
	Op     string `json:"op"`
	Status string `json:"status"`
}

type UpstreamConnection struct {
	// Send a *Task here to upload its status to upstream Flamenco Server.
	UploadChannel chan *Task

	config  *Conf
	session *mgo.Session

	// Send any boolean here to kick the task downloader into downloading new tasks.
	download_kick chan chan bool

	done    chan bool
	done_wg *sync.WaitGroup
}

func ConnectUpstream(config *Conf, session *mgo.Session) *UpstreamConnection {
	upload_chan := make(chan *Task, MAX_OUTSTANDING_TASKS)

	// For uploading task statuses.
	go func() {
		for task := range upload_chan {
			upload_task_status(config, task)
		}
	}()

	upconn := UpstreamConnection{
		upload_chan,
		config,
		session,
		make(chan chan bool),
		make(chan bool),
		new(sync.WaitGroup),
	}
	upconn.download_task_loop()

	return &upconn
}

/**
 * Closes the upstream connection by stopping all upload/download loops.
 */
func (self *UpstreamConnection) Close() {
	close(self.done)

	// Dirty hack: sleep for a bit to ensure the closing of the 'done'
	// channel can be handled by other goroutines, before handling the
	// closing of the other channels.
	time.Sleep(1)
	close(self.UploadChannel)
	close(self.download_kick)

	log.Println("UpstreamConnection: shutting down, waiting for shutdown to complete.")
	self.done_wg.Wait()
	log.Println("UpstreamConnection: shutdown complete.")
}

func (self *UpstreamConnection) KickDownloader(synchronous bool) {
	if synchronous {
		pingback := make(chan bool)
		self.download_kick <- pingback
		log.Println("KickDownloader: Waiting for task downloader to finish.")

		// wait for the download to be complete, or the connection to be shut down.
		self.done_wg.Add(1)
		defer self.done_wg.Done()

		for {
			switch {
			case <-pingback:
				log.Println("KickDownloader: done.")
				return
			case <-self.done:
				log.Println("KickDownloader: Aborting waiting for task downloader; shutting down.")
				return
			}
		}
	} else {
		log.Println("KickDownloader: asynchronous kick, just kicking.")
		self.download_kick <- nil
	}
}

func upload_task_status(config *Conf, task *Task) {
	// TODO: when uploading a task status change fails, remember this somewhere and
	// keep retrying until it succeeds.
	rel_url, err := url.Parse(fmt.Sprintf("api/flamenco/tasks/%s", task.Id.Hex()))
	if err != nil {
		log.Printf("ERROR: Unable to construct Flamenco URL for task %s: %s\n",
			task.Id.Hex(), err)
		return
	}

	err = SendPatch(config, rel_url, SetTaskStatusPatch{
		Op:     "set-task-status",
		Status: task.Status,
	})
	if err != nil {
		log.Printf("ERROR: Error PATCHting task %s: %s\n", task.Id.Hex(), err)
		return
	}

	log.Printf("Done sending task %s to upstream Flamenco\n", task.Id)
}

func (self *UpstreamConnection) download_task_loop() {
	timer_chan := Timer("download_task_loop",
		self.config.DownloadTaskSleep,
		self.done,
		self.done_wg,
	)

	go func() {
		mongo_sess := self.session.Copy()
		defer mongo_sess.Close()

		self.done_wg.Add(1)
		defer self.done_wg.Done()

		for {
			select {
			case <-self.done:
				log.Println("download_task_loop: Task download goroutine shutting down.")
				return
			case <-timer_chan:
				log.Println("download_task_loop: Going to fetch tasks due to periodic timeout.")
				download_tasks_from_upstream(self.config, mongo_sess)
			case pingback_chan := <-self.download_kick:
				log.Println("download_task_loop: Going to fetch tasks due to kick.")
				download_tasks_from_upstream(self.config, mongo_sess)
				if pingback_chan != nil {
					pingback_chan <- true
				}
			}
		}
	}()
}

/**
 * Downloads a chunkn of tasks from the upstream Flamenco Server.
 */
func download_tasks_from_upstream(config *Conf, mongo_sess *mgo.Session) {
	// Try to get as many tasks as we have workers.
	db := mongo_sess.DB("")
	worker_count := WorkerCount(db)

	url_str := fmt.Sprintf("/flamenco/scheduler/tasks/%s?chunk_size=%d",
		config.ManagerId, worker_count)
	rel_url, err := url.Parse(url_str)
	if err != nil {
		log.Printf("Error parsing '%s' as URL; unable to fetch tasks.\n", url_str)
		return
	}

	get_url := config.Flamenco.ResolveReference(rel_url)
	log.Printf("Getting tasks from upstream Flamenco %s\n", get_url)

	req, err := http.NewRequest("GET", get_url.String(), nil)
	if err != nil {
		log.Printf("Unable to create GET request: %s\n", err)
		return
	}
	req.SetBasicAuth(config.ManagerSecret, "")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("ERROR: Unable to GET %s: %s\n", get_url, err)
		return
	}

	if resp.StatusCode >= 300 {
		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			log.Printf("ERROR: Error %d GETing %s: %s\n", resp.StatusCode, get_url, err)
			return
		}

		log.Printf("ERROR: Error %d GETing %s: %s\n", resp.StatusCode, get_url, body)
		return
	}

	if resp.StatusCode == 204 {
		log.Println("No tasks for us; sleeping.")
		return
	}

	// body, err := ioutil.ReadAll(resp.Body)
	// log.Printf("BODY:\n%s\n\n", body)

	// Parse the received tasks.
	var scheduled_tasks []Task
	decoder := json.NewDecoder(resp.Body)
	defer resp.Body.Close()

	if err = decoder.Decode(&scheduled_tasks); err != nil {
		log.Println("Unable to decode scheduled tasks JSON:", err)
		return
	}

	// Insert them into the MongoDB
	log.Printf("Received %d tasks from upstream Flamenco Server.\n", len(scheduled_tasks))
	tasks_coll := db.C("flamenco_tasks")
	for _, task := range scheduled_tasks {
		change, err := tasks_coll.Upsert(bson.M{"_id": task.Id}, task)
		if err != nil {
			log.Printf("ERROR: unable to insert new task %s: %s\n", task.Id.Hex(), err)
			continue
		}

		if change.Updated > 0 {
			log.Printf("WARNING: Upstream server re-queued existing task %s\n", task.Id.Hex())
		} else if change.Matched > 0 {
			log.Printf("Upstream server re-queued existing task %s, but nothing changed\n",
				task.Id.Hex())
		}
	}
}

func (self *UpstreamConnection) ResolveUrl(relative_url string, a ...interface{}) (*url.URL, error) {
	rel_url, err := url.Parse(fmt.Sprintf(relative_url, a...))
	if err != nil {
		return &url.URL{}, err
	}
	url := self.config.Flamenco.ResolveReference(rel_url)

	return url, nil
}

func (self *UpstreamConnection) SendJson(logprefix, method string, url *url.URL,
	payload interface{}, bodyhandler func([]byte) error) error {

	payload_bytes, err := json.Marshal(payload)
	if err != nil {
		log.Printf("%s: ERROR: Unable to marshal JSON: %s\n", logprefix, err)
		return err
	}

	req, err := http.NewRequest("POST", url.String(), bytes.NewBuffer(payload_bytes))
	if err != nil {
		log.Printf("%s: ERROR: Unable to create request: %s\n", logprefix, err)
		return err
	}
	req.Header.Add("Content-Type", "application/json")
	req.SetBasicAuth(self.config.ManagerSecret, "")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("%s: ERROR: Unable to POST to %s: %s\n", logprefix, url, err)
		return err
	}

	body, err := ioutil.ReadAll(resp.Body)
	defer resp.Body.Close()
	if err != nil {
		log.Printf("%s: ERROR: Error %d POSTing to %s: %s\n",
			logprefix, resp.StatusCode, url, err)
		return err
	}

	if resp.StatusCode >= 300 {
		log.Printf("%s: ERROR: Error %d POSTing to %s\n",
			logprefix, resp.StatusCode, url)
		if resp.StatusCode != 404 {
			log.Printf("    body:\n%s\n", body)
		}
		return fmt.Errorf("%s: Error %d POSTing to %s", logprefix, resp.StatusCode, url)
	}

	if bodyhandler != nil {
		return bodyhandler(body)
	}

	return nil
}

/**
 * Sends a StartupNotification document to upstream Flamenco Server.
 * Keeps trying in a goroutine until the notification was succesful.
 */
func (self *UpstreamConnection) SendStartupNotification() {

	notification := StartupNotification{
		ManagerUrl:         self.config.OwnUrl,
		VariablesByVarname: self.config.VariablesByVarname,
		NumberOfWorkers:    0,
	}

	url, err := self.ResolveUrl("/api/flamenco/managers/%s/startup", self.config.ManagerId)
	if err != nil {
		panic(fmt.Sprintf("SendStartupNotification: unable to construct URL: %s\n", err))
	}

	// Performs the actual sending.
	send_startup_notification := func(mongo_sess *mgo.Session) error {
		notification.NumberOfWorkers = WorkerCount(mongo_sess.DB(""))

		err := self.SendJson("SendStartupNotification", "POST", url, &notification, nil)
		if err != nil {
			log.Printf("SendStartupNotification: ERROR: Unable to send: %s\n", err)
			return err
		}

		log.Printf("SendStartupNotification: Done sending notification to upstream Flamenco\n")
		return nil
	}

	go func() {
		// Register as a loop that responds to 'done' being closed.
		self.done_wg.Add(1)
		defer self.done_wg.Done()

		mongo_sess := self.session.Copy()
		defer mongo_sess.Close()

		time.Sleep(STARTUP_NOTIFICATION_INITIAL_DELAY)
		timer_chan := Timer("SendStartupNotification", STARTUP_NOTIFICATION_RETRY,
			self.done, self.done_wg)

		for _ = range timer_chan {
			log.Println("SendStartupNotification: trying to send notification.")
			err := send_startup_notification(mongo_sess)
			if err == nil {
				return
			}
		}

		log.Println("SendStartupNotification: shutting down without succesfully sending notification.")
	}()
}

func (self *UpstreamConnection) SendTaskUpdates(updates *[]TaskUpdate) error {
	url, err := self.ResolveUrl("/api/flamenco/managers/%s/task-update-batch",
		self.config.ManagerId)
	if err != nil {
		panic(fmt.Sprintf("SendTaskUpdates: unable to construct URL: %s\n", err))
	}

	return self.SendJson("SendTaskUpdates", "POST", url, updates, nil)
}

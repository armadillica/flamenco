/**
 * Periodically fetches new tasks from the Flamenco Server, and sends updates back.
 */
package flamenco

import (
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

type UpstreamConnection struct {
	config  *Conf
	session *mgo.Session

	// Send any boolean here to kick the task downloader into downloading new tasks.
	download_kick chan chan bool

	done    chan bool
	done_wg *sync.WaitGroup
}

func ConnectUpstream(config *Conf, session *mgo.Session) *UpstreamConnection {
	upconn := UpstreamConnection{
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

func (self *UpstreamConnection) download_task_loop() {
	timer_chan := Timer("download_task_loop",
		self.config.DownloadTaskSleep,
		true,
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
		config.ManagerId, MaxInt(worker_count, 1))
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
	// TODO Sybren: before inserting, compare to the database and deal with any changed statuses.
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
	payload interface{},
	responsehandler func(resp *http.Response, body []byte) error,
) error {
	authenticate := func(req *http.Request) {
		req.SetBasicAuth(self.config.ManagerSecret, "")
	}

	return SendJson(logprefix, method, url, payload, authenticate, responsehandler)
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

		ok := KillableSleep("SendStartupNotification-initial", STARTUP_NOTIFICATION_INITIAL_DELAY,
			self.done, self.done_wg)
		if !ok {
			log.Println("SendStartupNotification: shutting down without sending startup notification.")
			return
		}
		timer_chan := Timer("SendStartupNotification", STARTUP_NOTIFICATION_RETRY,
			false, self.done, self.done_wg)

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

/**
 * Performs a POST to /api/flamenco/managers/{manager-id}/task-update-batch to
 * send a batch of task updates to the Server.
 */
func (self *UpstreamConnection) SendTaskUpdates(updates *[]TaskUpdate) (*TaskUpdateResponse, error) {
	url, err := self.ResolveUrl("/api/flamenco/managers/%s/task-update-batch",
		self.config.ManagerId)
	if err != nil {
		panic(fmt.Sprintf("SendTaskUpdates: unable to construct URL: %s\n", err))
	}

	response := TaskUpdateResponse{}
	parse_response := func(resp *http.Response, body []byte) error {
		err := json.Unmarshal(body, &response)
		if err != nil {
			log.Printf("SendTaskUpdates: error parsing server response: %s", err)
			return err
		}
		return nil
	}
	err = self.SendJson("SendTaskUpdates", "POST", url, updates, parse_response)

	return &response, err
}

/**
 * Re-fetches a task from the Server, but only if its etag changed.
 * - If the etag changed, the differences between the old and new status are handled.
 * - If the Server cannot be reached, this error is ignored and the task is untouched.
 * - If the Server returns an error code other than 500 Internal Server Error,
 *   (Forbidden, Not Found, etc.) the task is removed from the local task queue.
 *
 * If the task was untouched, this function returns false.
 * If it was changed or removed, this function return true.
 */
func (self *UpstreamConnection) RefetchTask(task *Task) bool {
	get_url, err := self.ResolveUrl("/api/flamenco/tasks/%s", task.Id.Hex())
	log.Printf("Verifying task with Flamenco Server %s\n", get_url)

	req, err := http.NewRequest("GET", get_url.String(), nil)
	if err != nil {
		log.Printf("WARNING: Unable to create GET request: %s\n", err)
		return false
	}
	req.SetBasicAuth(self.config.ManagerSecret, "")
	req.Header["If-None-Match"] = []string{task.Etag}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("WARNING: Unable to re-fetch task: %s\n", err)
		return false
	}

	if resp.StatusCode == http.StatusNotModified {
		// Nothing changed, we're good to go.
		log.Printf("Cached task %s is still the same on the Server\n", task.Id.Hex())
		return false
	}

	if resp.StatusCode >= 500 {
		// Internal errors, we'll ignore that.
		log.Printf("WARNING: Error %d trying to re-fetch task %s\n",
			resp.StatusCode, task.Id.Hex())
		return false
	}
	if 300 <= resp.StatusCode && resp.StatusCode < 400 {
		// Redirects, we'll ignore those too for now.
		log.Printf("WARNING: Redirect %d trying to re-fetch task %s\n",
			resp.StatusCode, task.Id.Hex())
		return false
	}

	// Either the task is gone (or gone-ish, i.e. 4xx code) or it has changed.
	// If it is gone, we handle it as canceled.
	new_task := Task{}

	if resp.StatusCode >= 400 || resp.StatusCode == 204 {
		// Not found, access denied, that kind of stuff. Locally cancel the task.
		log.Printf("WARNING: Code %d when re-fetching task %s; canceling local copy\n",
			resp.StatusCode, task.Id.Hex())

		new_task = *task
		new_task.Status = "canceled"
	} else {
		// Parse the new task we received.
		decoder := json.NewDecoder(resp.Body)
		defer resp.Body.Close()

		if err = decoder.Decode(&new_task); err != nil {
			// We can't decode what's being sent. Remove it from the queue, as we no longer know
			// whether this task is valid at all.
			log.Printf("ERROR: Unable to decode updated tasks JSON from %s: %s", get_url, err)

			new_task = *task
			new_task.Status = "canceled"
		}
	}

	// save the task to the queue.
	log.Printf("Cached task %s was changed on the Server, status=%s, priority=%d.",
		task.Id.Hex(), new_task.Status, new_task.Priority)
	tasks_coll := self.session.DB("").C("flamenco_tasks")
	tasks_coll.UpdateId(task.Id,
		bson.M{"$set": new_task})

	return true
}

/**
 * Periodically fetches new tasks from the Flamenco Server, and sends updates back.
 */
package flamenco

import (
	"encoding/json"
	"fmt"
	"io/ioutil"
	"net/http"
	"net/url"
	"time"

	log "github.com/Sirupsen/logrus"
	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

// Gives the system some time to start up (and open listening HTTP port)
const STARTUP_NOTIFICATION_INITIAL_DELAY = 500 * time.Millisecond

// Duration between consecutive retries of sending the startup notification.
const STARTUP_NOTIFICATION_RETRY = 30 * time.Second

type UpstreamConnection struct {
	closable
	config  *Conf
	session *mgo.Session

	// Send any boolean here to kick the task downloader into downloading new tasks.
	download_kick chan chan bool
}

func ConnectUpstream(config *Conf, session *mgo.Session) *UpstreamConnection {
	upconn := UpstreamConnection{
		makeClosable(),
		config,
		session,
		make(chan chan bool),
	}
	upconn.download_task_loop()

	return &upconn
}

/**
 * Closes the upstream connection by stopping all upload/download loops.
 */
func (self *UpstreamConnection) Close() {
	log.Debugf("UpstreamConnection: shutting down, waiting for shutdown to complete.")
	close(self.download_kick) // TODO: maybe move this between closing of done channel and waiting
	self.closableCloseAndWait()
	log.Info("UpstreamConnection: shutdown complete.")
}

func (self *UpstreamConnection) KickDownloader(synchronous bool) {
	if synchronous {
		pingback := make(chan bool)
		self.download_kick <- pingback
		log.Info("KickDownloader: Waiting for task downloader to finish.")

		// wait for the download to be complete, or the connection to be shut down.
		if !self.closableAdd(1) {
			log.Debugf("KickDownloader: Aborting waiting for task downloader; shutting down.")
			return
		}
		defer self.closableDone()

		for {
			select {
			case <-pingback:
				log.Debugf("KickDownloader: done.")
				return
			case <-self.doneChan:
				log.Debugf("KickDownloader: Aborting waiting for task downloader; shutting down.")
				return
			}
		}
	} else {
		log.Debugf("KickDownloader: asynchronous kick, just kicking.")
		self.download_kick <- nil
	}
}

func (self *UpstreamConnection) download_task_loop() {
	timer_chan := Timer("download_task_loop",
		self.config.DownloadTaskSleep,
		false,
		&self.closable,
	)

	go func() {
		mongo_sess := self.session.Copy()
		defer mongo_sess.Close()

		if !self.closableAdd(1) {
			return
		}
		defer self.closableDone()
		defer log.Info("download_task_loop: Task download goroutine shutting down.")

		for {
			select {
			case <-self.doneChan:
				return
			case _, ok := <-timer_chan:
				if !ok {
					return
				}
				log.Info("download_task_loop: Going to fetch tasks due to periodic timeout.")
				download_tasks_from_upstream(self.config, mongo_sess)
			case pingback_chan, ok := <-self.download_kick:
				if !ok {
					return
				}
				log.Info("download_task_loop: Going to fetch tasks due to kick.")
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
	db := mongo_sess.DB("")

	url_str := fmt.Sprintf("/api/flamenco/managers/%s/depsgraph", config.ManagerId)
	rel_url, err := url.Parse(url_str)
	if err != nil {
		log.Warningf("Error parsing '%s' as URL; unable to fetch tasks.", url_str)
		return
	}

	get_url := config.Flamenco.ResolveReference(rel_url)
	req, err := http.NewRequest("GET", get_url.String(), nil)
	if err != nil {
		log.Warningf("Unable to create GET request: %s", err)
		return
	}
	req.SetBasicAuth(config.ManagerSecret, "")

	// Set If-Modified-Since header on our request.
	settings := GetSettings(db)
	if settings.DepsgraphLastModified != nil {
		log.Infof("Getting tasks from upstream Flamenco %s If-Modified-Since %s", get_url,
			*settings.DepsgraphLastModified)
		req.Header.Set("X-Flamenco-If-Updated-Since", *settings.DepsgraphLastModified)
	} else {
		log.Infof("Getting tasks from upstream Flamenco %s", get_url)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Warningf("Unable to GET %s: %s", get_url, err)
		return
	}
	if resp.StatusCode == http.StatusNotModified {
		log.Debug("Server-side depsgraph was not modified, nothing to do.")
		return
	}
	if resp.StatusCode == http.StatusNoContent {
		log.Info("No tasks for us; sleeping.")
		return
	}
	if resp.StatusCode >= 300 {
		body, err := ioutil.ReadAll(resp.Body)
		if err != nil {
			log.Errorf("Error %d GETing %s: %s", resp.StatusCode, get_url, err)
			return
		}
		log.Errorf("Error %d GETing %s: %s", resp.StatusCode, get_url, body)
		return
	}

	// Parse the received tasks.
	var scheduled_tasks ScheduledTasks
	decoder := json.NewDecoder(resp.Body)
	defer resp.Body.Close()

	if err = decoder.Decode(&scheduled_tasks); err != nil {
		log.Warning("Unable to decode scheduled tasks JSON:", err)
		return
	}

	// Insert them into the MongoDB
	depsgraph := scheduled_tasks.Depsgraph
	if len(depsgraph) > 0 {
		log.Infof("Received %d tasks from upstream Flamenco Server.", len(depsgraph))
	} else {
		// This shouldn't happen, as it should actually have been a 204 or 306.
		log.Debugf("Received %d tasks from upstream Flamenco Server.", len(depsgraph))
	}
	tasks_coll := db.C("flamenco_tasks")
	for _, task := range depsgraph {
		change, err := tasks_coll.Upsert(bson.M{"_id": task.ID}, task)
		if err != nil {
			log.Errorf("unable to insert new task %s: %s", task.ID.Hex(), err)
			continue
		}

		if change.Updated > 0 {
			log.Debug("Upstream server re-queued existing task ", task.ID.Hex())
		} else if change.Matched > 0 {
			log.Debugf("Upstream server re-queued existing task %s, but nothing changed",
				task.ID.Hex())
		}
	}

	// Check if we had a Last-Modified header, since we need to remember that.
	last_modified := resp.Header.Get("X-Flamenco-Last-Updated")
	if last_modified != "" {
		log.Info("Last modified task was at ", last_modified)
		settings.DepsgraphLastModified = &last_modified
		SaveSettings(db, settings)
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
		ManagerURL:         self.config.OwnUrl,
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
			log.Warningf("SendStartupNotification: Unable to send: %s", err)
			return err
		}

		log.Infof("SendStartupNotification: Done sending notification to upstream Flamenco")
		return nil
	}

	go func() {
		// Register as a loop that responds to 'done' being closed.
		if !self.closableAdd(1) {
			log.Warning("SendStartupNotification: shutting down early without sending startup notification.")
			return
		}
		defer self.closableDone()

		mongo_sess := self.session.Copy()
		defer mongo_sess.Close()

		ok := KillableSleep("SendStartupNotification-initial", STARTUP_NOTIFICATION_INITIAL_DELAY,
			&self.closable)
		if !ok {
			log.Warning("SendStartupNotification: shutting down without sending startup notification.")
			return
		}
		timer_chan := Timer("SendStartupNotification", STARTUP_NOTIFICATION_RETRY,
			false, &self.closable)

		for _ = range timer_chan {
			log.Info("SendStartupNotification: trying to send notification.")
			err := send_startup_notification(mongo_sess)
			if err == nil {
				return
			}
		}

		log.Warning("SendStartupNotification: shutting down without succesfully sending notification.")
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
			log.Warningf("SendTaskUpdates: error parsing server response: %s", err)
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
	get_url, err := self.ResolveUrl("/api/flamenco/tasks/%s", task.ID.Hex())
	log.Infof("Verifying task with Flamenco Server %s", get_url)

	req, err := http.NewRequest("GET", get_url.String(), nil)
	if err != nil {
		log.Errorf("WARNING: Unable to create GET request: %s", err)
		return false
	}
	req.SetBasicAuth(self.config.ManagerSecret, "")
	req.Header["If-None-Match"] = []string{task.Etag}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Warningf("Unable to re-fetch task: %s", err)
		return false
	}

	if resp.StatusCode == http.StatusNotModified {
		// Nothing changed, we're good to go.
		log.Infof("Cached task %s is still the same on the Server", task.ID.Hex())
		return false
	}

	if resp.StatusCode >= 500 {
		// Internal errors, we'll ignore that.
		log.Warningf("Error %d trying to re-fetch task %s",
			resp.StatusCode, task.ID.Hex())
		return false
	}
	if 300 <= resp.StatusCode && resp.StatusCode < 400 {
		// Redirects, we'll ignore those too for now.
		log.Warningf("Redirect %d trying to re-fetch task %s, not following redirect.",
			resp.StatusCode, task.ID.Hex())
		return false
	}

	// Either the task is gone (or gone-ish, i.e. 4xx code) or it has changed.
	// If it is gone, we handle it as canceled.
	new_task := Task{}

	if resp.StatusCode >= 400 || resp.StatusCode == 204 {
		// Not found, access denied, that kind of stuff. Locally cancel the task.
		// TODO: probably better to go to "failed".
		log.Warningf("Code %d when re-fetching task %s; canceling local copy",
			resp.StatusCode, task.ID.Hex())

		new_task = *task
		new_task.Status = "canceled"
	} else {
		// Parse the new task we received.
		decoder := json.NewDecoder(resp.Body)
		defer resp.Body.Close()

		if err = decoder.Decode(&new_task); err != nil {
			// We can't decode what's being sent. Remove it from the queue, as we no longer know
			// whether this task is valid at all.
			log.Warningf("Unable to decode updated tasks JSON from %s: %s", get_url, err)

			new_task = *task
			new_task.Status = "canceled"
		}
	}

	// save the task to the queue.
	log.Infof("Cached task %s was changed on the Server, status=%s, priority=%d.",
		task.ID.Hex(), new_task.Status, new_task.Priority)
	tasks_coll := self.session.DB("").C("flamenco_tasks")
	tasks_coll.UpdateId(task.ID,
		bson.M{"$set": new_task})

	return true
}

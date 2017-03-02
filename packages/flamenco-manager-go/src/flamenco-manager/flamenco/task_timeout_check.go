/**
 * Checks active tasks to see if their worker is still alive & running.
 */
package flamenco

import (
	"fmt"
	"time"

	log "github.com/Sirupsen/logrus"
	mgo "gopkg.in/mgo.v2"
)

// Interval for checking all active tasks for timeouts.
const TASK_TIMEOUT_CHECK_INTERVAL = 5 * time.Second
const TASK_TIMEOUT_CHECK_INITIAL_SLEEP = 5 * time.Minute

type TaskTimeoutChecker struct {
	closable
	config  *Conf
	session *mgo.Session
}

func CreateTaskTimeoutChecker(config *Conf, session *mgo.Session) *TaskTimeoutChecker {
	return &TaskTimeoutChecker{
		makeClosable(),
		config, session,
	}
}

func (self *TaskTimeoutChecker) Go() {
	session := self.session.Copy()
	defer session.Close()
	db := session.DB("")

	self.closableAdd(1)
	defer self.closableDone()
	defer log.Info("TaskTimeoutChecker: shutting down.")

	// Start with a delay, so that workers get a chance to push their updates
	// after the manager has started up.
	ok := KillableSleep("TaskTimeoutChecker-initial", TASK_TIMEOUT_CHECK_INITIAL_SLEEP, &self.closable)
	if !ok {
		log.Info("TaskTimeoutChecker: Killable sleep was killed, not even starting checker.")
		return
	}

	timer := Timer("TaskTimeoutCheck", TASK_TIMEOUT_CHECK_INTERVAL, false, &self.closable)

	for _ = range timer {
		self.Check(db)
	}

}

func (self *TaskTimeoutChecker) Close() {
	self.closableCloseAndWait()
	log.Debug("TaskTimeoutChecker: shutdown complete.")
}

func (self *TaskTimeoutChecker) Check(db *mgo.Database) {
	timeout_threshold := UtcNow().Add(-self.config.ActiveTaskTimeoutInterval)
	log.Debugf("Failing all active tasks that have not been touched since %s", timeout_threshold)

	var timedout_tasks []Task
	// find all active tasks that either have never been pinged, or were pinged long ago.
	query := M{
		"status": "active",
		"$or": []M{
			M{"last_worker_ping": M{"$lte": timeout_threshold}},
			M{"last_worker_ping": M{"$exists": false}},
		},
	}
	projection := M{
		"_id":              1,
		"last_worker_ping": 1,
		"worker_id":        1,
		"worker":           1,
		"name":             1,
	}
	if err := db.C("flamenco_tasks").Find(query).Select(projection).All(&timedout_tasks); err != nil {
		log.Warningf("Error finding timed-out tasks: %s", err)
	}

	for _, task := range timedout_tasks {
		log.Warningf("    - Task %s (%s) timed out", task.Name, task.ID.Hex())
		var ident string
		if task.Worker != "" {
			ident = task.Worker
		} else if task.WorkerID != nil {
			ident = task.WorkerID.Hex()
		} else {
			ident = "-no worker-"
		}

		tupdate := TaskUpdate{
			TaskID:     task.ID,
			TaskStatus: "failed",
			Activity:   fmt.Sprintf("Task timed out on worker %s", ident),
			Log: fmt.Sprintf(
				"%s Task %s (%s) timed out, was active but untouched since %s. "+
					"Was handled by worker %s",
				UtcNow().Format(IsoFormat), task.Name, task.ID.Hex(), task.LastWorkerPing, ident),
		}
		QueueTaskUpdate(&tupdate, db)
	}
}

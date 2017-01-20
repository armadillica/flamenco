/**
 * Checks active tasks to see if their worker is still alive & running.
 */
package flamenco

import (
	"fmt"
	"sync"
	"time"

	log "github.com/Sirupsen/logrus"
	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

// Interval for checking all active tasks for timeouts.
const TASK_TIMEOUT_CHECK_INTERVAL = 5 * time.Second
const TASK_TIMEOUT_CHECK_INITIAL_SLEEP = 5 * time.Minute

type TaskTimeoutChecker struct {
	config    *Conf
	session   *mgo.Session
	done_chan chan bool
	done_wg   *sync.WaitGroup
}

func CreateTaskTimeoutChecker(config *Conf, session *mgo.Session) *TaskTimeoutChecker {
	return &TaskTimeoutChecker{
		config, session,
		make(chan bool),
		&sync.WaitGroup{},
	}
}

func (self *TaskTimeoutChecker) Go() {
	session := self.session.Copy()
	defer session.Close()
	db := session.DB("")

	self.done_wg.Add(1)
	defer self.done_wg.Done()
	defer log.Infof("TaskTimeoutChecker: shutting down.")

	// Start with a delay, so that workers get a chance to push their updates
	// after the manager has started up.
	ok := KillableSleep("TaskTimeoutChecker-initial", TASK_TIMEOUT_CHECK_INITIAL_SLEEP,
		self.done_chan, self.done_wg)
	if !ok {
		return
	}

	timer := Timer("TaskTimeoutCheck", TASK_TIMEOUT_CHECK_INTERVAL, false,
		self.done_chan, self.done_wg)

	for _ = range timer {
		self.check(db)
	}

}

func (self *TaskTimeoutChecker) Close() {
	close(self.done_chan)
	log.Debug("TaskTimeoutChecker: waiting for shutdown to finish.")
	self.done_wg.Wait()
	log.Debug("TaskTimeoutChecker: shutdown complete.")
}

func (self *TaskTimeoutChecker) check(db *mgo.Database) {
	timeout_threshold := UtcNow().Add(-self.config.ActiveTaskTimeoutInterval)
	// log.Infof("Failing all active tasks that have not been touched since %s", timeout_threshold)

	// TODO Sybren: Also check that the worker is actually working on the task;
	// it could just as well be working on another task now (so worker is alive, but
	// task.status = "active" is inaccurate).

	var timedout_tasks []Task
	query := bson.M{
		"status":           "active",
		"last_worker_ping": bson.M{"$lte": timeout_threshold},
	}
	projection := bson.M{
		"_id":              1,
		"last_worker_ping": 1,
		"worker_id":        1,
		"worker":           1,
	}
	if err := db.C("flamenco_tasks").Find(query).Select(projection).All(&timedout_tasks); err != nil {
		log.Warningf("Error finding timed-out tasks: %s", err)
	}

	for _, task := range timedout_tasks {
		log.Warningf("    - Task %s (%s) timed out", task.Name, task.Id.Hex())
		tupdate := TaskUpdate{
			TaskId:     task.Id,
			TaskStatus: "failed",
			Activity: fmt.Sprintf("Task timed out on worker %s (%s)",
				task.Worker, task.WorkerId.Hex()),
			Log: fmt.Sprintf(
				"%s Task %s (%s) timed out, was active but untouched since %s. "+
					"Was handled by worker %s (%s)",
				UtcNow(), task.Name, task.Id.Hex(), task.LastWorkerPing,
				task.Worker, task.WorkerId.Hex()),
		}
		QueueTaskUpdate(&tupdate, db)
	}
}

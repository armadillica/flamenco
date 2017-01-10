/*
 * Receives task updates from workers, queues them, and forwards them to the Flamenco Server.
 */
package flamenco

import (
	"fmt"
	"log"
	"net/http"
	"sync"
	"time"

	auth "github.com/abbot/go-http-auth"

	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

const QUEUE_MGO_COLLECTION = "task_update_queue"
const TASK_QUEUE_INSPECT_PERIOD = 1 * time.Second

type TaskUpdatePusher struct {
	config   *Conf
	upstream *UpstreamConnection
	session  *mgo.Session

	// For allowing shutdown.
	done    chan bool
	done_wg *sync.WaitGroup
}

/**
 * Receives a task update from a worker, and queues it for sending to Flamenco Server.
 */
func QueueTaskUpdateFromWorker(w http.ResponseWriter, r *auth.AuthenticatedRequest,
	db *mgo.Database, task_id bson.ObjectId) {
	log.Printf("%s Received task update for task %s\n", r.RemoteAddr, task_id.Hex())

	// Get the worker
	worker, err := FindWorker(r.Username, bson.M{"address": 1}, db)
	if err != nil {
		log.Printf("%s QueueTaskUpdate: Unable to find worker address: %s\n",
			r.RemoteAddr, err)
		w.WriteHeader(http.StatusForbidden)
		fmt.Fprintf(w, "Unable to find worker address: %s", err)
		return
	}

	// Parse the task JSON
	tupdate := TaskUpdate{}
	defer r.Body.Close()
	if err := DecodeJson(w, r.Body, &tupdate, fmt.Sprintf("%s QueueTaskUpdate:", r.RemoteAddr)); err != nil {
		return
	}
	tupdate.TaskId = task_id
	tupdate.Worker = worker.Address

	if err := QueueTaskUpdate(&tupdate, db); err != nil {
		log.Printf("%s: %s", err)
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprintf(w, "Unable to store update: %s\n", err)
		return
	}

	w.WriteHeader(204)
}

func QueueTaskUpdate(tupdate *TaskUpdate, db *mgo.Database) error {
	// For ensuring the ordering of updates. time.Time has nanosecond precision.
	tupdate.ReceivedOnManager = time.Now().UTC()
	tupdate.Id = bson.NewObjectId()

	// Store the update in the queue for sending to the Flamenco Server later.
	task_update_queue := db.C(QUEUE_MGO_COLLECTION)
	if err := task_update_queue.Insert(&tupdate); err != nil {
		return fmt.Errorf("QueueTaskUpdate: error inserting task update in queue: %s", err)
	}

	// Locally apply the change to our cached version of the task too.
	task_coll := db.C("flamenco_tasks")
	updates := bson.M{}
	if tupdate.TaskStatus != "" {
		updates["status"] = tupdate.TaskStatus
	}
	if tupdate.Activity != "" {
		updates["activity"] = tupdate.Activity
	}
	if len(updates) > 0 {
		if err := task_coll.UpdateId(tupdate.TaskId, bson.M{"$set": updates}); err != nil {
			return fmt.Errorf("QueueTaskUpdate: error updating local task cache: %s", err)
		}
	}

	return nil
}

func CreateTaskUpdatePusher(config *Conf, upstream *UpstreamConnection, session *mgo.Session) *TaskUpdatePusher {
	return &TaskUpdatePusher{
		config,
		upstream,
		session,
		make(chan bool),
		new(sync.WaitGroup),
	}
}

/**
 * Closes the task update pusher by stopping all timers & goroutines.
 */
func (self *TaskUpdatePusher) Close() {
	close(self.done)

	// Dirty hack: sleep for a bit to ensure the closing of the 'done'
	// channel can be handled by other goroutines, before handling the
	// closing of the other channels.
	time.Sleep(1)

	log.Println("TaskUpdatePusher: shutting down, waiting for shutdown to complete.")
	self.done_wg.Wait()
	log.Println("TaskUpdatePusher: shutdown complete.")
}

func (self *TaskUpdatePusher) Go() {
	log.Println("TaskUpdatePusher: Starting")
	mongo_sess := self.session.Copy()
	defer mongo_sess.Close()

	var last_push time.Time
	db := mongo_sess.DB("")
	queue := db.C(QUEUE_MGO_COLLECTION)

	self.done_wg.Add(1)
	defer self.done_wg.Done()

	// Investigate the queue periodically.
	timer_chan := Timer("TaskUpdatePusherTimer",
		TASK_QUEUE_INSPECT_PERIOD, false, self.done, self.done_wg)

	for _ = range timer_chan {
		// log.Println("TaskUpdatePusher: checking task update queue")
		update_count, err := Count(queue)
		if err != nil {
			log.Printf("TaskUpdatePusher: ERROR checking queue: %s\n", err)
			continue
		}

		time_since_last_push := time.Now().Sub(last_push)
		may_regular_push := update_count > 0 &&
			(update_count >= self.config.TaskUpdatePushMaxCount ||
				time_since_last_push >= self.config.TaskUpdatePushMaxInterval)
		may_empty_push := time_since_last_push >= self.config.CancelTaskFetchInterval
		if !may_regular_push && !may_empty_push {
			continue
		}

		// Time to push!
		if update_count > 0 {
			log.Printf("TaskUpdatePusher: %d updates are queued", update_count)
		}
		if err := self.push(db); err != nil {
			log.Println("TaskUpdatePusher: unable to push to upstream Flamenco Server:", err)
			continue
		}

		// Only remember we've pushed after it was succesful.
		last_push = time.Now()
	}
}

/**
 * Push task updates to the queue, and handle the response.
 * This response can include a list of task IDs to cancel.
 *
 * NOTE: this function assumes there is only one thread/process doing the pushing,
 * and that we can safely leave documents in the queue until they have been pushed. */
func (self *TaskUpdatePusher) push(db *mgo.Database) error {
	var result []TaskUpdate

	queue := db.C(QUEUE_MGO_COLLECTION)
	tasks_coll := db.C("flamenco_tasks")

	// Figure out what to send.
	query := queue.Find(bson.M{}).Limit(self.config.TaskUpdatePushMaxCount)
	if err := query.All(&result); err != nil {
		return err
	}

	// Perform the sending.
	log.Printf("TaskUpdatePusher: pushing %d updates to upstream Flamenco Server", len(result))
	response, err := self.upstream.SendTaskUpdates(&result)
	if err != nil {
		// TODO Sybren: implement some exponential backoff when things fail to get sent.
		return err
	}

	if len(response.HandledUpdateIds) != len(result) {
		log.Printf("TaskUpdatePusher: server accepted %d of %d items.",
			len(response.HandledUpdateIds), len(result))
	}

	// If succesful, remove the accepted updates from the queue.
	/* If there is an error, don't return just yet - we also want to cancel any task
	   that needs cancelling. */
	var err_unqueue error = nil
	var err_cancel error = nil
	if len(response.HandledUpdateIds) > 0 {
		_, err_unqueue = queue.RemoveAll(bson.M{"_id": bson.M{"$in": response.HandledUpdateIds}})
	}

	// Mark all canceled tasks as such.
	if len(response.CancelTasksIds) > 0 {
		log.Printf("TaskUpdatePusher: canceling %d tasks", len(response.CancelTasksIds))
		_, err_cancel = tasks_coll.UpdateAll(
			bson.M{"_id": bson.M{"$in": response.CancelTasksIds}},
			bson.M{"$set": bson.M{"status": "cancel-requested"}},
		)

		if err_cancel != nil {
			log.Printf("TaskUpdatePusher: unable to cancel tasks: %s", err_cancel)
		}
	}

	if err_unqueue != nil {
		log.Printf("TaskUpdatePusher: This is awkward; we have already sent the task updates")
		log.Println("upstream, but now we cannot un-queue them. Expect duplicates.")
		return err_unqueue
	}

	return err_cancel
}

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
func QueueTaskUpdate(w http.ResponseWriter, r *auth.AuthenticatedRequest, db *mgo.Database,
	task_id bson.ObjectId) {
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

	// For ensuring the ordering of updates. time.Time has nanosecond precision.
	tupdate.ReceivedOnManager = time.Now().UTC()
	tupdate.TaskId = task_id
	tupdate.Id = bson.NewObjectId()
	tupdate.Worker = worker.Address

	// Store the update in the queue for sending to the Flamenco Server later.
	task_update_queue := db.C(QUEUE_MGO_COLLECTION)
	if err := task_update_queue.Insert(&tupdate); err != nil {
		log.Printf("%s QueueTaskUpdate: error inserting task update in queue: %s",
			r.RemoteAddr, err)
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprintf(w, "Unable to store update: %s\n", err)
		return
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
		if err := task_coll.UpdateId(task_id, bson.M{"$set": updates}); err != nil {
			log.Printf("%s QueueTaskUpdate: error updating local task cache: %s",
				r.RemoteAddr, err)
		}
	}

	w.WriteHeader(204)
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

func (self *TaskUpdatePusher) Go() {
	log.Println("TaskUpdatePusher: Starting")
	mongo_sess := self.session.Copy()
	defer mongo_sess.Close()

	var last_push time.Time
	queue := mongo_sess.DB("").C(QUEUE_MGO_COLLECTION)

	// Investigate the queue periodically.
	timer_chan := Timer("TaskUpdatePusherTimer",
		TASK_QUEUE_INSPECT_PERIOD, self.done, self.done_wg)

	for _ = range timer_chan {
		// log.Println("TaskUpdatePusher: checking task update queue")
		update_count, err := Count(queue)
		if err != nil {
			log.Printf("TaskUpdatePusher: ERROR checking queue: %s\n", err)
			continue
		}

		if update_count == 0 {
			continue
		}

		if update_count < self.config.TaskUpdatePushMaxCount && time.Now().Sub(last_push) < self.config.TaskUpdatePushMaxInterval {
			continue
		}

		// Time to push!
		log.Printf("TaskUpdatePusher: %d updates are queued", update_count)
		if err := self.push(queue); err != nil {
			log.Println("TaskUpdatePusher: unable to push to upstream Flamenco Server:", err)
			continue
		}

		// Only remember we've pushed after it was succesful.
		last_push = time.Now()
	}
}

/* NOTE: this function assumes there is only one thread/process doing the pushing,
 * and that we can safely leave documents in the queue until they have been pushed. */
func (self *TaskUpdatePusher) push(queue *mgo.Collection) error {
	var result []TaskUpdate

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

	// If succesful, remove the accepted updates from the queue.
	_, err = queue.RemoveAll(bson.M{"_id": bson.M{"$in": response.HandledUpdateIds}})
	if err != nil {
		log.Printf("TaskUpdatePusher: This is awkward; we have already sent the task updates")
		log.Println("upstream, but now we cannot un-queue them. Expect duplicates.")
		return err
	}

	log.Printf("TaskUpdatePusher: server accepted %d of %d items.",
		len(response.HandledUpdateIds), len(result))

	return nil
}

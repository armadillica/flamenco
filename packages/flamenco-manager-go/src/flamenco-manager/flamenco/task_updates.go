/*
 * Receives task updates from workers, queues them, and forwards them to the Flamenco Server.
 */
package flamenco

import (
	"fmt"
	"net/http"
	"time"

	log "github.com/Sirupsen/logrus"
	auth "github.com/abbot/go-http-auth"

	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

const QUEUE_MGO_COLLECTION = "task_update_queue"
const TASK_QUEUE_INSPECT_PERIOD = 1 * time.Second

type TaskUpdatePusher struct {
	closable
	config   *Conf
	upstream *UpstreamConnection
	session  *mgo.Session
}

/**
 * Receives a task update from a worker, and queues it for sending to Flamenco Server.
 */
func QueueTaskUpdateFromWorker(w http.ResponseWriter, r *auth.AuthenticatedRequest,
	db *mgo.Database, task_id bson.ObjectId) {

	// Get the worker
	worker, err := FindWorker(r.Username, bson.M{"address": 1, "nickname": 1}, db)
	if err != nil {
		log.Warningf("QueueTaskUpdate: Unable to find worker %s at address: %s",
			r.Username, r.RemoteAddr, err)
		w.WriteHeader(http.StatusForbidden)
		fmt.Fprintf(w, "Unable to find worker address: %s", err)
		return
	}
	WorkerSeen(worker, r.RemoteAddr, db)
	log.Infof("QueueTaskUpdateFromWorker: Received task update for task %s from %s",
		task_id.Hex(), worker.Identifier())

	// Parse the task JSON
	tupdate := TaskUpdate{}
	defer r.Body.Close()
	if err := DecodeJson(w, r.Body, &tupdate, fmt.Sprintf("%s QueueTaskUpdate:", worker.Identifier())); err != nil {
		return
	}
	tupdate.TaskID = task_id
	tupdate.Worker = worker.Identifier()

	// Check that this worker is allowed to update this task.
	task := Task{}
	if err := db.C("flamenco_tasks").FindId(task_id).One(&task); err != nil {
		log.Warningf("%s QueueTaskUpdateFromWorker: unable to find task %s for worker %s",
			r.RemoteAddr, task_id.Hex(), worker.Identifier())
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprintf(w, "Task %s is unknown.", task_id.Hex())
		return
	}
	if task.WorkerID != nil && *task.WorkerID != worker.ID {
		log.Warningf("%s QueueTaskUpdateFromWorker: task %s update rejected from %s (%s), task is assigned to %s",
			r.RemoteAddr, task_id.Hex(), worker.ID.Hex(), worker.Identifier(), task.WorkerID.Hex())
		w.WriteHeader(http.StatusConflict)
		fmt.Fprintf(w, "Task %s is assigned to another worker.", task_id.Hex())
		return
	}

	// Only set the task's worker.ID if it's not already set to the current worker.
	var setWorkerID *bson.ObjectId
	if task.WorkerID == nil {
		setWorkerID = &worker.ID
	}
	WorkerPingedTask(setWorkerID, tupdate.TaskID, db)

	if err := QueueTaskUpdate(&tupdate, db); err != nil {
		log.Warningf("%s: %s", worker.Identifier(), err)
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprintf(w, "Unable to store update: %s\n", err)
		return
	}

	w.WriteHeader(204)
}

func QueueTaskUpdate(tupdate *TaskUpdate, db *mgo.Database) error {
	return QueueTaskUpdateWithExtra(tupdate, db, bson.M{})
}

/* Same as QueueTaskUpdate(), but with extra updates to be performed on the local flamenco_tasks
 * collection.
 */
func QueueTaskUpdateWithExtra(tupdate *TaskUpdate, db *mgo.Database, extra_updates bson.M) error {
	// For ensuring the ordering of updates. time.Time has nanosecond precision.
	tupdate.ReceivedOnManager = time.Now().UTC()
	tupdate.ID = bson.NewObjectId()

	// Store the update in the queue for sending to the Flamenco Server later.
	task_update_queue := db.C(QUEUE_MGO_COLLECTION)
	if err := task_update_queue.Insert(&tupdate); err != nil {
		return fmt.Errorf("QueueTaskUpdate: error inserting task update in queue: %s", err)
	}

	// Locally apply the change to our cached version of the task too, if it is a valid transition.
	// This prevents a task being reported active on the worker from overwriting the
	// cancel-requested state we received from the Server.
	task_coll := db.C("flamenco_tasks")
	updates := extra_updates
	if tupdate.TaskStatus != "" {
		// Before blindly applying the task status, first check if the transition is valid.
		if TaskStatusTransitionValid(task_coll, tupdate.TaskID, tupdate.TaskStatus) {
			updates["status"] = tupdate.TaskStatus
		} else {
			log.Warningf("QueueTaskUpdate: not locally applying status=%s for %s",
				tupdate.TaskStatus, tupdate.TaskID.Hex())
		}
	}
	if tupdate.Activity != "" {
		updates["activity"] = tupdate.Activity
	}
	if len(updates) > 0 {
		log.Debugf("QueueTaskUpdate: applying update %s to task %s", updates, tupdate.TaskID.Hex())
		if err := task_coll.UpdateId(tupdate.TaskID, bson.M{"$set": updates}); err != nil {
			if err != mgo.ErrNotFound {
				return fmt.Errorf("QueueTaskUpdate: error updating local task cache: %s", err)
			} else {
				log.Warningf("QueueTaskUpdate: cannot find task %s to update locally", tupdate.TaskID.Hex())
			}
		}
	} else {
		log.Debugf("QueueTaskUpdate: nothing to do locally for task %s", tupdate.TaskID.Hex())
	}

	return nil
}

/**
 * Performs a query on the database to determine the current status, then checks whether
 * the new status is acceptable.
 */
func TaskStatusTransitionValid(task_coll *mgo.Collection, task_id bson.ObjectId, new_status string) bool {
	/* The only actual test we do is when the transition is from cancel-requested
	   to something else. If the new status is valid for cancel-requeted, we don't
	   even need to go to the database to fetch the current status. */
	if ValidForCancelRequested(new_status) {
		return true
	}

	task_curr := Task{}
	if err := task_coll.FindId(task_id).Select(bson.M{"status": 1}).One(&task_curr); err != nil {
		log.Warningf("Unable to find task %s - not accepting status update to %s", err, new_status)
		return false
	}

	// We already know the new status is not valid for cancel-requested.
	// All other statuses are fine, though.
	return task_curr.Status != "cancel-requested"
}

func ValidForCancelRequested(new_status string) bool {
	// Valid statuses to which a task can go after being cancel-requested
	valid_statuses := map[string]bool{
		"canceled":  true, // the expected case
		"failed":    true, // it may have failed on the worker before it could be canceled
		"completed": true, // it may have completed on the worker before it could be canceled
	}

	valid, found := valid_statuses[new_status]
	return valid && found
}

func CreateTaskUpdatePusher(config *Conf, upstream *UpstreamConnection, session *mgo.Session) *TaskUpdatePusher {
	return &TaskUpdatePusher{
		makeClosable(),
		config,
		upstream,
		session,
	}
}

/**
 * Closes the task update pusher by stopping all timers & goroutines.
 */
func (self *TaskUpdatePusher) Close() {
	log.Info("TaskUpdatePusher: shutting down, waiting for shutdown to complete.")
	self.closableCloseAndWait()
	log.Info("TaskUpdatePusher: shutdown complete.")
}

func (self *TaskUpdatePusher) Go() {
	log.Info("TaskUpdatePusher: Starting")
	mongo_sess := self.session.Copy()
	defer mongo_sess.Close()

	var last_push time.Time
	db := mongo_sess.DB("")
	queue := db.C(QUEUE_MGO_COLLECTION)

	if !self.closableAdd(1) {
		return
	}
	defer self.closableDone()

	// Investigate the queue periodically.
	timer_chan := Timer("TaskUpdatePusherTimer",
		TASK_QUEUE_INSPECT_PERIOD, false, &self.closable)

	for _ = range timer_chan {
		// log.Info("TaskUpdatePusher: checking task update queue")
		update_count, err := Count(queue)
		if err != nil {
			log.Warningf("TaskUpdatePusher: ERROR checking queue: %s", err)
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
			log.Debugf("TaskUpdatePusher: %d updates are queued", update_count)
		}
		if err := self.push(db); err != nil {
			log.Warning("TaskUpdatePusher: unable to push to upstream Flamenco Server: ", err)
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

	// Figure out what to send.
	query := queue.Find(bson.M{}).Limit(self.config.TaskUpdatePushMaxCount)
	if err := query.All(&result); err != nil {
		return err
	}

	// Perform the sending.
	if len(result) > 0 {
		log.Infof("TaskUpdatePusher: pushing %d updates to upstream Flamenco Server", len(result))
	} else {
		log.Debugf("TaskUpdatePusher: pushing %d updates to upstream Flamenco Server", len(result))
	}
	response, err := self.upstream.SendTaskUpdates(&result)
	if err != nil {
		// TODO Sybren: implement some exponential backoff when things fail to get sent.
		return err
	}

	if len(response.HandledUpdateIds) != len(result) {
		log.Warningf("TaskUpdatePusher: server accepted %d of %d items.",
			len(response.HandledUpdateIds), len(result))
	}

	// If succesful, remove the accepted updates from the queue.
	/* If there is an error, don't return just yet - we also want to cancel any task
	   that needs cancelling. */
	var err_unqueue error = nil
	if len(response.HandledUpdateIds) > 0 {
		_, err_unqueue = queue.RemoveAll(bson.M{"_id": bson.M{"$in": response.HandledUpdateIds}})
	}
	err_cancel := self.handle_incoming_cancel_requests(response.CancelTasksIds, db)

	if err_unqueue != nil {
		log.Warningf("TaskUpdatePusher: This is awkward; we have already sent the task updates "+
			"upstream, but now we cannot un-queue them. Expect duplicates: %s", err)
		return err_unqueue
	}

	return err_cancel
}

/**
 * Handles the canceling of tasks, as mentioned in the task batch update response.
 */
func (self *TaskUpdatePusher) handle_incoming_cancel_requests(cancel_task_ids []bson.ObjectId, db *mgo.Database) error {
	if len(cancel_task_ids) == 0 {
		return nil
	}

	log.Infof("TaskUpdatePusher: canceling %d tasks", len(cancel_task_ids))
	tasks_coll := db.C("flamenco_tasks")

	// Fetch all to-be-canceled tasks
	var tasks_to_cancel []Task
	err := tasks_coll.Find(bson.M{
		"_id": bson.M{"$in": cancel_task_ids},
	}).Select(bson.M{
		"_id":    1,
		"status": 1,
	}).All(&tasks_to_cancel)
	if err != nil {
		log.Warningf("TaskUpdatePusher: ERROR unable to fetch tasks: %s", err)
		return err
	}

	// Remember which tasks we actually have seen, so we know which ones we don't have cached.
	canceled_count := 0
	seen_tasks := map[bson.ObjectId]bool{}
	go_to_cancel_requested := make([]bson.ObjectId, 0, len(cancel_task_ids))

	queue_task_cancel := func(task_id bson.ObjectId) {
		tupdate := TaskUpdate{
			TaskID:     task_id,
			TaskStatus: "canceled",
		}
		if err := QueueTaskUpdate(&tupdate, db); err != nil {
			log.Warningf("TaskUpdatePusher: Unable to queue task update for canceled task %s, "+
				"expect the task to hang in cancel-requested state.", task_id)
		} else {
			canceled_count++
		}
	}

	for _, task_to_cancel := range tasks_to_cancel {
		seen_tasks[task_to_cancel.ID] = true

		if task_to_cancel.Status == "active" {
			// This needs to be canceled through the worker, and thus go to cancel-requested.
			go_to_cancel_requested = append(go_to_cancel_requested, task_to_cancel.ID)
		} else {
			queue_task_cancel(task_to_cancel.ID)
		}
	}

	// Mark tasks as cancel-requested.
	update_info, err := tasks_coll.UpdateAll(
		bson.M{"_id": bson.M{"$in": go_to_cancel_requested}},
		bson.M{"$set": bson.M{"status": "cancel-requested"}},
	)
	if err != nil {
		log.Warningf("TaskUpdatePusher: unable to mark tasks as cancel-requested: %s", err)
	} else {
		log.Infof("TaskUpdatePusher: marked %d tasks as cancel-requested: %s",
			update_info.Matched, go_to_cancel_requested)
	}

	// Just push a "canceled" update to the Server about tasks we know nothing about.
	for _, task_id := range cancel_task_ids {
		seen, _ := seen_tasks[task_id]
		if seen {
			continue
		}
		log.Warningf("TaskUpdatePusher: unknown task: %s", task_id.Hex())
		queue_task_cancel(task_id)
	}

	log.Infof("TaskUpdatePusher: marked %d tasks as canceled", canceled_count)

	if update_info.Matched+canceled_count < len(cancel_task_ids) {
		log.Warningf("TaskUpdatePusher: I was unable to cancel %d tasks for some reason.",
			len(cancel_task_ids)-(update_info.Matched+canceled_count))
	}

	return err
}

func LogTaskActivity(worker *Worker, task_id bson.ObjectId, activity, log_line string, db *mgo.Database) {
	tupdate := TaskUpdate{
		TaskID:   task_id,
		Activity: activity,
		Log:      log_line,
	}
	if err := QueueTaskUpdate(&tupdate, db); err != nil {
		log.Errorf("LogTaskActivity: Unable to queue task(%s) update for worker %s: %s",
			task_id.Hex(), worker.Identifier(), err)
	}
}

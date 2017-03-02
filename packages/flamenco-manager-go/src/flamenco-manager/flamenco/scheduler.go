package flamenco

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	log "github.com/Sirupsen/logrus"
	auth "github.com/abbot/go-http-auth"

	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

type TaskScheduler struct {
	config   *Conf
	upstream *UpstreamConnection
	session  *mgo.Session

	/* Timestamp of the last time we kicked the task downloader because there weren't any
	 * tasks left for workers. */
	lastUpstreamCheck time.Time
}

func CreateTaskScheduler(config *Conf, upstream *UpstreamConnection, session *mgo.Session) *TaskScheduler {
	return &TaskScheduler{
		config,
		upstream,
		session,
		time.Time{},
	}
}

func (ts *TaskScheduler) ScheduleTask(w http.ResponseWriter, r *auth.AuthenticatedRequest) {
	mongo_sess := ts.session.Copy()
	defer mongo_sess.Close()
	db := mongo_sess.DB("")

	// Fetch the worker's info
	projection := bson.M{"platform": 1, "supported_job_types": 1, "address": 1, "nickname": 1}
	worker, err := FindWorker(r.Username, projection, db)
	if err != nil {
		log.Warningf("ScheduleTask: Unable to find worker, requested from %s: %s", r.RemoteAddr, err)
		w.WriteHeader(http.StatusForbidden)
		fmt.Fprintf(w, "Unable to find worker: %s", err)
		return
	}
	WorkerSeen(worker, r.RemoteAddr, db)
	log.Infof("ScheduleTask: Worker %s asking for a task", worker.Identifier())

	var task *Task
	var was_changed bool
	for attempt := 0; attempt < 1000; attempt++ {
		// Fetch the first available task of a supported job type.
		task = ts.fetchTaskFromQueueOrManager(w, db, worker)
		if task == nil {
			// A response has already been written to 'w'.
			return
		}

		was_changed = ts.upstream.RefetchTask(task)
		if !was_changed {
			break
		}

		log.Debugf("Task %s was changed, reexamining queue.", task.ID.Hex())
	}
	if was_changed {
		log.Errorf("Infinite loop detected, tried 1000 tasks and they all changed...")
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// Update the task status to "active", pushing it as a task update to the manager too.
	task.Status = "active"
	tupdate := TaskUpdate{TaskID: task.ID, TaskStatus: task.Status}
	local_updates := bson.M{
		"worker_id":        worker.ID,
		"last_worker_ping": UtcNow(),
	}
	if err := QueueTaskUpdateWithExtra(&tupdate, db, local_updates); err != nil {
		log.Errorf("Unable to queue task update while assigning task %s to worker %s: %s",
			task.ID.Hex(), worker.Identifier(), err)
		w.WriteHeader(http.StatusInternalServerError)
		return
	}

	// Perform variable replacement on the task.
	ReplaceVariables(ts.config, task, worker)

	// Set it to this worker.
	w.Header().Set("Content-Type", "application/json")
	encoder := json.NewEncoder(w)
	encoder.Encode(task)

	log.Infof("ScheduleTask: assigned task %s to worker %s",
		task.ID.Hex(), worker.Identifier())

	// Push a task log line stating we've assigned this task to the given worker.
	// This is done here, instead of by the worker, so that it's logged even if the worker fails.
	msg := fmt.Sprintf("Manager assigned task to worker %s", worker.Identifier())
	LogTaskActivity(worker, task.ID, msg, time.Now().Format(IsoFormat)+": "+msg, db)
}

/**
 * Fetches a task from either the queue, or if it is empty, from the manager.
 */
func (ts *TaskScheduler) fetchTaskFromQueueOrManager(
	w http.ResponseWriter, db *mgo.Database, worker *Worker) *Task {

	if len(worker.SupportedJobTypes) == 0 {
		log.Warningf("TaskScheduler: worker %s has no supported job types.", worker.Identifier())
		w.WriteHeader(http.StatusNotAcceptable)
		fmt.Fprintln(w, "You do not support any job types.")
		return nil
	}

	result := aggregationPipelineResult{}
	tasks_coll := db.C("flamenco_tasks")

	pipe := tasks_coll.Pipe([]M{
		// 1: Select only tasks that have a runnable status & acceptable job type.
		M{"$match": M{
			"status": M{"$in": []string{"queued", "claimed-by-manager"}},
			// "job_type": M{"$in": []string{"sleeping", "testing"}},
		}},
		// 2: Unwind the parents array, so that we can do a lookup in the next stage.
		M{"$unwind": M{
			"path": "$parents",
			"preserveNullAndEmptyArrays": true,
		}},
		// 3: Look up the parent document for each unwound task.
		// This produces 1-length "parent_doc" arrays.
		M{"$lookup": M{
			"from":         "flamenco_tasks",
			"localField":   "parents",
			"foreignField": "_id",
			"as":           "parent_doc",
		}},
		// 4: Unwind again, to turn the 1-length "parent_doc" arrays into a subdocument.
		M{"$unwind": M{
			"path": "$parent_doc",
			"preserveNullAndEmptyArrays": true,
		}},
		// 5: Group by task ID to undo the unwind, and create an array parent_statuses
		// with booleans indicating whether the parent status is "completed".
		M{"$group": M{
			"_id": "$_id",
			"parent_statuses": M{"$push": M{
				"$eq": []interface{}{
					"completed",
					M{"$ifNull": []string{"$parent_doc.status", "completed"}}}}},
			// This allows us to keep all dynamic properties of the original task document:
			"task": M{"$first": "$$ROOT"},
		}},
		// 6: Turn the list of "parent_statuses" booleans into a single boolean
		M{"$project": M{
			"_id":               0,
			"parents_completed": M{"$allElementsTrue": []string{"$parent_statuses"}},
			"task":              1,
		}},
		// 7: Select only those tasks for which the parents have completed.
		M{"$match": M{
			"parents_completed": true,
		}},
		// 8: just keep the task info, the "parents_runnable" is no longer needed.
		M{"$project": M{"task": 1}},
		// 9: Sort by priority, with highest prio first. If prio is equal, use newest task.
		M{"$sort": bson.D{
			{"task.job_priority", -1},
			{"task.priority", -1},
			{"task._id", 1},
		}},
		// 10: Only return one task.
		M{"$limit": 1},
	})

	err := pipe.One(&result)
	if err == mgo.ErrNotFound {
		log.Infof("TaskScheduler: no more tasks available for %s", worker.Identifier())
		ts.maybeKickTaskDownloader()
		w.WriteHeader(204)
		return nil
	}
	if err != nil {
		log.Errorf("TaskScheduler: Error fetching task for %s: %s", worker.Identifier(), err)
		w.WriteHeader(500)
		return nil
	}

	return result.Task
}

func (ts *TaskScheduler) maybeKickTaskDownloader() {
	dtrt := ts.config.DownloadTaskRecheckThrottle
	if dtrt < 0 || time.Now().Sub(ts.lastUpstreamCheck) <= dtrt {
		return
	}

	log.Infof("TaskScheduler: kicking task downloader")
	ts.lastUpstreamCheck = time.Now()
	ts.upstream.KickDownloader(false)
}

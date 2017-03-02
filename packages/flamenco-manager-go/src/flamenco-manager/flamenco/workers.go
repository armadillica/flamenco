package flamenco

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"time"

	log "github.com/Sirupsen/logrus"
	auth "github.com/abbot/go-http-auth"

	"golang.org/x/crypto/bcrypt"

	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

/**
 * Returns the worker's address, with the nickname in parentheses (if set).
 *
 * Make sure that you include the nickname in the projection when you fetch
 * the worker from MongoDB.
 */
func (worker *Worker) Identifier() string {
	if len(worker.Nickname) > 0 {
		return fmt.Sprintf("%s (%s)", worker.Address, worker.Nickname)
	}
	return worker.Address
}

func RegisterWorker(w http.ResponseWriter, r *http.Request, db *mgo.Database) {
	var err error

	log.Info(r.RemoteAddr, "Worker registering")

	// Parse the given worker information.
	winfo := WorkerRegistration{}
	if err = DecodeJson(w, r.Body, &winfo, fmt.Sprintf("%s RegisterWorker:", r.RemoteAddr)); err != nil {
		return
	}

	// Store it in MongoDB after hashing the password and assigning an ID.
	worker := Worker{}
	worker.Secret = winfo.Secret
	worker.Platform = winfo.Platform
	worker.SupportedJobTypes = winfo.SupportedJobTypes
	worker.Nickname = winfo.Nickname
	worker.Address = r.RemoteAddr

	if err = StoreNewWorker(&worker, db); err != nil {
		log.Errorf(r.RemoteAddr, "Unable to store worker:", err)

		w.WriteHeader(500)
		w.Header().Set("Content-Type", "text/plain")
		fmt.Fprintln(w, "Unable to store worker")

		return
	}

	w.Header().Set("Content-Type", "application/json")
	encoder := json.NewEncoder(w)
	encoder.Encode(worker)
}

func StoreNewWorker(winfo *Worker, db *mgo.Database) error {
	var err error

	// Store it in MongoDB after hashing the password and assigning an ID.
	winfo.ID = bson.NewObjectId()
	winfo.HashedSecret, err = bcrypt.GenerateFromPassword([]byte(winfo.Secret), bcrypt.DefaultCost)
	if err != nil {
		log.Errorf("Unable to hash password:", err)
		return err
	}

	workers_coll := db.C("flamenco_workers")
	if err = workers_coll.Insert(winfo); err != nil {
		log.Errorf("Unable to insert worker in DB:", err)
		return err
	}

	return nil
}

/**
 * Returns the hashed secret of the worker.
 */
func WorkerSecret(user string, db *mgo.Database) string {
	projection := bson.M{"hashed_secret": 1}
	worker, err := FindWorker(user, projection, db)

	if err != nil {
		log.Warning("Error fetching hashed password: ", err)
		return ""
	}

	return string(worker.HashedSecret)
}

/**
 * Returns the worker given its ID.
 */
func FindWorker(worker_id string, projection interface{}, db *mgo.Database) (*Worker, error) {
	worker := Worker{}

	if !bson.IsObjectIdHex(worker_id) {
		return &worker, errors.New("Invalid ObjectID")
	}
	workers_coll := db.C("flamenco_workers")
	err := workers_coll.FindId(bson.ObjectIdHex(worker_id)).Select(projection).One(&worker)

	return &worker, err
}

/**
 * Returns the number of registered workers.
 */
func WorkerCount(db *mgo.Database) int {
	count, err := Count(db.C("flamenco_workers"))
	if err != nil {
		return -1
	}
	return count
}

func WorkerMayRunTask(w http.ResponseWriter, r *auth.AuthenticatedRequest,
	db *mgo.Database, task_id bson.ObjectId) {

	// Get the worker
	worker, err := FindWorker(r.Username, M{"_id": 1, "address": 1, "nickname": 1}, db)
	if err != nil {
		log.Warningf("%s WorkerMayRunTask: Unable to find worker: %s",
			r.RemoteAddr, err)
		w.WriteHeader(http.StatusForbidden)
		fmt.Fprintf(w, "Unable to find worker: %s", err)
		return
	}
	WorkerSeen(worker, r.RemoteAddr, db)
	log.Debugf("WorkerMayRunTask: %s asking if it is allowed to keep running task %s",
		worker.Identifier(), task_id.Hex())

	response := MayKeepRunningResponse{}

	// Get the task and check its status.
	task := Task{}
	if err := db.C("flamenco_tasks").FindId(task_id).One(&task); err != nil {
		log.Warningf("%s WorkerMayRunTask: unable to find task %s for worker %s",
			r.RemoteAddr, task_id.Hex(), worker.ID.Hex())
		response.Reason = fmt.Sprintf("unable to find task %s", task_id.Hex())
	} else if task.WorkerID != nil && *task.WorkerID != worker.ID {
		log.Warningf("%s WorkerMayRunTask: task %s was assigned from worker %s to %s",
			r.RemoteAddr, task_id.Hex(), worker.ID.Hex(), task.WorkerID.Hex())
		response.Reason = fmt.Sprintf("task %s reassigned to another worker", task_id.Hex())
	} else if !IsRunnableTaskStatus(task.Status) {
		log.Warningf("%s WorkerMayRunTask: task %s is in not-runnable status %s, worker %s will stop",
			r.RemoteAddr, task_id.Hex(), task.Status, worker.ID.Hex())
		response.Reason = fmt.Sprintf("task %s in non-runnable status %s", task_id.Hex(), task.Status)
	} else {
		response.MayKeepRunning = true
		WorkerPingedTask(&worker.ID, task_id, db)
	}

	// Send the response
	w.Header().Set("Content-Type", "application/json")
	encoder := json.NewEncoder(w)
	encoder.Encode(response)
}

func IsRunnableTaskStatus(status string) bool {
	runnable_statuses := map[string]bool{
		"active":             true,
		"claimed-by-manager": true,
		"queued":             true,
	}

	runnable, found := runnable_statuses[status]
	return runnable && found
}

/*
 * Mark the task as pinged by the worker.
 * If worker_id is not nil, sets the worker_id field of the task. Otherwise doesn't
 * touch that field and only updates last_worker_ping.
 */
func WorkerPingedTask(worker_id *bson.ObjectId, task_id bson.ObjectId, db *mgo.Database) {
	tasks_coll := db.C("flamenco_tasks")

	updates := bson.M{
		"last_worker_ping": UtcNow(),
	}
	if worker_id != nil {
		updates["worker_id"] = *worker_id
	}

	if err := tasks_coll.UpdateId(task_id, bson.M{"$set": updates}); err != nil {
		log.Errorf("WorkerPingedTask: ERROR unable to update last_worker_ping on task %s: %s",
			task_id.Hex(), err)
	}
}

/**
 * Registers that we have seen this worker at a certain address.
 */
func WorkerSeen(worker *Worker, remote_addr string, db *mgo.Database) {
	worker.LastActivity = UtcNow()

	updates := bson.M{
		"last_activity": worker.LastActivity,
	}

	if worker.Address != remote_addr {
		worker.Address = remote_addr
		updates["address"] = remote_addr
	}

	if err := db.C("flamenco_workers").UpdateId(worker.ID, bson.M{"$set": updates}); err != nil {
		log.Errorf("WorkerSeen: unable to update worker %s in MongoDB: %s", worker.ID, err)
	}
}

/**
 * Re-queues all active tasks (should be only one) that are assigned to this worker.
 */
func WorkerSignOff(w http.ResponseWriter, r *auth.AuthenticatedRequest, db *mgo.Database) {
	// Get the worker
	worker, err := FindWorker(r.Username, bson.M{"_id": 1, "address": 1, "nickname": 1}, db)
	if err != nil {
		log.Warningf("%s WorkerSignOff: Unable to find worker: %s", r.RemoteAddr, err)
		w.WriteHeader(http.StatusForbidden)
		return
	}
	w_ident := worker.Identifier()

	log.Warningf("%s Worker %s signing off", r.RemoteAddr, w_ident)

	// Update the tasks assigned to the worker.
	var tasks []Task
	query := bson.M{
		"worker_id": worker.ID,
		"status":    "active",
	}
	sent_header := false
	if err := db.C("flamenco_tasks").Find(query).All(&tasks); err != nil {
		log.Warningf("WorkerSignOff: unable to find active tasks of worker %s in MongoDB: %s",
			w_ident, err)
		w.WriteHeader(http.StatusInternalServerError)
		sent_header = true
	} else {
		tupdate := TaskUpdate{
			TaskStatus: "claimed-by-manager",
			Worker:     "-", // no longer assigned to any worker
			Activity:   fmt.Sprintf("Re-queued task after worker %s signed off", w_ident),
			Log: fmt.Sprintf("%s: Manager re-queued task after worker %s signed off",
				time.Now(), w_ident),
		}

		for _, task := range tasks {
			tupdate.TaskID = task.ID
			if err := QueueTaskUpdate(&tupdate, db); err != nil {
				if !sent_header {
					w.WriteHeader(http.StatusInternalServerError)
					sent_header = true
				}
				fmt.Fprintf(w, "Error updating task %s: %s\n", task.ID.Hex(), err)
				log.Errorf("WorkerSignOff: unable to update task %s for worker %s in MongoDB: %s",
					task.ID.Hex(), w_ident, err)
			}
		}
	}

	// Update the worker itself, to show it's down in the DB too.
	worker.Status = "down"
	updates := bson.M{
		"status": worker.Status,
	}
	if err := db.C("flamenco_workers").UpdateId(worker.ID, bson.M{"$set": updates}); err != nil {
		if !sent_header {
			w.WriteHeader(http.StatusInternalServerError)
		}
		log.Errorf("WorkerSignOff: unable to update worker %s in MongoDB: %s", w_ident, err)
	}
}

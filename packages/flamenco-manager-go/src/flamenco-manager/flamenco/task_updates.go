package flamenco

import (
	"fmt"
	"log"
	"net/http"
	"time"

	auth "github.com/abbot/go-http-auth"

	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

func HandleTaskUpdate(w http.ResponseWriter, r *auth.AuthenticatedRequest, db *mgo.Database,
	task_id bson.ObjectId) {
	log.Printf("%s Received task update for task %s\n", r.RemoteAddr, task_id.Hex())

	// Parse the task JSON
	tupdate := TaskUpdate{}
	defer r.Body.Close()
	if err := DecodeJson(w, r.Body, &tupdate, fmt.Sprintf("%s HandleTaskUpdate:", r.RemoteAddr)); err != nil {
		return
	}

	// For ensuring the ordering of updates. time.Time has nanosecond precision.
	tupdate.ReceivedOnManager = time.Now().UTC()
	tupdate.TaskId = task_id

	// Store the update in the queue for sending to the Flamenco Server later.
	task_update_queue := db.C("task_update_queue")
	if err := task_update_queue.Insert(&tupdate); err != nil {
		log.Printf("%s HandleTaskUpdate: error inserting task update in queue: %s",
			r.RemoteAddr, err)
		w.WriteHeader(http.StatusInternalServerError)
		fmt.Fprintf(w, "Unable to store update: %s\n", err)
		return
	}

	w.WriteHeader(204)
}

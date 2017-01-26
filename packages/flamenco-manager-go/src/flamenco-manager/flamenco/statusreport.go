package flamenco

import (
	"encoding/json"
	"fmt"
	"net/http"

	log "github.com/Sirupsen/logrus"
	mgo "gopkg.in/mgo.v2"
)

/**
 * Reports the status of the manager in JSON.
 */
func SendStatusReport(w http.ResponseWriter, r *http.Request, session *mgo.Session,
	flamenco_version string) {
	log.Info(r.RemoteAddr, "Status request received")

	mongo_sess := session.Copy()
	defer mongo_sess.Close()
	db := mongo_sess.DB("")

	var task_count, worker_count int
	var err error
	if task_count, err = Count(db.C("flamenco_tasks")); err != nil {
		fmt.Printf("ERROR : %s\n", err.Error())
		return
	}
	if worker_count, err = Count(db.C("flamenco_workers")); err != nil {
		fmt.Printf("ERROR : %s\n", err.Error())
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "close")

	statusreport := StatusReport{
		worker_count,
		task_count,
		flamenco_version,
	}

	encoder := json.NewEncoder(w)
	encoder.Encode(statusreport)
}

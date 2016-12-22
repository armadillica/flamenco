package main

import (
	"log"
	"net/http"
	"strings"

	"gopkg.in/mgo.v2"

	auth "github.com/abbot/go-http-auth"

	"flamenco-manager/flamenco"

	"github.com/gorilla/mux"
)

// MongoDB session
var session *mgo.Session
var config flamenco.Conf
var upstream *flamenco.UpstreamConnection
var task_scheduler *flamenco.TaskScheduler

func http_status(w http.ResponseWriter, r *http.Request) {
	flamenco.SendStatusReport(w, r, session)
}

func http_register_worker(w http.ResponseWriter, r *http.Request) {
	mongo_sess := session.Copy()
	defer mongo_sess.Close()
	flamenco.RegisterWorker(w, r, mongo_sess.DB(""))
}

func http_schedule_task(w http.ResponseWriter, r *auth.AuthenticatedRequest) {
	task_scheduler.ScheduleTask(w, r)
}

func http_kick(w http.ResponseWriter, r *http.Request) {
	upstream.KickDownloader(false)
	w.WriteHeader(204)
}

func worker_secret(user, realm string) string {
	mongo_sess := session.Copy()
	defer mongo_sess.Close()

	return flamenco.WorkerSecret(user, mongo_sess.DB(""))
}

func main() {
	config = flamenco.GetConf()
	log.Println("MongoDB database server :", config.DatabaseUrl)
	log.Println("Upstream Flamenco server:", config.Flamenco)

	session = flamenco.MongoSession(&config)
	upstream = flamenco.ConnectUpstream(&config, session)
	task_scheduler = flamenco.CreateTaskScheduler(&config, upstream, session)

	// Set up our own HTTP server
	worker_authenticator := auth.NewBasicAuthenticator("Flamenco Manager", worker_secret)
	router := mux.NewRouter().StrictSlash(true)
	router.HandleFunc("/", http_status).Methods("GET")
	router.HandleFunc("/register-worker", http_register_worker).Methods("POST")
	router.HandleFunc("/task", worker_authenticator.Wrap(http_schedule_task)).Methods("POST")
	router.HandleFunc("/kick", http_kick)
	log.Println("Listening at            :", config.Listen)

	upstream.SendStartupNotification()

	// Fall back to insecure server if TLS certificate/key is not defined.
	if config.TLSCert == "" || config.TLSKey == "" {
		log.Println("WARNING: TLS not enabled!")

		config.OwnUrl = strings.Replace(config.OwnUrl, "https://", "http://", 1)
		log.Println("My URL is               :", config.OwnUrl)
		log.Fatal(http.ListenAndServe(config.Listen, router))
	}

	config.OwnUrl = strings.Replace(config.OwnUrl, "http://", "https://", 1)
	log.Println("My URL is               :", config.OwnUrl)

	log.Fatal(http.ListenAndServeTLS(
		config.Listen,
		config.TLSCert,
		config.TLSKey,
		router))
}

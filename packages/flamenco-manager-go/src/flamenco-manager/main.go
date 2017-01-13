package main

import (
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strings"
	"time"

	"gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"

	auth "github.com/abbot/go-http-auth"

	"flamenco-manager/flamenco"

	"github.com/gorilla/mux"
)

// MongoDB session
var session *mgo.Session
var config flamenco.Conf
var upstream *flamenco.UpstreamConnection
var task_scheduler *flamenco.TaskScheduler
var task_update_pusher *flamenco.TaskUpdatePusher
var task_timeout_checker *flamenco.TaskTimeoutChecker

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

func http_task_update(w http.ResponseWriter, r *auth.AuthenticatedRequest) {
	mongo_sess := session.Copy()
	defer mongo_sess.Close()

	vars := mux.Vars(&r.Request)
	task_id := vars["task-id"]

	if !bson.IsObjectIdHex(task_id) {
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprintf(w, "Invalid ObjectID passed as task ID: %s\n", task_id)
		return
	}

	flamenco.QueueTaskUpdateFromWorker(w, r, mongo_sess.DB(""), bson.ObjectIdHex(task_id))
}

/**
 * Called by a worker, to check whether it is allowed to keep running this task.
 */
func http_worker_may_run_task(w http.ResponseWriter, r *auth.AuthenticatedRequest) {
	mongo_sess := session.Copy()
	defer mongo_sess.Close()

	vars := mux.Vars(&r.Request)
	task_id := vars["task-id"]

	if !bson.IsObjectIdHex(task_id) {
		w.WriteHeader(http.StatusNotFound)
		fmt.Fprintf(w, "Invalid ObjectID passed as task ID: %s\n", task_id)
		return
	}

	flamenco.WorkerMayRunTask(w, r, mongo_sess.DB(""), bson.ObjectIdHex(task_id))
}

func worker_secret(user, realm string) string {
	mongo_sess := session.Copy()
	defer mongo_sess.Close()

	return flamenco.WorkerSecret(user, mongo_sess.DB(""))
}

func shutdown() {
	// Always shut down after 2 seconds.
	timeout := flamenco.TimeoutAfter(2 * time.Second)

	go func() {
		log.Println("Interrupt signal received, shutting down.")
		task_timeout_checker.Close()
		task_update_pusher.Close()
		upstream.Close()
		session.Close()
		log.Println("Shutdown complete, stopping process.")
		timeout <- false
	}()

	if <-timeout {
		log.Println("Shutdown forced, stopping process.")
	}
	os.Exit(-2)
}

func main() {
	log.SetFlags(log.Ldate | log.Ltime | log.Lmicroseconds | log.Lshortfile)

	config = flamenco.GetConf()
	has_tls := config.TLSCert != "" && config.TLSKey != ""
	log.Println("MongoDB database server :", config.DatabaseUrl)
	log.Println("Upstream Flamenco server:", config.Flamenco)
	log.Println("My URL is               :", config.OwnUrl)
	log.Println("Listening at            :", config.Listen)
	if has_tls {
		config.OwnUrl = strings.Replace(config.OwnUrl, "http://", "https://", 1)
	} else {
		config.OwnUrl = strings.Replace(config.OwnUrl, "https://", "http://", 1)
		log.Println("WARNING: TLS not enabled!")
	}

	session = flamenco.MongoSession(&config)
	upstream = flamenco.ConnectUpstream(&config, session)
	task_scheduler = flamenco.CreateTaskScheduler(&config, upstream, session)
	task_update_pusher = flamenco.CreateTaskUpdatePusher(&config, upstream, session)
	task_timeout_checker = flamenco.CreateTaskTimeoutChecker(&config, session)

	// Set up our own HTTP server
	worker_authenticator := auth.NewBasicAuthenticator("Flamenco Manager", worker_secret)
	router := mux.NewRouter().StrictSlash(true)
	router.HandleFunc("/", http_status).Methods("GET")
	router.HandleFunc("/register-worker", http_register_worker).Methods("POST")
	router.HandleFunc("/task", worker_authenticator.Wrap(http_schedule_task)).Methods("POST")
	router.HandleFunc("/tasks/{task-id}/update", worker_authenticator.Wrap(http_task_update)).Methods("POST")
	router.HandleFunc("/may-i-run/{task-id}", worker_authenticator.Wrap(http_worker_may_run_task)).Methods("GET")
	router.HandleFunc("/kick", http_kick)

	upstream.SendStartupNotification()
	go task_update_pusher.Go()
	go task_timeout_checker.Go()

	// Handle Ctrl+C
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)
	go func() {
		for _ = range c {
			// Run the shutdown sequence in a goroutine, so that multiple Ctrl+C presses can be handled in parallel.
			go shutdown()
		}
	}()

	// Fall back to insecure server if TLS certificate/key is not defined.
	if !has_tls {
		log.Fatal(http.ListenAndServe(config.Listen, router))
	} else {
		log.Fatal(http.ListenAndServeTLS(
			config.Listen,
			config.TLSCert,
			config.TLSKey,
			router))
	}
}

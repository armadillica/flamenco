package flamenco

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"

	"golang.org/x/crypto/bcrypt"

	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

func RegisterWorker(w http.ResponseWriter, r *http.Request, db *mgo.Database) {
	var err error

	log.Println(r.RemoteAddr, "Worker registering")

	// Parse the given worker information.
	winfo := WorkerRegistration{}
	decoder := json.NewDecoder(r.Body)
	defer r.Body.Close()

	if err = decoder.Decode(&winfo); err != nil {
		log.Println(r.RemoteAddr, "Unable to decode worker JSON:", err)
		return
	}

	// Store it in MongoDB after hashing the password and assigning an ID.
	worker := Worker{}
	worker.Secret = winfo.Secret
	worker.Platform = winfo.Platform
	worker.SupportedJobTypes = winfo.SupportedJobTypes
	if err = StoreWorker(&worker, db); err != nil {
		log.Println(r.RemoteAddr, "Unable to store worker:", err)

		w.WriteHeader(500)
		w.Header().Set("Content-Type", "text/plain")
		fmt.Fprintln(w, "Unable to store worker")

		return
	}

	w.Header().Set("Content-Type", "application/json")
	encoder := json.NewEncoder(w)
	encoder.Encode(worker)
}

func StoreWorker(winfo *Worker, db *mgo.Database) error {
	var err error

	// Store it in MongoDB after hashing the password and assigning an ID.
	winfo.Id = bson.NewObjectId()
	winfo.HashedSecret, err = bcrypt.GenerateFromPassword([]byte(winfo.Secret), bcrypt.DefaultCost)
	if err != nil {
		log.Println("Unable to hash password:", err)
		return err
	}

	workers_coll := db.C("flamenco_workers")
	if err = workers_coll.Insert(winfo); err != nil {
		log.Println("Unable to insert worker in DB:", err)
		return err
	}

	return nil
}

/**
 * Returns the hashed secret of the worker.
 */
func WorkerSecret(user string, db *mgo.Database) string {
	if !bson.IsObjectIdHex(user) {
		log.Printf("WorkerSecret: Invalid ObjectID passed as username: %s\n", user)
		return ""
	}
	workers_coll := db.C("flamenco_workers")
	worker := Worker{}

	query := bson.M{"_id": bson.ObjectIdHex(user)}
	projection := bson.M{"hashed_secret": 1}

	if err := workers_coll.Find(query).Select(projection).One(&worker); err != nil {
		log.Println("Error fetching hashed password: ", err)
		return ""
	}

	return string(worker.HashedSecret)
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

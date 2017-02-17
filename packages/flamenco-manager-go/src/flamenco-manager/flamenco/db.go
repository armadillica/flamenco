package flamenco

import (
	"bufio"
	"fmt"
	"os"

	log "github.com/Sirupsen/logrus"
	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

type countresult struct {
	Count int `bson:"count"`
}

// M is a shortcut for bson.M to make longer queries easier to read.
type M bson.M

// MongoSession returns a MongoDB session.
//
// The database name should be configured in the database URL.
// You can use this default database using session.DB("").
func MongoSession(config *Conf) *mgo.Session {
	var err error
	var session *mgo.Session

	log.Infof("Connecting to MongoDB at %s", config.DatabaseUrl)
	if session, err = mgo.Dial(config.DatabaseUrl); err != nil {
		panic(err)
	}
	session.SetMode(mgo.Monotonic, true)

	ensureIndices(session)

	return session
}

func ensureIndices(session *mgo.Session) {
	db := session.DB("")

	index := mgo.Index{
		Key:        []string{"status", "priority"},
		Unique:     false,
		DropDups:   false,
		Background: false,
		Sparse:     false,
	}
	if err := db.C("flamenco_tasks").EnsureIndex(index); err != nil {
		panic(err)
	}

	index = mgo.Index{
		Key:        []string{"task_id", "received_on_manager"},
		Unique:     false,
		DropDups:   false,
		Background: false,
		Sparse:     false,
	}
	if err := db.C("task_update_queue").EnsureIndex(index); err != nil {
		panic(err)
	}
}

// Count returns the number of documents in the given collection.
func Count(coll *mgo.Collection) (int, error) {
	aggrOps := []bson.M{
		bson.M{
			"$group": bson.M{
				"_id":   nil,
				"count": bson.M{"$sum": 1},
			},
		},
	}
	pipe := coll.Pipe(aggrOps)
	result := countresult{}
	if err := pipe.One(&result); err != nil {
		if err == mgo.ErrNotFound {
			// An empty collection is not an error.
			return 0, nil
		}
		return -1, err
	}

	return result.Count, nil
}

// GetSettings returns the settings as saved in our MongoDB.
func GetSettings(db *mgo.Database) *SettingsInMongo {
	settings := &SettingsInMongo{}
	err := db.C("settings").Find(bson.M{}).One(settings)
	if err != nil && err != mgo.ErrNotFound {
		log.Panic("db.GetSettings: Unable to get settings: ", err)
	}

	return settings
}

// SaveSettings stores the given settings in MongoDB.
func SaveSettings(db *mgo.Database, settings *SettingsInMongo) {
	_, err := db.C("settings").Upsert(bson.M{}, settings)
	if err != nil && err != mgo.ErrNotFound {
		log.Panic("db.SaveSettings: Unable to save settings: ", err)
	}
}

// CleanSlate erases all tasks in the flamenco_tasks collection.
func CleanSlate(db *mgo.Database) {
	fmt.Println("")
	fmt.Println("Performing Clean Slate operation, this will erase all tasks from the local DB.")
	fmt.Println("After performing the Clean Slate, Flamenco-Manager will shut down.")
	fmt.Println("Press [ENTER] to continue, [Ctrl+C] to abort.")
	bufio.NewReader(os.Stdin).ReadLine()

	info, err := db.C("flamenco_tasks").RemoveAll(bson.M{})
	if err != nil {
		log.WithError(err).Panic("unable to erase all tasks")
	}
	log.Warningf("Erased %d tasks", info.Removed)

	settings := GetSettings(db)
	settings.DepsgraphLastModified = nil
	SaveSettings(db, settings)
}

package flamenco

import (
	log "github.com/Sirupsen/logrus"
	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

type countresult struct {
	Count int `bson:"count"`
}

/**
 * Returns a MongoDB session.
 *
 * The database name should be configured in the database URL.
 * You can use this default database using session.DB("").
 */
func MongoSession(config *Conf) *mgo.Session {
	var err error
	var session *mgo.Session

	log.Infof("Connecting to MongoDB at %s", config.DatabaseUrl)
	if session, err = mgo.Dial(config.DatabaseUrl); err != nil {
		panic(err)
	}
	session.SetMode(mgo.Monotonic, true)

	ensure_indices(session)

	return session
}

func ensure_indices(session *mgo.Session) {
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

/**
 * Counts the number of documents in the given collection.
 */
func Count(coll *mgo.Collection) (int, error) {
	aggr_ops := []bson.M{
		bson.M{
			"$group": bson.M{
				"_id":   nil,
				"count": bson.M{"$sum": 1},
			},
		},
	}
	pipe := coll.Pipe(aggr_ops)
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

func GetSettings(db *mgo.Database) *SettingsInMongo {
	settings := &SettingsInMongo{}
	err := db.C("settings").Find(bson.M{}).One(settings)
	if err != nil && err != mgo.ErrNotFound {
		log.Errorf("db.GetSettings: Unable to get settings: ", err)
	}

	return settings
}

func SaveSettings(db *mgo.Database, settings *SettingsInMongo) {
	_, err := db.C("settings").Upsert(bson.M{}, settings)
	if err != nil && err != mgo.ErrNotFound {
		log.Errorf("db.SaveSettings: Unable to save settings: ", err)
	}
}

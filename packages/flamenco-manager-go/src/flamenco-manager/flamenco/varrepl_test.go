package flamenco

import (
	"flag"
	"os"
	"testing"

	log "github.com/Sirupsen/logrus"
	"github.com/stretchr/testify/assert"

	"gopkg.in/mgo.v2/bson"
)

func TestMain(m *testing.M) {
	flag.Parse()
	log.SetLevel(log.InfoLevel)

	config := GetTestConfig()
	session := MongoSession(&config)
	db := session.DB("")

	if err := db.DropDatabase(); err != nil {
		panic("Unable to drop test database!")
	}

	os.Exit(m.Run())
}

func TestReplaceVariables(t *testing.T) {
	config := GetTestConfig()
	task := Task{
		Commands: []Command{
			Command{"echo", bson.M{"message": "Running Blender from {blender} {blender}"}},
			Command{"sleep", bson.M{"{blender}": 3}},
		},
	}
	worker := Worker{
		Platform: "linux",
	}

	ReplaceVariables(&config, &task, &worker)

	// Substitution should happen as often as needed.
	assert.Equal(t,
		"Running Blender from /opt/myblenderbuild/blender /opt/myblenderbuild/blender",
		task.Commands[0].Settings["message"],
	)

	// No substitution on keys, just on values.
	assert.Equal(t, 3, task.Commands[1].Settings["{blender}"])
}

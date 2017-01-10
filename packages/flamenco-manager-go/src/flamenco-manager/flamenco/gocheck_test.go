/**
 * Common test functionality, and integration with GoCheck.
 */
package flamenco

import (
	"testing"
	"time"

	check "gopkg.in/check.v1"
	"gopkg.in/mgo.v2/bson"
)

// Hook up gocheck into the "go test" runner.
// You only need one of these per package, or tests will run multiple times.
func TestWithGocheck(t *testing.T) { check.TestingT(t) }

func TimeoutAfter(duration time.Duration) chan bool {
	timeout := make(chan bool, 1)

	go func() {
		time.Sleep(duration)
		timeout <- true
	}()

	return timeout
}

func ConstructTestTask(task_id, job_type string) Task {
	return ConstructTestTaskWithPrio(task_id, job_type, 50)
}

func ConstructTestTaskWithPrio(task_id, job_type string, priority int) Task {
	return Task{
		Id:       bson.ObjectIdHex(task_id),
		Etag:     "1234567",
		Job:      bson.ObjectIdHex("bbbbbbbbbbbbbbbbbbbbbbbb"),
		Manager:  bson.ObjectIdHex("cccccccccccccccccccccccc"),
		Project:  bson.ObjectIdHex("dddddddddddddddddddddddd"),
		User:     bson.ObjectIdHex("eeeeeeeeeeeeeeeeeeeeeeee"),
		Name:     "Test task",
		Status:   "queued",
		Priority: priority,
		JobType:  job_type,
		Commands: []Command{
			Command{"echo", bson.M{"message": "Running Blender from {blender}"}},
			Command{"sleep", bson.M{"time_in_seconds": 3}},
		},
		Parents: []bson.ObjectId{
			bson.ObjectIdHex("ffffffffffffffffffffffff"),
		},
		Worker: "worker1",
	}
}

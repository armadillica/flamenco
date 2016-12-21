package flamenco

import (
	"encoding/json"
	"log"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	auth "github.com/abbot/go-http-auth"
	"github.com/stretchr/testify/assert"

	"gopkg.in/jarcoal/httpmock.v1"
	"gopkg.in/mgo.v2/bson"
)

func check(u string, ch chan<- bool) {
	time.Sleep(4 * time.Second)
	ch <- true
}

func IsReachable(urls []string) bool {
	ch := make(chan bool, len(urls))
	for _, url := range urls {
		go check(url, ch)
	}
	time.AfterFunc(time.Second, func() { ch <- false })
	return <-ch
}

func construct_task(task_id, job_type string) Task {
	return Task{
		Id:       bson.ObjectIdHex(task_id),
		Etag:     "1234567",
		Job:      bson.ObjectIdHex("bbbbbbbbbbbbbbbbbbbbbbbb"),
		Manager:  bson.ObjectIdHex("cccccccccccccccccccccccc"),
		Project:  bson.ObjectIdHex("dddddddddddddddddddddddd"),
		User:     bson.ObjectIdHex("eeeeeeeeeeeeeeeeeeeeeeee"),
		Name:     "Test task",
		Status:   "queued",
		Priority: 50,
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

func TestSchedulerPatchUpstream(t *testing.T) {
	config := GetTestConfig()
	session := MongoSession(&config)
	// db := session.DB("")

	task := construct_task("aaaaaaaaaaaaaaaaaaaaaaaa", "testing")

	httpmock.Activate()
	defer httpmock.DeactivateAndReset()

	timeout := make(chan bool, 1)
	// Timeout after 1 second.
	go func() {
		time.Sleep(1 * time.Second)
		timeout <- true
	}()

	httpmock.RegisterResponder(
		"PATCH",
		"http://localhost:51234/api/flamenco/tasks/aaaaaaaaaaaaaaaaaaaaaaaa",
		func(req *http.Request) (*http.Response, error) {
			// TODO: test contents of patch
			defer func() { timeout <- false }()
			log.Println("PATCH from manager received on server.")

			return httpmock.NewStringResponse(204, ""), nil
		},
	)

	upstream := ConnectUpstream(&config, session)
	defer upstream.Close()

	upstream.UploadChannel <- &task

	timedout := <-timeout
	assert.False(t, timedout, "HTTP PATCH to Flamenco not performed")
}

/**
 * In this test we don't mock the upstream HTTP connection, so it's normal to see
 * errors about failed PATCH requests. These are harmless. As a matter of fact, testing
 * in such error conditions is good; task scheduling should keep working.
 */
func TestVariableReplacement(t *testing.T) {
	config := GetTestConfig()
	session := MongoSession(&config)
	db := session.DB("")

	upstream := ConnectUpstream(&config, session)
	defer upstream.Close()

	sched := CreateTaskScheduler(&config, upstream, session)

	// Store task in DB.
	task := construct_task("aaaaaaaaaaaaaaaaaaaaaaaa", "testing")
	if err := db.C("flamenco_tasks").Insert(task); err != nil {
		t.Fatal("Unable to insert test task", err)
	}
	task2 := construct_task("1aaaaaaaaaaaaaaaaaaaaaaa", "sleeping")
	if err := db.C("flamenco_tasks").Insert(task2); err != nil {
		t.Fatal("Unable to insert test task 2", err)
	}

	// Store workers in DB, on purpose in the opposite order as the tasks.
	worker_lnx := Worker{
		Platform:          "linux",
		SupportedJobTypes: []string{"sleeping"},
	}
	if err := StoreWorker(&worker_lnx, db); err != nil {
		t.Fatal("Unable to insert test worker_lnx", err)
	}
	worker_win := Worker{
		Platform:          "windows",
		SupportedJobTypes: []string{"testing"},
	}
	if err := StoreWorker(&worker_win, db); err != nil {
		t.Fatal("Unable to insert test worker_win", err)
	}

	// Perform HTTP request
	resp_rec := httptest.NewRecorder()
	request, _ := http.NewRequest("GET", "/task", nil)
	ar := &auth.AuthenticatedRequest{Request: *request, Username: worker_lnx.Id.Hex()}
	sched.ScheduleTask(resp_rec, ar)

	// Check the response JSON
	assert.Equal(t, 200, resp_rec.Code)
	headers := resp_rec.Header()
	assert.Equal(t, "application/json", headers.Get("Content-Type"))

	json_task := Task{}
	decoder := json.NewDecoder(resp_rec.Body)
	if err := decoder.Decode(&json_task); err != nil {
		t.Errorf("Unable to decode JSON: %s", err)
		return
	}

	assert.Equal(t, "processing", json_task.Status)
	assert.Equal(t, "sleeping", json_task.JobType)
	assert.Equal(t, "Running Blender from /opt/myblenderbuild/blender",
		json_task.Commands[0].Settings["message"])

	// Check worker with other job type
	ar = &auth.AuthenticatedRequest{Request: *request, Username: worker_win.Id.Hex()}
	sched.ScheduleTask(resp_rec, ar)

	// Check the response JSON
	assert.Equal(t, 200, resp_rec.Code)
	decoder = json.NewDecoder(resp_rec.Body)
	if err := decoder.Decode(&json_task); err != nil {
		t.Errorf("Unable to decode JSON: %s", err)
		return
	}

	assert.Equal(t, "processing", json_task.Status)
	assert.Equal(t, "testing", json_task.JobType)
	assert.Equal(t, "Running Blender from c:/temp/blender.exe",
		json_task.Commands[0].Settings["message"])

}

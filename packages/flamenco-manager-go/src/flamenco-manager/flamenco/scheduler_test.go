package flamenco

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"time"

	log "github.com/Sirupsen/logrus"
	auth "github.com/abbot/go-http-auth"
	"github.com/stretchr/testify/assert"

	check "gopkg.in/check.v1"
	"gopkg.in/jarcoal/httpmock.v1"
	mgo "gopkg.in/mgo.v2"
)

type SchedulerTestSuite struct {
	worker_lnx Worker
	worker_win Worker

	db       *mgo.Database
	upstream *UpstreamConnection
	sched    *TaskScheduler
}

var _ = check.Suite(&SchedulerTestSuite{})

func parseJson(c *check.C, resp_rec *httptest.ResponseRecorder, expected_status int, parsed interface{}) {
	assert.Equal(c, 200, resp_rec.Code)
	headers := resp_rec.Header()
	assert.Equal(c, "application/json", headers.Get("Content-Type"))

	decoder := json.NewDecoder(resp_rec.Body)
	if err := decoder.Decode(&parsed); err != nil {
		c.Fatalf("Unable to decode JSON: %s", err)
	}
}

func (s *SchedulerTestSuite) SetUpTest(c *check.C) {
	httpmock.Activate()

	config := GetTestConfig()
	session := MongoSession(&config)
	s.db = session.DB("")

	s.upstream = ConnectUpstream(&config, session)
	s.sched = CreateTaskScheduler(&config, s.upstream, session)

	// Store workers in DB, on purpose in the opposite order as the tasks.
	s.worker_lnx = Worker{
		Platform:          "linux",
		SupportedJobTypes: []string{"sleeping"},
	}
	if err := StoreNewWorker(&s.worker_lnx, s.db); err != nil {
		c.Fatal("Unable to insert test worker_lnx", err)
	}
	s.worker_win = Worker{
		Platform:          "windows",
		SupportedJobTypes: []string{"testing"},
	}
	if err := StoreNewWorker(&s.worker_win, s.db); err != nil {
		c.Fatal("Unable to insert test worker_win", err)
	}

}

func (s *SchedulerTestSuite) TearDownTest(c *check.C) {
	log.Info("SchedulerTestSuite tearing down test, dropping database.")
	s.upstream.Close()
	s.db.DropDatabase()
	httpmock.DeactivateAndReset()
}

/**
 * In this test we don't mock the upstream HTTP connection, so it's normal to see
 * errors about failed requests. These are harmless. As a matter of fact, testing
 * in such error conditions is good; task scheduling should keep working.
 */
func (s *SchedulerTestSuite) TestVariableReplacement(t *check.C) {
	// Store task in DB.
	task1 := ConstructTestTask("aaaaaaaaaaaaaaaaaaaaaaaa", "testing")
	if err := s.db.C("flamenco_tasks").Insert(task1); err != nil {
		t.Fatal("Unable to insert test task", err)
	}
	task2 := ConstructTestTask("1aaaaaaaaaaaaaaaaaaaaaaa", "sleeping")
	if err := s.db.C("flamenco_tasks").Insert(task2); err != nil {
		t.Fatal("Unable to insert test task 2", err)
	}

	// Perform HTTP request
	resp_rec := httptest.NewRecorder()
	request, _ := http.NewRequest("GET", "/task", nil)
	ar := &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	s.sched.ScheduleTask(resp_rec, ar)

	// Check the response JSON
	json_task := Task{}
	parseJson(t, resp_rec, 200, &json_task)
	assert.Equal(t, "active", json_task.Status)
	assert.Equal(t, "sleeping", json_task.JobType)
	assert.Equal(t, "Running Blender from /opt/myblenderbuild/blender",
		json_task.Commands[0].Settings["message"])

	// Check worker with other job type
	ar = &auth.AuthenticatedRequest{Request: *request, Username: s.worker_win.Id.Hex()}
	s.sched.ScheduleTask(resp_rec, ar)

	// Check the response JSON
	parseJson(t, resp_rec, 200, &json_task)
	assert.Equal(t, "active", json_task.Status)
	assert.Equal(t, "testing", json_task.JobType)
	assert.Equal(t, "Running Blender from c:/temp/blender.exe",
		json_task.Commands[0].Settings["message"])

}

func (s *SchedulerTestSuite) TestSchedulerOrderByPriority(t *check.C) {
	// Store task in DB.
	task1 := ConstructTestTaskWithPrio("1aaaaaaaaaaaaaaaaaaaaaaa", "sleeping", 50)
	if err := s.db.C("flamenco_tasks").Insert(task1); err != nil {
		t.Fatal("Unable to insert test task1", err)
	}
	task2 := ConstructTestTaskWithPrio("2aaaaaaaaaaaaaaaaaaaaaaa", "sleeping", 100)
	if err := s.db.C("flamenco_tasks").Insert(task2); err != nil {
		t.Fatal("Unable to insert test task 2", err)
	}

	// Perform HTTP request to the scheduler.
	resp_rec := httptest.NewRecorder()
	request, _ := http.NewRequest("GET", "/task", nil)
	ar := &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	s.sched.ScheduleTask(resp_rec, ar)

	// We should have gotten task 2, because it has the highest priority.
	json_task := Task{}
	parseJson(t, resp_rec, 200, &json_task)
	assert.Equal(t, task2.Id.Hex(), json_task.Id.Hex())
}

/**
 * The failure case, where the TaskScheduler cannot reach the Server to check
 * the task for updates, is already implicitly handled in the TestVariableReplacement
 * test case; a Responder for that endpoint isn't registered there, and thus it results
 * in a connection error.
 */
func (s *SchedulerTestSuite) TestSchedulerVerifyUpstreamCanceled(t *check.C) {
	// Store task in DB.
	task1 := ConstructTestTaskWithPrio("1aaaaaaaaaaaaaaaaaaaaaaa", "sleeping", 50)
	if err := s.db.C("flamenco_tasks").Insert(task1); err != nil {
		t.Fatal("Unable to insert test task1", err)
	}
	task2 := ConstructTestTaskWithPrio("2aaaaaaaaaaaaaaaaaaaaaaa", "sleeping", 100)
	if err := s.db.C("flamenco_tasks").Insert(task2); err != nil {
		t.Fatal("Unable to insert test task 2", err)
	}

	timeout := TimeoutAfter(1 * time.Second)
	defer close(timeout)

	// Mock that the task with highest priority was actually canceled on the Server.
	httpmock.RegisterResponder(
		"GET",
		"http://localhost:51234/api/flamenco/tasks/2aaaaaaaaaaaaaaaaaaaaaaa",
		func(req *http.Request) (*http.Response, error) {
			defer func() { timeout <- false }()
			log.Info("GET from manager received on server, sending back updated task.")

			// same task, but with changed status.
			changed_task := task2
			changed_task.Status = "canceled"
			return httpmock.NewJsonResponse(200, &changed_task)
		},
	)

	// Perform HTTP request to the scheduler.
	resp_rec := httptest.NewRecorder()
	request, _ := http.NewRequest("GET", "/task", nil)
	ar := &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	s.sched.ScheduleTask(resp_rec, ar)

	timedout := <-timeout
	assert.False(t, timedout, "HTTP GET to Flamenco Server not performed")

	// Check the response JSON
	json_task := Task{}
	parseJson(t, resp_rec, 200, &json_task)

	// We should have gotten task 1, because task 2 was canceled.
	assert.Equal(t, task1.Id.Hex(), json_task.Id.Hex())

	// In our queue, task 2 should have been canceled, since it was canceled on the server.
	found_task2 := Task{}
	err := s.db.C("flamenco_tasks").FindId(task2.Id).One(&found_task2)
	assert.Equal(t, nil, err)
	assert.Equal(t, "canceled", found_task2.Status)
}

func (s *SchedulerTestSuite) TestSchedulerVerifyUpstreamPrioChange(t *check.C) {
	// Store task in DB.
	task1 := ConstructTestTaskWithPrio("1aaaaaaaaaaaaaaaaaaaaaaa", "sleeping", 50)
	if err := s.db.C("flamenco_tasks").Insert(task1); err != nil {
		t.Fatal("Unable to insert test task1", err)
	}
	task2 := ConstructTestTaskWithPrio("2aaaaaaaaaaaaaaaaaaaaaaa", "sleeping", 100)
	if err := s.db.C("flamenco_tasks").Insert(task2); err != nil {
		t.Fatal("Unable to insert test task 2", err)
	}

	timeout := TimeoutAfter(1 * time.Second)
	defer close(timeout)

	// Mock that the task with highest priority was actually canceled on the Server.
	httpmock.RegisterResponder(
		"GET",
		"http://localhost:51234/api/flamenco/tasks/2aaaaaaaaaaaaaaaaaaaaaaa",
		func(req *http.Request) (*http.Response, error) {
			defer func() { timeout <- false }()
			log.Info("GET from manager received on server, sending back updated task.")

			// same task, but with changed status.
			changed_task := task2
			changed_task.Priority = 5
			return httpmock.NewJsonResponse(200, &changed_task)
		},
	)

	// Perform HTTP request to the scheduler.
	resp_rec := httptest.NewRecorder()
	request, _ := http.NewRequest("GET", "/task", nil)
	ar := &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	s.sched.ScheduleTask(resp_rec, ar)

	timedout := <-timeout
	assert.False(t, timedout, "HTTP GET to Flamenco Server not performed")

	// Check the response JSON
	json_task := Task{}
	parseJson(t, resp_rec, 200, &json_task)

	// We should have gotten task 1, because task 2 was lowered in prio.
	assert.Equal(t, task1.Id.Hex(), json_task.Id.Hex())

	// In our queue, task 2 should have been lowered in prio, and task1 should be active.
	found_task := Task{}
	err := s.db.C("flamenco_tasks").FindId(task2.Id).One(&found_task)
	assert.Equal(t, nil, err)
	assert.Equal(t, "queued", found_task.Status)
	assert.Equal(t, 5, found_task.Priority)

	err = s.db.C("flamenco_tasks").FindId(task1.Id).One(&found_task)
	assert.Equal(t, nil, err)
	assert.Equal(t, "active", found_task.Status)
	assert.Equal(t, 50, found_task.Priority)
}

func (s *SchedulerTestSuite) TestSchedulerVerifyUpstreamDeleted(t *check.C) {
	// Store task in DB.
	task1 := ConstructTestTaskWithPrio("1aaaaaaaaaaaaaaaaaaaaaaa", "sleeping", 50)
	if err := s.db.C("flamenco_tasks").Insert(task1); err != nil {
		t.Fatal("Unable to insert test task1", err)
	}
	task2 := ConstructTestTaskWithPrio("2aaaaaaaaaaaaaaaaaaaaaaa", "sleeping", 100)
	if err := s.db.C("flamenco_tasks").Insert(task2); err != nil {
		t.Fatal("Unable to insert test task 2", err)
	}

	timeout := TimeoutAfter(1 * time.Second)
	defer close(timeout)

	// Mock that the task with highest priority was actually canceled on the Server.
	httpmock.RegisterResponder(
		"GET",
		"http://localhost:51234/api/flamenco/tasks/2aaaaaaaaaaaaaaaaaaaaaaa",
		func(req *http.Request) (*http.Response, error) {
			defer func() { timeout <- false }()
			log.Info("GET from manager received on server, sending back 404.")
			return httpmock.NewStringResponse(404, ""), nil
		},
	)

	// Perform HTTP request to the scheduler.
	resp_rec := httptest.NewRecorder()
	request, _ := http.NewRequest("GET", "/task", nil)
	ar := &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	s.sched.ScheduleTask(resp_rec, ar)

	timedout := <-timeout
	assert.False(t, timedout, "HTTP GET to Flamenco Server not performed")

	// Check the response JSON
	json_task := Task{}
	parseJson(t, resp_rec, 200, &json_task)

	// We should have gotten task 1, because task 2 was deleted.
	assert.Equal(t, task1.Id.Hex(), json_task.Id.Hex())

	// In our queue, task 2 should have been canceled, and task1 should be active.
	found_task := Task{}
	err := s.db.C("flamenco_tasks").FindId(task2.Id).One(&found_task)
	assert.Equal(t, nil, err)
	assert.Equal(t, "canceled", found_task.Status)
	assert.Equal(t, 100, found_task.Priority)

	err = s.db.C("flamenco_tasks").FindId(task1.Id).One(&found_task)
	assert.Equal(t, nil, err)
	assert.Equal(t, "active", found_task.Status)
	assert.Equal(t, 50, found_task.Priority)
}

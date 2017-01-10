package flamenco

import (
	"fmt"
	"net/http"
	"net/http/httptest"

	auth "github.com/abbot/go-http-auth"
	"github.com/stretchr/testify/assert"
	check "gopkg.in/check.v1"
	"gopkg.in/mgo.v2/bson"
)

func (s *SchedulerTestSuite) TestWorkerMayRun(t *check.C) {
	// Store task in DB.
	task := ConstructTestTask("aaaaaaaaaaaaaaaaaaaaaaaa", "sleeping")
	if err := s.db.C("flamenco_tasks").Insert(task); err != nil {
		t.Fatal("Unable to insert test task", err)
	}

	// Make sure the scheduler gives us this task.
	resp_rec := httptest.NewRecorder()
	request, _ := http.NewRequest("GET", "/task", nil)
	ar := &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	s.sched.ScheduleTask(resp_rec, ar)

	// Right after obtaining the task, we should be allowed to keep running it.
	resp_rec = httptest.NewRecorder()
	request, _ = http.NewRequest("GET", fmt.Sprintf("/may-i-run/%s", task.Id.Hex()), nil)
	ar = &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	WorkerMayRunTask(resp_rec, ar, s.db, task.Id)

	resp := MayKeepRunningResponse{}
	parseJson(t, resp_rec, 200, &resp)
	assert.Equal(t, "", resp.Reason)
	assert.Equal(t, true, resp.MayKeepRunning)

	// If we now change the task status to "canceled", the worker should be denied.
	assert.Nil(t, s.db.C("flamenco_tasks").UpdateId(task.Id, bson.M{"$set": bson.M{"status": "canceled"}}))
	resp_rec = httptest.NewRecorder()
	request, _ = http.NewRequest("GET", fmt.Sprintf("/may-i-run/%s", task.Id.Hex()), nil)
	ar = &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	WorkerMayRunTask(resp_rec, ar, s.db, task.Id)

	resp = MayKeepRunningResponse{}
	parseJson(t, resp_rec, 200, &resp)
	assert.Equal(t, false, resp.MayKeepRunning)

	// Changing status back to "active", but assigning to another worker
	assert.Nil(t, s.db.C("flamenco_tasks").UpdateId(task.Id, bson.M{"$set": bson.M{
		"status":    "active",
		"worker_id": s.worker_win.Id,
	}}))
	resp_rec = httptest.NewRecorder()
	request, _ = http.NewRequest("GET", fmt.Sprintf("/may-i-run/%s", task.Id.Hex()), nil)
	ar = &auth.AuthenticatedRequest{Request: *request, Username: s.worker_lnx.Id.Hex()}
	WorkerMayRunTask(resp_rec, ar, s.db, task.Id)

	resp = MayKeepRunningResponse{}
	parseJson(t, resp_rec, 200, &resp)
	assert.Equal(t, false, resp.MayKeepRunning)
}

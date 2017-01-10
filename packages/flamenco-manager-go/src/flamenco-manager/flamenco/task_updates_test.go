package flamenco

import (
	"log"
	"net/http"
	"time"

	"github.com/stretchr/testify/assert"

	check "gopkg.in/check.v1"
	"gopkg.in/jarcoal/httpmock.v1"
	mgo "gopkg.in/mgo.v2"
	"gopkg.in/mgo.v2/bson"
)

type TaskUpdatesTestSuite struct {
	config   Conf
	session  *mgo.Session
	db       *mgo.Database
	upstream *UpstreamConnection
}

var _ = check.Suite(&TaskUpdatesTestSuite{})

func (s *TaskUpdatesTestSuite) SetUpTest(c *check.C) {
	httpmock.Activate()

	s.config = GetTestConfig()
	s.session = MongoSession(&s.config)
	s.db = s.session.DB("")
	s.upstream = ConnectUpstream(&s.config, s.session)
}

func (s *TaskUpdatesTestSuite) TearDownTest(c *check.C) {
	log.Println("SchedulerTestSuite tearing down test, dropping database.")
	s.upstream.Close()
	s.db.DropDatabase()
	httpmock.DeactivateAndReset()
}

func (s *TaskUpdatesTestSuite) TestCancelRunningTasks(t *check.C) {
	tasks_coll := s.db.C("flamenco_tasks")

	task1 := ConstructTestTask("1aaaaaaaaaaaaaaaaaaaaaaa", "testing")
	if err := tasks_coll.Insert(task1); err != nil {
		t.Fatal("Unable to insert test task", err)
	}
	task2 := ConstructTestTask("2aaaaaaaaaaaaaaaaaaaaaaa", "sleeping")
	if err := tasks_coll.Insert(task2); err != nil {
		t.Fatal("Unable to insert test task 2", err)
	}

	timeout := TimeoutAfter(1 * time.Second)

	// Mock that the task with highest priority was actually canceled on the Server.
	httpmock.RegisterResponder(
		"POST",
		"http://localhost:51234/api/flamenco/managers/5852bc5198377351f95d103e/task-update-batch",
		func(req *http.Request) (*http.Response, error) {
			defer func() { timeout <- false }()
			log.Println("POST from manager received on server, sending back TaskUpdateResponse.")

			resp := TaskUpdateResponse{
				CancelTasksIds: []bson.ObjectId{task2.Id},
			}
			return httpmock.NewJsonResponse(200, &resp)
		},
	)

	// Set up some decent timeouts so we don't have to wait forevah.
	s.config.TaskUpdatePushMaxInterval = 30 * time.Second
	s.config.TaskUpdatePushMaxCount = 4000
	s.config.CancelTaskFetchInterval = 300 * time.Millisecond

	tup := CreateTaskUpdatePusher(&s.config, s.upstream, s.session)
	defer tup.Close()

	go tup.Go()

	timedout := <-timeout
	assert.False(t, timedout, "HTTP POST to Flamenco Server not performed")

	// Check that one task was canceled and the other was not.
	task_db := Task{}
	assert.Nil(t, tasks_coll.FindId(task1.Id).One(&task_db))
	assert.Equal(t, "queued", task_db.Status)
	assert.Nil(t, tasks_coll.FindId(task2.Id).One(&task_db))
	assert.Equal(t, "cancel-requested", task_db.Status)
}

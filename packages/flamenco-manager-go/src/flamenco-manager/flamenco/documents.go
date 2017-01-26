package flamenco

import (
	"time"

	"gopkg.in/mgo.v2/bson"
)

type Command struct {
	Name     string `bson:"name" json:"name"`
	Settings bson.M `bson:"settings" json:"settings"`
}

type Task struct {
	Id       bson.ObjectId   `bson:"_id,omitempty" json:"_id,omitempty"`
	Etag     string          `bson:"_etag,omitempty" json:"_etag,omitempty"`
	Job      bson.ObjectId   `bson:"job,omitempty" json:"job"`
	Manager  bson.ObjectId   `bson:"manager,omitempty" json:"manager"`
	Project  bson.ObjectId   `bson:"project,omitempty" json:"project"`
	User     bson.ObjectId   `bson:"user,omitempty" json:"user"`
	Name     string          `bson:"name" json:"name"`
	Status   string          `bson:"status" json:"status"`
	Priority int             `bson:"priority" json:"priority"`
	JobType  string          `bson:"job_type" json:"job_type"`
	Commands []Command       `bson:"commands" json:"commands"`
	Log      string          `bson:"log,omitempty" json:"log,omitempty"`
	Activity string          `bson:"activity,omitempty" json:"activity,omitempty"`
	Parents  []bson.ObjectId `bson:"parents,omitempty" json:"parents,omitempty"`
	Worker   string          `bson:"worker,omitempty" json:"worker,omitempty"`

	// Internal bookkeeping
	WorkerId       *bson.ObjectId `bson:"worker_id,omitempty" json:"-"`
	LastWorkerPing *time.Time     `bson:"last_worker_ping,omitempty" json:"-"`
}

// Dependency graph response from Server.
type ScheduledTasks struct {
	Depsgraph []Task `json:"depsgraph"`
}

// Both sent from Worker to Manager, as well as from Manager to Server.
type TaskUpdate struct {
	Id                        bson.ObjectId `bson:"_id" json:"_id"`
	TaskId                    bson.ObjectId `bson:"task_id" json:"task_id,omitempty"`
	TaskStatus                string        `bson:"task_status,omitempty" json:"task_status,omitempty"`
	ReceivedOnManager         time.Time     `bson:"received_on_manager" json:"received_on_manager"`
	Activity                  string        `bson:"activity,omitempty" json:"activity,omitempty"`
	TaskProgressPercentage    int           `bson:"task_progress_percentage" json:"task_progress_percentage"`
	CurrentCommandIdx         int           `bson:"current_command_idx" json:"current_command_idx"`
	CommandProgressPercentage int           `bson:"command_progress_percentage" json:"command_progress_percentage"`
	Log                       string        `bson:"log,omitempty" json:"log,omitempty"`
	Worker                    string        `bson:"worker" json:"worker"`
}

// Received from Server.
type TaskUpdateResponse struct {
	ModifiedCount    int             `json:"modified_count"`
	HandledUpdateIds []bson.ObjectId `json:"handled_update_ids,omitempty"`
	CancelTasksIds   []bson.ObjectId `json:"cancel_task_ids,omitempty"`
}

type WorkerRegistration struct {
	Secret            string   `json:"secret"`
	Platform          string   `json:"platform"`
	SupportedJobTypes []string `json:"supported_job_types"`
	Nickname          string   `json:"nickname"`
}

type Worker struct {
	Id                bson.ObjectId `bson:"_id,omitempty" json:"_id,omitempty"`
	Secret            string        `bson:"-" json:"-"`
	HashedSecret      []byte        `bson:"hashed_secret" json:"-"`
	Nickname          string        `bson:"nickname" json:"nickname"`
	Address           string        `bson:"address" json:"address"`
	Status            string        `bson:"status" json:"status"`
	Platform          string        `bson:"platform" json:"platform"`
	CurrentTask       bson.ObjectId `bson:"current_task,omitempty" json:"current_task,omitempty"`
	TimeCost          int           `bson:"time_cost" json:"time_cost"`
	LastActivity      *time.Time    `bson:"last_activity,omitempty" json:"last_activity,omitempty"`
	SupportedJobTypes []string      `bson:"supported_job_types" json:"supported_job_types"`
}

/**
 * Notification sent to upstream Flamenco Server upon startup. This is a combination
 * of settings (see settings.go) and information from the database.
 */
type StartupNotification struct {
	// Settings
	ManagerUrl         string                       `json:"manager_url"`
	VariablesByVarname map[string]map[string]string `json:"variables"`

	// From our local database
	NumberOfWorkers int `json:"nr_of_workers"`
}

type MayKeepRunningResponse struct {
	MayKeepRunning bool   `json:"may_keep_running"`
	Reason         string `json:"reason,omitempty"`
}

// Settings we want to be able to update from within Flamenco Manager itself,
// so those are stored in MongoDB itself.
type SettingsInMongo struct {
	DepsgraphLastModified *time.Time `bson:"depsgraph_last_modified"`
}

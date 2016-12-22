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
	Etag     string          `bson:"-" json:"_etag,omitempty"`
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
}

type TaskUpdate struct {
	TaskId                    bson.ObjectId `bson:"task_id" json:"-"`
	TaskStatus                string        `bson:"task_status,omitempty" json:"task_status,omitempty"`
	ReceivedOnManager         time.Time     `bson:"received_on_manager" json:"-"`
	Activity                  string        `bson:"activity,omitempty" json:"activity,omitempty"`
	TaskProgressPercentage    int           `bson:"task_progress_percentage,omitempty" json:"task_progress_percentage,omitempty"`
	CurrentCommandIdx         int           `bson:"current_command_idx,omitempty" json:"current_command_idx,omitempty"`
	CommandProgressPercentage int           `bson:"command_progress_percentage,omitempty" json:"command_progress_percentage,omitempty"`
	Log                       string        `bson:"log,omitempty" json:"log,omitempty"`
}

type WorkerRegistration struct {
	Secret            string   `json:"secret"`
	Platform          string   `bson:"platform" json:"platform"`
	SupportedJobTypes []string `json:"supported_job_types"`
}

type Worker struct {
	Id                bson.ObjectId `bson:"_id,omitempty" json:"_id,omitempty"`
	Secret            string        `bson:"-" json:"-"`
	HashedSecret      []byte        `bson:"hashed_secret" json:"-"`
	Address           string        `bson:"address" json:"address"`
	Status            string        `bson:"status" json:"status"`
	Platform          string        `bson:"platform" json:"platform"`
	CurrentTask       bson.ObjectId `bson:"current_task,omitempty" json:"current_task,omitempty"`
	TimeCost          int           `bson:"time_cost" json:"time_cost"`
	LastActivity      time.Time     `bson:"last_activity" json:"last_activity"`
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

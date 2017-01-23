package flamenco

import (
	"io/ioutil"
	"net/url"
	"os"
	"path"
	"time"

	log "github.com/Sirupsen/logrus"

	"gopkg.in/yaml.v2"
)

type Conf struct {
	DatabaseUrl   string   `yaml:"database_url"`
	Listen        string   `yaml:"listen"`
	OwnUrl        string   `yaml:"own_url"`
	FlamencoStr   string   `yaml:"flamenco"`
	Flamenco      *url.URL `yaml:"-"`
	ManagerId     string   `yaml:"manager_id"`
	ManagerSecret string   `yaml:"manager_secret"`
	TLSKey        string   `yaml:"tlskey"`
	TLSCert       string   `yaml:"tlscert"`

	DownloadTaskSleep_ int           `yaml:"download_task_sleep_seconds"`
	DownloadTaskSleep  time.Duration `yaml:"-"`

	/* The number of seconds between rechecks when there are no more tasks for workers.
	 * If set to 0, will not throttle at all.
	 * If set to -1, will never check when a worker asks for a task (so only every
	 * download_task_sleep_seconds seconds). */
	DownloadTaskRecheckThrottle_ int           `yaml:"download_task_recheck_throttle_seconds"`
	DownloadTaskRecheckThrottle  time.Duration `yaml:"-"`

	/* Variables, stored differently in YAML and these settings.
	 * Variables:             variable name -> platform -> value
	 * VariablesPerPlatform:  platform -> variable name -> value
	 */
	VariablesByVarname  map[string]map[string]string `yaml:"variables"`
	VariablesByPlatform map[string]map[string]string `yaml:"-"`

	TaskUpdatePushMaxInterval_ int           `yaml:"task_update_push_max_interval_seconds"`
	TaskUpdatePushMaxInterval  time.Duration `yaml:"-"`
	TaskUpdatePushMaxCount     int           `yaml:"task_update_push_max_count"`
	CancelTaskFetchInterval_   int           `yaml:"cancel_task_fetch_max_interval_seconds"`
	CancelTaskFetchInterval    time.Duration `yaml:"-"`

	ActiveTaskTimeoutInterval_ int           `yaml:"active_task_timeout_interval_seconds"`
	ActiveTaskTimeoutInterval  time.Duration `yaml:"-"`
}

func GetConf() Conf {
	yamlFile, err := ioutil.ReadFile("flamenco-manager.yaml")
	if err != nil {
		log.Fatalf("GetConf err   #%v ", err)
	}

	// Construct the struct with some more or less sensible defaults.
	c := Conf{
		DownloadTaskSleep_:           300,
		DownloadTaskRecheckThrottle_: 10,
		TaskUpdatePushMaxInterval_:   30,
		TaskUpdatePushMaxCount:       10,
		CancelTaskFetchInterval_:     10,
		ActiveTaskTimeoutInterval_:   60,
	}
	err = yaml.Unmarshal(yamlFile, &c)
	if err != nil {
		log.Fatalf("Unmarshal: %v", err)
	}

	// Parse URL
	c.Flamenco, err = url.Parse(c.FlamencoStr)
	if err != nil {
		log.Fatalf("Bad Flamenco URL: %v", err)
	}

	// Transpose the variables matrix.
	c.VariablesByPlatform = make(map[string]map[string]string)
	for varname, perplatform := range c.VariablesByVarname {
		for platform, varvalue := range perplatform {
			if c.VariablesByPlatform[platform] == nil {
				c.VariablesByPlatform[platform] = make(map[string]string)
			}
			c.VariablesByPlatform[platform][varname] = varvalue
		}
	}

	// Convert durations. TODO: use actual unmarshaling code for this.
	c.DownloadTaskSleep = time.Duration(c.DownloadTaskSleep_) * time.Second
	c.DownloadTaskRecheckThrottle = time.Duration(c.DownloadTaskRecheckThrottle_) * time.Second
	c.TaskUpdatePushMaxInterval = time.Duration(c.TaskUpdatePushMaxInterval_) * time.Second
	c.CancelTaskFetchInterval = time.Duration(c.CancelTaskFetchInterval_) * time.Second
	c.ActiveTaskTimeoutInterval = time.Duration(c.ActiveTaskTimeoutInterval_) * time.Second

	return c
}

/**
 * Configuration for unit tests.
 */
func GetTestConfig() Conf {
	cwd, err := os.Getwd()
	if err != nil {
		log.Fatal(err)
		os.Exit(1)
	}

	if path.Base(cwd) != "flamenco" {
		log.Panic("Expecting tests to run from flamenco package dir.")
		os.Exit(2)
	}

	return GetConf()
}

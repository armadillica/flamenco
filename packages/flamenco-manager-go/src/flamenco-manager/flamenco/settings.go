package flamenco

import (
	"io/ioutil"
	"log"
	"net/url"
	"os"
	"path"

	"gopkg.in/yaml.v2"
)

type Conf struct {
	DatabaseUrl       string   `yaml:"database_url"`
	Listen            string   `yaml:"listen"`
	OwnUrl            string   `yaml:"own_url"`
	FlamencoStr       string   `yaml:"flamenco"`
	Flamenco          *url.URL `yaml:"-"`
	ManagerId         string   `yaml:"manager_id"`
	ManagerSecret     string   `yaml:"manager_secret"`
	TLSKey            string   `yaml:"tlskey"`
	TLSCert           string   `yaml:"tlscert"`
	DownloadTaskSleep int64    `yaml:"download_task_sleep_seconds"`

	/* The number of seconds between rechecks when there are no more tasks for workers.
	 * If set to 0, will not throttle at all.
	 * If set to -1, will never check when a worker asks for a task (so only every
	 * download_task_sleep_seconds seconds). */
	DownloadTaskRecheckThrottle int64 `yaml:"download_task_recheck_throttle_seconds"`

	/* Variables, stored differently in YAML and these settings.
	 * Variables:             variable name -> platform -> value
	 * VariablesPerPlatform:  platform -> variable name -> value
	 */
	VariablesByVarname  map[string]map[string]string `yaml:"variables"`
	VariablesByPlatform map[string]map[string]string `yaml:"-"`
}

func GetConf() Conf {
	yamlFile, err := ioutil.ReadFile("flamenco-manager.yaml")
	if err != nil {
		log.Printf("GetConf err   #%v ", err)
	}
	c := Conf{}
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
		log.Fatal("Expecting tests to run from flamenco package dir.")
		os.Exit(2)
	}

	return GetConf()
}

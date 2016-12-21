package flamenco

import (
	"fmt"
	"reflect"
	"strings"
)

var stringType reflect.Type = reflect.TypeOf("somestring")

/**
 * Variable replacement for tasks.
 */
func ReplaceVariables(config *Conf, task *Task, worker *Worker) {
	varmap := config.VariablesByPlatform[worker.Platform]

	for _, cmd := range task.Commands {
		for key, value := range cmd.Settings {
			// Only do replacement on string types
			if reflect.TypeOf(value) != stringType {
				continue
			}

			strvalue := reflect.ValueOf(value).String()
			for varname, varvalue := range varmap {
				placeholder := fmt.Sprintf("{%s}", varname)
				strvalue = strings.Replace(strvalue, placeholder, varvalue, -1)
			}

			cmd.Settings[key] = strvalue
		}
	}
}

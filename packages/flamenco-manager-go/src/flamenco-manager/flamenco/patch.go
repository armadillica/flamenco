package flamenco

import (
	"bytes"
	"encoding/json"
	"io/ioutil"
	"log"
	"net/http"
	"net/url"
)

/**
 * Sends a PATCH command to upstream Flamenco Server.
 */
func SendPatch(config *Conf, relative_url *url.URL, patch interface{}) error {
	patch_url := config.Flamenco.ResolveReference(relative_url)
	log.Printf("Sending patch %s to upstream Flamenco %s\n", patch, patch_url)

	task_bytes, err := json.Marshal(patch)
	if err != nil {
		log.Printf("ERROR: Unable to convert patch %s to JSON\n", patch)
		return err
	}
	req, err := http.NewRequest("PATCH", patch_url.String(), bytes.NewBuffer(task_bytes))
	req.Header.Add("Content-Type", "application/json")
	req.SetBasicAuth(config.ManagerSecret, "")

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		// log.Printf("ERROR: Unable to PATCH to %s: %s\n", patch_url, err)
		return err
	}

	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		log.Printf("ERROR: Error %d PATCHting to %s: %s\n",
			resp.StatusCode, patch_url, err)
		return err
	}

	if resp.StatusCode >= 300 {
		log.Printf("ERROR: Error %d PATCHting to %s: %s\n",
			resp.StatusCode, patch_url, body)
		return err
	}

	log.Printf("Done sending PATCH to upstream Flamenco\n")
	return nil
}

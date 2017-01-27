package flamenco

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"io/ioutil"
	"net/http"
	"net/url"

	log "github.com/Sirupsen/logrus"
)

// For timestamp parsing
const IsoFormat = "2006-01-02T15:04:05-0700"

/**
 * Decodes JSON and writes a Bad Request status if it fails.
 */
func DecodeJson(w http.ResponseWriter, r io.Reader, document interface{},
	logprefix string) error {
	dec := json.NewDecoder(r)

	if err := dec.Decode(document); err != nil {
		log.Warningf("%s Unable to decode JSON: %s", logprefix, err)
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "Unable to decode JSON: %s\n", err)
		return err
	}

	return nil
}

/**
 * Sends a JSON document to some URL via HTTP.
 * :param tweakrequest: can be used to tweak the request before sending it, for
 *    example by adding authentication headers. May be nil.
 * :param responsehandler: is called when a non-error response has been read.
 *    May be nil.
 */
func SendJson(logprefix, method string, url *url.URL,
	payload interface{},
	tweakrequest func(req *http.Request),
	responsehandler func(resp *http.Response, body []byte) error,
) error {
	payload_bytes, err := json.Marshal(payload)
	if err != nil {
		log.Errorf("%s: Unable to marshal JSON: %s", logprefix, err)
		return err
	}

	// TODO Sybren: enable GZip compression.
	req, err := http.NewRequest("POST", url.String(), bytes.NewBuffer(payload_bytes))
	if err != nil {
		log.Errorf("%s: Unable to create request: %s", logprefix, err)
		return err
	}
	req.Header.Add("Content-Type", "application/json")
	if tweakrequest != nil {
		tweakrequest(req)
	}

	client := &http.Client{}
	resp, err := client.Do(req)
	if err != nil {
		log.Warningf("%s: Unable to POST to %s: %s", logprefix, url, err)
		return err
	}

	body, err := ioutil.ReadAll(resp.Body)
	defer resp.Body.Close()
	if err != nil {
		log.Warningf("%s: Error %d POSTing to %s: %s",
			logprefix, resp.StatusCode, url, err)
		return err
	}

	if resp.StatusCode >= 300 {
		suffix := ""
		if resp.StatusCode != 404 {
			suffix = fmt.Sprintf("\n    body:\n%s", body)
		}
		log.Warningf("%s: Error %d POSTing to %s%s",
			logprefix, resp.StatusCode, url, suffix)
		return fmt.Errorf("%s: Error %d POSTing to %s", logprefix, resp.StatusCode, url)
	}

	if responsehandler != nil {
		return responsehandler(resp, body)
	}

	return nil
}

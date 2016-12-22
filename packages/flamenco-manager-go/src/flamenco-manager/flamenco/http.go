package flamenco

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
)

/**
 * Decodes JSON and writes a Bad Request status if it fails.
 */
func DecodeJson(w http.ResponseWriter, r io.Reader, document interface{},
	logprefix string) error {
	dec := json.NewDecoder(r)

	if err := dec.Decode(document); err != nil {
		log.Printf("%s Unable to decode JSON: %s", logprefix, err)
		w.WriteHeader(http.StatusBadRequest)
		fmt.Fprintf(w, "Unable to decode JSON: %s\n", err)
		return err
	}

	return nil
}

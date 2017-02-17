package flamenco

import (
	"sync"

	log "github.com/Sirupsen/logrus"
)

// closable offers a way to cleanly shut down a running goroutine.
type closable struct {
	doneChan chan struct{}
	doneWg   *sync.WaitGroup
}

// makeClosable constructs a new closable struct
func makeClosable() closable {
	return closable{make(chan struct{}), new(sync.WaitGroup)}
}

// closableAdd(delta) should be combined with 'delta' calls to closableDone()
func (closable *closable) closableAdd(delta int) bool {
	log.Debugf("Closable: doneWg.Add(%d) ok", delta)
	closable.doneWg.Add(delta)
	return true
}

// closableDone marks one "thing" as "done"
func (closable *closable) closableDone() {
	log.Debugf("Closable: doneWg.Done() ok")
	closable.doneWg.Done()
}

// closableCloseAndWait marks the goroutine as "done",
// and waits for all things added with closableAdd() to be "done" too.
func (closable *closable) closableCloseAndWait() {
	close(closable.doneChan)
	log.Debugf("Closable: waiting for shutdown to finish.")
	closable.doneWg.Wait()
}

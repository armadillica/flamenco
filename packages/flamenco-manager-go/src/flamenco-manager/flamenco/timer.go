package flamenco

import (
	"time"

	log "github.com/Sirupsen/logrus"
)

type TimerPing struct{}

/**
 * Generic timer for periodic signals.
 *
 * :param sleep_first: if true: sleep first, then ping. If false: ping first, then sleep.
 */
func Timer(name string, sleep_duration time.Duration, sleep_first bool, closable *closable) <-chan TimerPing {
	timer_chan := make(chan TimerPing, 1) // don't let the timer block

	go func() {
		if !closable.closableAdd(1) {
			log.Infof("Timer '%s' goroutine shutting down.", name)
			return
		}
		defer closable.closableDone()
		defer close(timer_chan)

		last_timer := time.Time{}
		if sleep_first {
			last_timer = time.Now()
		}

		for {
			select {
			case <-closable.doneChan:
				log.Infof("Timer '%s' goroutine shutting down.", name)
				return
			default:
				// Only sleep a little bit, so that we can check 'done' quite often.
				time.Sleep(50 * time.Millisecond)
			}

			now := time.Now()
			if now.Sub(last_timer) > sleep_duration {
				// Timeout occurred
				last_timer = now
				timer_chan <- TimerPing{}
			}
		}
	}()

	return timer_chan
}

/**
 * Sleep that can be killed by closing the "done_chan" channel.
 *
 * :returns: "ok", so true when the sleep stopped normally, and false if it was killed.
 */
func KillableSleep(name string, sleep_duration time.Duration, closable *closable) bool {

	if !closable.closableAdd(1) {
		return false
	}
	defer closable.closableDone()
	defer log.Infof("Sleep '%s' goroutine is shut down.", name)

	sleep_start := time.Now()
	for {
		select {
		case <-closable.doneChan:
			log.Infof("Sleep '%s' goroutine shutting down.", name)
			return false
		default:
			// Only sleep a little bit, so that we can check 'done' quite often.
			time.Sleep(50 * time.Millisecond)
		}

		now := time.Now()
		if now.Sub(sleep_start) > sleep_duration {
			// Timeout occurred
			break
		}
	}

	return true
}

func UtcNow() *time.Time {
	now := time.Now().UTC()
	return &now
}

/* TimeoutAfter: Sends a 'true' to the channel after the given timeout.
 * Send a 'false' to the channel yourself if you want to notify the receiver that
 * a timeout didn't happen.
 *
 * The channel is buffered with size 2, so both your 'false' and this routine's 'true'
 * write won't block.
 */
func TimeoutAfter(duration time.Duration) chan bool {
	timeout := make(chan bool, 2)

	go func() {
		time.Sleep(duration)
		defer func() {
			// Recover from a panic. This panic can happen when the caller closed the
			// channel while we were sleeping.
			recover()
		}()
		timeout <- true
	}()

	return timeout
}

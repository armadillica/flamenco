#!/bin/bash
# flamenco-worker initial script starter

: ${FLAMENCO_WORKER:?"Need to set FLAMENCO_WORKER"}
: ${FLAMENCO_VENV:?"Need to set FLAMENCO_VENV"}

start() {
    (
        exec >/dev/null 2>&1
        source "$FLAMENCO_VENV"
        python2.7 "$FLAMENCO_WORKER" runserver &
    )
    echo "Flamenco-Worker started"
}

stop() {
    pid=`pgrep -f "$FLAMENCO_WORKER"`
    if [ $pid ]; then
       echo "Killing worker application"
       kill -n 9 $pid
    else
       echo "No worker application found"
    fi

    # TODO currently this is hardcoded to look for a "farm" value in the
    # process. This is not ideal and we should try to shutdown any task
    # run by the worker in a clean way (possibly using a curl command)
    pid_blender=`pgrep -f "farm"`
    if [ $pid_blender ]; then
       echo "Killing blender"
       kill -n 9 $pid_blender
    else
       echo "No blender farm instance found"
    fi

    sleep 2
    echo "Flamenco-Worker killed"
}

case "$1" in
  start)
    start
    ;;
  stop)
    stop   
    ;;
  restart)
    stop
    start
    ;;
  *)
    echo "Usage: /etc/init.d/flamenco-worker {start|stop|restart}"
    exit 1
esac
exit 0

# Flamenco Manager

This is the Flamenco Manager implementation in Go.

## Starting development

`$FM` denotes the directory containing a checkout of Flamenco Manager, that is, the
absolute path of this `flamenco-manager-go` directory.

1. `export GOPATH=$FM`
2. `cd $FM/src/flamenco-manager`
3. Download all dependencies with `go get`
4. Download Flamenco test dependencies with `go get -t ./flamenco`
5. Run the unittests with `go test ./flamenco`
6. Build your first Flamenco Manager with `go build`; this will create an executable
   `flamenco-manager` in `$FM/src/flamenco-manager`


## Known issues & limitations

1. The downloading of tasks doesn't consider job types. This means that workers can be starved
   waiting for tasks, when there are 1000nds of tasks and workers of type X and only a relatively
   low number of workers and tasks of type Y.


## TO DO

1. Heartbeat receiver from workers.
2. Remove address & status from worker registration payload.
3. Way for Flamenco Server to get an overview of Workers, and set their status.

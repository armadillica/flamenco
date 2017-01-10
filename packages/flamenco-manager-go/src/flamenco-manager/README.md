

## Testing

To run all unit tests, run `go test ./flamenco -v`. To run a specific GoCheck test, run
`go test ./flamenco -v --run TestWithGocheck -check.f SchedulerTestSuite.TestVariableReplacement`
where the argument to `--run` determines which suite to run, and `-check.f` determines the
exact test function of that suite. Once all tests have been moved over to use GoCheck, the
`--run` parameter will probably not be needed any more.

## MISSING FEATURES

- Task queue cleanup. At the moment tasks are stored in the queue forever, since that makes
  it possible to notice a task was canceled while a worker was running it. Eventually such
  tasks should be cleaned up, though.

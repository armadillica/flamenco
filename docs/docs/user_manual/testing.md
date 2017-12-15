# Testing Flamenco Workers

**Requires Flamenco Manager and Worker version 2.1 or newer.**

Flamenco Manager and Worker support a special test mode. In this test mode it is possible to test
a new worker before allowing it to join the render farm and execute actual render jobs.

To enable test mode, run the worker with `flamenco-worker --test`. You can also add `--single`, and
the worker will shut down automatically after running a single test task.

When a worker is in testing mode, you can click on the camera icon in Flamenco Manager to send it a
test task to render a blend file. This blend file requires Blender with Cycles.

**NOTE:** these test tasks are local to your Manager and Workers. Information about these tasks are
not sent to Flamenco Server.


## Configuring Flamenco Manager for test mode

Test Mode requires Flamenco Manager to know a bit about your infrastructure. It needs to copy a
blend file to the shared storage so that the worker can read it. Furthermore, it needs to create the
render output directory. These settings should be set in `flamenco-manager.yaml`:


    test_tasks:
        test_blender_render:
            job_storage: '{render}/_flamenco/tests/jobs'
            render_output: '{render}/_flamenco/tests/renders'

`job_storage` indicates the location where the blend file will be placed for the Worker to pick up.
`render_output` indicates the location where the Worker will save the rendered frame.

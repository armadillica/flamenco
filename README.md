# Flamenco Server

This is the Flamenco Server component, implemented as a Pillar extension.

## Development Setup

In order to get Flamenco up and running, we need to follow these steps:

- add Flamenco as Pillar extension to our project
- create a Manager doc
- give a user 'admin' rights for Flamenco (this is temporary)
- give setup a project to use Flamenco

Add Flamenco to your Pillar application as an extension (docs will be available in the Pillar 
documentaiton). At this point we can proceed with the setup of our first manager.

```
python manage.py flamenco create_manager flm-manager@example.com local-manager 'Local manager'
```

The required params are: 
- `flm-manager@example.com` is a new Pillar service account that gets associated with the
new manager created
- `local-manager` is the name of the manager
- `'Local manager` is a description of the manager

Once the manager doc is created, we note down the following info:

- `_id` in the new manager doc
- the *Access Token*

We will use these values in the `flamenco-manager.yaml` config file for the Manager.

Next, we allow a user to interact with a Flamenco project:

```
python manage.py make_admin user@example.com
```

where `user@example.com` is an existing user.

Finally, we set up a project to be used with Flamenco:

```
python manage.py setup_for_flamenco project-url
```

At this point we can run our server and access Flamenco on the `/flamenco` endpoint.

## TODO

- When a certain percentage of a job's tasks have failed, cancel the remaining
  tasks and only then mark the job as failed.
- Handle parent relations between tasks (scheduling, canceling, failing etc.)

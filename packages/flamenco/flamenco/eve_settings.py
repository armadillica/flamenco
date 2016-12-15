
managers_schema = {
    'name': {
        'type': 'string',
        'required': True,
    },
    # Short description of the manager
    'description': {
        'type': 'string',
    },
    # Used in the interface, should be a web address for a picture or logo
    # representing the manager
    'picture': {
        'type': 'string',
    },
    # Full web address of the host. Use for internal queries about status of
    # workers or other operations.
    'url': {
        'type': 'string',
    },
    # The jobs supported by the manager. This means that the manager has a task
    # compiler capable of handling the tasks provided by the server so that
    # the workers can understand them. Both server and manager need to agree
    # on how a job type looks like (in terms of tasks).
    'job_types': {
        'type': 'dict',
        # TODO: will be renamed to 'keyschema' in Cerberus 1.0
        'propertyschema': {  # name of the job type
            'type': 'string',
        },
        'valueschema': {  # configuration of the job type
            'type': 'dict',
            'schema': {
                'vars': {
                    'type': 'dict',
                    # TODO: will be renamed to 'keyschema' in Cerberus 1.0
                    'propertyschema': {  # name of the variable
                        'type': 'string',
                    },
                    'valueschema': {  # variable values for different platforms.
                        'type': 'dict',
                        'schema': {
                            'linux': {'type': 'string'},
                            'darwin': {'type': 'string'},
                            'win': {'type': 'string'},
                        }
                    }
                },
                # This is used to dynamically generate the interface form for
                # submitting a new job.
                'settings_schema': {
                    'type': 'dict',
                }
            }
        }
    },
    # TODO: add user so that we can authenticate the manager itself. The user
    # will be of type 'service', 'flamenco_manager'. The user will be part of
    # a group together with the users of the project it's used it. A sparate
    # permission system will manage access to GET, PUT, DELETE or PATCH
}

jobs_schema = {
    'name': {
        'type': 'string',
        'required': True,
    },
    # Defines how we are going to parse the settings field, in order to generate
    # the tasks list.
    'job_type': {
        'type': 'string',
        'required': True,
    },
    # Remarks about the settings, the author or the system
    'description': {
        'type': 'string',
    },
    'project': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'projects',
            'field': '_id',
            'embeddable': True
        },
    },
    'user': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'users',
            'field': '_id',
            'embeddable': True
        },
    },
    # We currently say that a job, and all its tasks, will be assigned to one
    # manager only. If one day we want to allow multiple managers to handle a
    # job we can convert this to a list.
    'manager': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'flamenco_managers',
            'field': '_id',
            'embeddable': True
        },
    },
    'status': {
        'type': 'string',
        'allowed': [
            'completed',
            'active',
            'canceled',
            'queued',
            'failed'],
        'default': 'queued'
    },
    # This number could be also be a float between 0 and 1.
    'priority': {
        'type': 'integer',
        'min': 1,
        'max': 100,
        'default': 50
    },
    # Embedded summary of the status of all tasks of a job. Used when listing
    # all jobs via a graphical interface.
    'tasks_status': {
        'type': 'dict',
        'schema': {
            'count': {'type': 'integer'},
            'completed': {'type': 'integer'},
            'failed': {'type': 'integer'},
            'canceled': {'type': 'integer'}
        }
    },
    # The most important part of a job. These custom values are parsed by the
    # job compiler in order to generate the tasks.
    'settings': {
        'type': 'dict',
        # TODO: introduce dynamic validator, based on job_type/task_type
        'allow_unknown': True,
    },
}

tasks_schema = {
    'job': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'flamenco_jobs',
            'field': '_id',
            'embeddable': True
        },
    },
    'manager': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'flamenco_managers',
            'field': '_id',
            'embeddable': True
        },
    },
    'project': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'projects',
            'field': '_id',
            'embeddable': True
        },
    },
    'user': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'users',
            'field': '_id',
            'embeddable': True
        },
    },
    'name': {
        'type': 'string',
        'required': True,
    },
    'status': {
        'type': 'string',
        'allowed': [
            'queued',
            'claimed-by-manager',
            'completed',
            'active',
            'canceled',
            'processing',
            'failed'],
        'default': 'queued'
    },
    'priority': {
        'type': 'integer',
        'min': 1,
        'max': 100,
        'default': 50
    },
    'job_type': {
        'type': 'string',
        'required': True,
    },
    'commands': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                # The parser is inferred form the command name
                'name': {
                    'type': 'string',
                    'required': True,
                },
                # In the list of built arguments for the command, we will
                # replace the executable, which will be defined on the fly by
                # the manager
                'settings': {
                    'type': 'dict',
                    # TODO: introduce dynamic validator, based on job_type/task_type
                    'allow_unknown': True,
                },
            }
        },
    },
    'log': {
        'type': 'string',
    },
    'activity': {
        'type': 'string',
        'maxlength': 128
    },
    'parents': {
        'type': 'list',
        'schema': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'flamenco_tasks',
                'field': '_id',
                'embeddable': True
            }
        },
    },
    'worker': {
        'type': 'string',
    },
}

_managers = {
    'schema': managers_schema,
}

_jobs = {
    'schema': jobs_schema,
    'item_methods': ['GET', 'PUT', 'DELETE', 'PATCH'],
}

_tasks = {
    'schema': tasks_schema,
    'item_methods': ['GET', 'PUT', 'DELETE', 'PATCH'],
}

DOMAIN = {
    'flamenco_managers': _managers,
    'flamenco_jobs': _jobs,
    'flamenco_tasks': _tasks
}

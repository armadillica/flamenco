
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
    # Project IDs this manager is associated with.
    'projects': {
        'type': 'list',
        'schema': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'projects',
                'field': '_id',
            }
        },
    },
    # The service account of this manager.
    'service_account': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'users',
            'field': '_id',
        },
    },

    # Received from the manager itself at startup.
    'variables': {
        'type': 'dict',
        'allow_unknown': True,
    },
    'stats': {
        'type': 'dict',
        'schema': {
            # TODO: determine which statistics should be stored here.
            'nr_of_workers': {
                'type': 'integer',
            }
        }
    }

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
        },
    },
    'user': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'users',
            'field': '_id',
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
        },
    },
    'manager': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'flamenco_managers',
            'field': '_id',
        },
    },
    'project': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'projects',
            'field': '_id',
        },
    },
    'user': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'users',
            'field': '_id',
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
            'cancel-requested',
            'canceled',
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
            }
        },
    },
    'worker': {
        'type': 'string',
    },
    'task_progress_percentage': {
        'type': 'integer',
    },
    'current_command_index': {
        'type': 'integer',
    },
    'command_progress_percentage': {
        'type': 'integer',
    },
}

task_logs_schema = {
    'task': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'flamenco_tasks',
            'field': '_id',
        },
        'required': True,
    },
    'received_on_manager': {
        'type': 'datetime',
        'required': True,
    },
    'log': {
        'type': 'string',
        'required': True,
    },
}

_managers = {
    'schema': managers_schema,
    'item_methods': ['GET', 'PUT', 'PATCH'],
    'public_methods': [],
    'public_item_methods': [],
}

_jobs = {
    'schema': jobs_schema,
    'item_methods': ['GET', 'PUT', 'DELETE', 'PATCH'],
    'public_methods': [],
    'public_item_methods': [],
}

_tasks = {
    'schema': tasks_schema,
    'item_methods': ['GET', 'PUT', 'DELETE'],
    'public_methods': [],
    'public_item_methods': [],
}

_task_logs = {
    'schema': task_logs_schema,
    'item_methods': ['GET', 'DELETE'],
    'public_methods': [],
    'public_item_methods': [],
}

DOMAIN = {
    'flamenco_managers': _managers,
    'flamenco_jobs': _jobs,
    'flamenco_tasks': _tasks,
    'flamenco_task_logs': _task_logs,
}

node_type_task = {
    'job': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'jobs',
            'field': '_id',
            'embeddable': True
        },
    },
    'manager': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'managers',
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
            'completed',
            'active',
            'canceled',
            'queued',
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
                'resource': 'tasks',
                'field': '_id',
                'embeddable': True
            }
        },
    },
    'worker': {
        'type': 'string',
    },
}

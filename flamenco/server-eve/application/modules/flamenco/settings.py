managers_schema = {
    'name': {
        'type': 'string',
        'required': True,
    },
    'description': {
        'type': 'string',
    },
    'picture': {
        'type': 'string',
    },
    'host': {
        'type': 'string',
        'required': True
    }
}

jobs_schema = {
    'name': {
        'type': 'string',
        'required': True,
    },
    'job_type': {
        'type': 'string',
        'required': True,
    },
    'notes': {
        'type': 'string',
    },
    'project': {
         'type': 'objectid',
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
    'priority': {
        'type': 'integer',
        'min': 1,
        'max': 100,
        'default': 50
    },
    'tasks_status': {
        'type': 'dict',
        'schema': {
            'count': {'type': 'integer'},
            'completed': {'type': 'integer'},
            'failed': {'type': 'integer'},
            'canceled': {'type': 'integer'}
        }
    },
    'settings': {
        'type': 'dict',
        'schema': {
            'frames': {'type': 'string'},
            'chunk_size': {'type': 'integer'},
            'filepath': {'type': 'string'},
            'render_settings': {'type': 'string'},
            'format': {'type': 'string'}
        }
    }
}

managers = {
    'schema': managers_schema,
}

jobs = {
    'schema': jobs_schema,
}
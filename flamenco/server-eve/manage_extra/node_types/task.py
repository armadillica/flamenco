node_type_task = {
    'name': 'task',
    'description': 'Task Node Type, for tasks',
    'dyn_schema': {
        'status': {
            'type': 'string',
            'allowed': [
                'todo',
                'in_progress',
                'on_hold',
                'approved',
                'cbb',
                'final',
                'review'
            ],
            'required': True,
        },
        'filepath': {
            'type': 'string',
        },
        'revision': {
            'type': 'integer',
        },
        'owners': {
            'type': 'dict',
            'schema': {
                'users': {
                    'type': 'list',
                    'schema': {
                        'type': 'objectid',
                    }
                },
                'groups': {
                    'type': 'list',
                    'schema': {
                        'type': 'objectid',
                    }
                }
            }
        },
        'time': {
            'type': 'dict',
            'schema': {
                'start': {
                    'type': 'datetime'
                },
                'duration': {
                    'type': 'integer'
                },
                'chunks': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'start': {
                                'type': 'datetime',
                            },
                            'duration': {
                                'type': 'integer',
                            }
                        }
                    }
                },
            }
        },
        'is_conflicting' : {
            'type': 'boolean'
        },
        'is_processing' : {
            'type': 'boolean'
        },
        'is_open' : {
            'type': 'boolean'
        }

    },
    'form_schema': {
        'status': {},
        'filepath': {},
        'revision': {},
        'owners': {
            'schema': {
                'users':{
                    'items': [('User', 'first_name')],
                },
                'groups': {}
            }
        },
        'time': {
            'schema': {
                'start': {},
                'duration': {},
                'chunks': {
                    'visible': False,
                    'schema': {
                        'start': {},
                        'duration': {}
                    }
                }
            }
        },
        'is_conflicting': {},
        'is_open': {},
        'is_processing': {},
    },
    'parent': ['shot']
}

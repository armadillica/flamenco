node_type_task = {
    'name': 'flamenco_task',
    'description': 'Task Node Type, for tasks',
    'dyn_schema': {
        'status': {
            'type': 'string',
            'allowed': [
                'invalid',
                'todo',
                'in_progress',
                'on_hold',
                'approved',
                'cbb',  # Could Be Better
                'final',
                'review'
            ],
            'default': 'todo',
            'required': True,
        },
        'task_type': {
            'type': 'string',
        },
        'assigned_to': {
            'type': 'dict',
            'schema': {
                'users': {
                    'type': 'list',
                    'schema': {
                        # TODO: refer to user collection
                        'type': 'objectid',
                    }
                }
            }
        },

        'due_date': {
            'type': 'datetime',
        },

        # For Gantt charts and the like.
        'time': {
            'type': 'dict',
            'schema': {
                'planned_start': {
                    'type': 'datetime'
                },
                'planned_duration_hours': {
                    'type': 'integer'
                },
                'chunks': {
                    'type': 'list',
                    'schema': {
                        'type': 'dict',
                        'schema': {
                            'planned_start': {
                                'type': 'datetime',
                            },
                            'planned_duration_hours': {
                                'type': 'integer',
                            }
                        }
                    }
                },
            }
        },
        'shortcode': {
            'type': 'string',
            'required': False,
            'maxlength': 16,
        },
    },

    'form_schema': {
        'time': {'visible': False},
    },

    'parent': ['task', 'shot'],
}

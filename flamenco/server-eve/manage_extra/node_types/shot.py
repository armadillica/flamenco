node_type_shot = {
    'name': 'shot',
    'description': 'Shot Node Type, for shots',
    'dyn_schema': {
        'url': {
            'type': 'string',
        },
        'cut_in': {
            'type': 'integer'
        },
        'cut_out': {
            'type': 'integer'
        },
        'status': {
            'type': 'string',
            'allowed': [
                'on_hold',
                'todo',
                'in_progress',
                'review',
                'final'
            ],
        },
        'notes': {
            'type': 'string',
            'maxlength': 256,
        },
        'shot_group': {
            'type': 'string',
            #'data_relation': {
            #    'resource': 'nodes',
            #    'field': '_id',
            #},
        },
    },
    'form_schema': {
        'url': {},
        'cut_in': {},
        'cut_out': {},
        'status': {},
        'notes': {},
        'shot_group': {}
    },
    'parent': ['scene']
}

node_type_group = {
    'name': 'group',
    'description': 'Generic group node type edited',
    'parent': ['group', 'project'],
    'dyn_schema': {
        # Used for sorting within the context of a group
        'order': {
            'type': 'integer'
        },
        'url': {
            'type': 'string',
        },
        'status': {
            'type': 'string',
            'allowed': [
                'published',
                'pending',
            ],
        },
        'notes': {
            'type': 'string',
            'maxlength': 256,
        },
    },
    'form_schema': {
        'url': {'visible': False},
        'status': {},
        'notes': {'visible': False},
        'order': {'visible': False}
    },
    'permissions': {
    }
}

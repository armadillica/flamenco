node_type_group_texture = {
    'name': 'group_texture',
    'description': 'Group for texture node type',
    'parent': ['group_texture', 'project'],
    'dyn_schema': {
        # Used for sorting within the context of a group
        'order': {
            'type': 'integer'
        },
        'status': {
            'type': 'string',
            'allowed': [
                'published',
                'pending',
            ],
        }
    },
    'form_schema': {
        'status': {},
        'order': {}
    }
}

node_type_text = {
    'name': 'text',
    'description': 'Text',
    'parent': ['group', 'project'],
    'dyn_schema': {
        'content': {
            'type': 'string',
            'required': True,
            'minlength': 3,
            'maxlength': 90000,
        },
        'shared_slug': {
            'type': 'string',
            'required': False,
        },
        'syntax': {  # for syntax highlighting
            'type': 'string',
            'required': False,
        },
        'node_expires': {
            'type': 'datetime',
            'required': False,
        },
    },
    'form_schema': {
        'shared_slug': {'visible': False},
    }
}

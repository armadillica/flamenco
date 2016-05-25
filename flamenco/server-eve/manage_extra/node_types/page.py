from manage_extra.node_types import _file_embedded_schema

node_type_page = {
    'name': 'page',
    'description': 'A single page',
    'dyn_schema': {
        # The page content (Markdown format)
        'content': {
            'type': 'string',
            'minlength': 5,
            'maxlength': 90000,
            'required': True
        },
        'status': {
            'type': 'string',
            'allowed': [
                'published',
                'pending'
            ],
            'default': 'pending'
        },
        'url': {
            'type': 'string'
        },
        'attachments': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    'field': {'type': 'string'},
                    'files': {
                        'type': 'list',
                        'schema': {
                            'type': 'dict',
                            'schema': {
                                'file': _file_embedded_schema,
                                'slug': {'type': 'string', 'minlength': 1},
                                'size': {'type': 'string'}
                            }
                        }
                    }
                }
            }
        }
    },
    'form_schema': {
        'content': {},
        'status': {},
        'url': {},
        'attachments': {'visible': False},
    },
    'parent': ['project', ],
    'permissions': {}
}

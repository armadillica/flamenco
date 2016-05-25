from manage_extra.node_types import _file_embedded_schema

node_type_post = {
    'name': 'post',
    'description': 'A blog post, for any project',
    'dyn_schema': {
        # The blogpost content (Markdown format)
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
        # Global categories, will be enforced to be 1 word
        'category': {
            'type': 'string',
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
        'category': {},
        'url': {},
        'attachments': {'visible': False},
    },
    'parent': ['blog', ],
    'permissions': {}
}

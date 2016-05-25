from manage_extra.node_types import _file_embedded_schema

node_type_asset = {
    'name': 'asset',
    'description': 'Basic Asset Type',
    # This data type does not have parent limitations (can be child
    # of any node). An empty parent declaration is required.
    'parent': ['group', ],
    'dyn_schema': {
        'status': {
            'type': 'string',
            'allowed': [
                'published',
                'pending',
                'processing'
            ],
        },
        # Used for sorting within the context of a group
        'order': {
            'type': 'integer'
        },
        # We expose the type of asset we point to. Usually image, video,
        # zipfile, ect.
        'content_type': {
            'type': 'string'
        },
        # We point to the original file (and use it to extract any relevant
        # variation useful for our scope).
        'file': _file_embedded_schema,
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
        },
        # Tags for search
        'tags': {
            'type': 'list',
            'schema': {
                'type': 'string'
            }
        },
        # Simple string to represent hierarchical categories. Should follow
        # this schema: "Root > Nested Category > One More Nested Category"
        'categories': {
            'type': 'string'
        }
    },
    'form_schema': {
        'status': {},
        'content_type': {'visible': False},
        'file': {},
        'attachments': {'visible': False},
        'order': {'visible': False},
        'tags': {'visible': False},
        'categories': {'visible': False}
    },
    'permissions': {
    }
}

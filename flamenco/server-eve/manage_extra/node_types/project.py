from manage_extra.node_types import _file_embedded_schema

node_type_project = {
    'name': 'project',
    'parent': {},
    'description': 'The official project type',
    'dyn_schema': {
        'category': {
            'type': 'string',
            'allowed': [
                'training',
                'film',
                'assets',
                'software',
                'game'
            ],
            'required': True,
        },
        'is_private': {
            'type': 'boolean'
        },
        'url': {
            'type': 'string'
        },
        'organization': {
            'type': 'objectid',
            'nullable': True,
            'data_relation': {
               'resource': 'organizations',
               'field': '_id',
               'embeddable': True
            },
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
                        'data_relation': {
                            'resource': 'groups',
                            'field': '_id',
                            'embeddable': True
                        }
                    }
                }
            }
        },
        'status': {
            'type': 'string',
            'allowed': [
                'published',
                'pending',
            ],
        },
        # Logo
        'picture_square': _file_embedded_schema,
        # Header
        'picture_header': _file_embedded_schema,
        # Short summary for the project
        'summary': {
            'type': 'string',
            'maxlength': 128
        },
        # Latest nodes being edited
        'nodes_latest': {
            'type': 'list',
            'schema': {
                'type': 'objectid',
            }
        },
        # Featured nodes, manually added
        'nodes_featured': {
            'type': 'list',
            'schema': {
                'type': 'objectid',
            }
        },
        # Latest blog posts, manually added
        'nodes_blog': {
            'type': 'list',
            'schema': {
                'type': 'objectid',
            }
        }
    },
    'form_schema': {
        'is_private': {},
        # TODO add group parsing
        'category': {},
        'url': {},
        'organization': {},
        'picture_square': {},
        'picture_header': {},
        'summary': {},
        'owners': {
            'schema': {
                'users': {},
                'groups': {
                    'items': [('Group', 'name')],
                },
            }
        },
        'status': {},
        'nodes_featured': {},
        'nodes_latest': {},
        'nodes_blog': {}
    },
    'permissions': {
        # 'groups': [{
        #     'group': app.config['ADMIN_USER_GROUP'],
        #     'methods': ['GET', 'PUT', 'POST']
        # }],
        # 'users': [],
        # 'world': ['GET']
    }
}

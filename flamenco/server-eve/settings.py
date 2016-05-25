import os

# Enable reads (GET), inserts (POST) and DELETE for resources/collections
# (if you omit this line, the API will default to ['GET'] and provide
# read-only access to the endpoint).
RESOURCE_METHODS = ['GET', 'POST', 'DELETE']

# Enable reads (GET), edits (PATCH), replacements (PUT) and deletes of
# individual items  (defaults to read-only item access).
ITEM_METHODS = ['GET', 'PUT', 'DELETE', 'PATCH']

PAGINATION_LIMIT = 250
PAGINATION_DEFAULT = 250

_file_embedded_schema = {
    'type': 'objectid',
    'data_relation': {
        'resource': 'files',
        'field': '_id',
        'embeddable': True
    }
}

_required_user_embedded_schema = {
    'type': 'objectid',
    'required': True,
    'data_relation': {
        'resource': 'users',
        'field': '_id',
        'embeddable': True
    },
}

_activity_object_type = {
    'type': 'string',
    'required': True,
    'allowed': [
        'project',
        'user',
        'node'
    ],
}

users_schema = {
    'full_name': {
        'type': 'string',
        'minlength': 3,
        'maxlength': 128,
        'required': True,
    },
    'username': {
        'type': 'string',
        'minlength': 3,
        'maxlength': 128,
        'required': True,
        'unique': True,
    },
    'email': {
        'type': 'string',
        'minlength': 5,
        'maxlength': 60,
    },
    'roles': {
        'type': 'list',
        'allowed': ["admin", "subscriber", "demo"],
    },
    'groups': {
        'type': 'list',
        'default': [],
        'schema': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'groups',
                'field': '_id',
                'embeddable': True
            }
        }
    },
    'auth': {
        # Storage of authentication credentials (one will be able to auth with
        # multiple providers on the same account)
        'type': 'list',
        'required': True,
        'schema': {
            'type': 'dict',
            'schema': {
                'provider': {
                    'type': 'string',
                    'allowed': ["blender-id", "local"],
                },
                'user_id': {
                    'type': 'string'
                },
                # A token is considered a "password" in case the provider is
                # "local".
                'token': {
                    'type': 'string'
                }
            }
        }
    },
    'settings': {
        'type': 'dict',
        'schema': {
            'email_communications': {
                'type': 'integer',
                'allowed': [0, 1]
            }
        }
    }
}

organizations_schema = {
    'name': {
        'type': 'string',
        'minlength': 1,
        'maxlength': 128,
        'required': True
    },
    'email': {
        'type': 'string'
    },
    'url': {
        'type': 'string',
        'minlength': 1,
        'maxlength': 128,
        'required': True
    },
    'description': {
        'type': 'string',
        'maxlength': 256,
    },
    'website': {
        'type': 'string',
        'maxlength': 256,
    },
    'location': {
        'type': 'string',
        'maxlength': 256,
    },
    'picture': {
        'type': 'objectid',
        'nullable': True,
        'data_relation': {
           'resource': 'files',
           'field': '_id',
           'embeddable': True
        },
    },
    'users': {
        'type': 'list',
        'default': [],
        'schema': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
                'embeddable': True
            }
        }
    },
    'teams': {
        'type': 'list',
        'default': [],
        'schema': {
            'type': 'dict',
            'schema': {
                # Team name
                'name': {
                    'type': 'string',
                    'minlength': 1,
                    'maxlength': 128,
                    'required': True
                },
                # List of user ids for the team
                'users': {
                    'type': 'list',
                    'default': [],
                    'schema': {
                        'type': 'objectid',
                        'data_relation': {
                            'resource': 'users',
                            'field': '_id',
                        }
                    }
                },
                # List of groups assigned to the team (this will automatically
                # update the groups property of each user in the team)
                'groups': {
                    'type': 'list',
                    'default': [],
                    'schema': {
                        'type': 'objectid',
                        'data_relation': {
                            'resource': 'groups',
                            'field': '_id',
                        }
                    }
                }
            }
        }
    }
}

permissions_embedded_schema = {
    'groups': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'group': {
                    'type': 'objectid',
                    'required': True,
                    'data_relation': {
                        'resource': 'groups',
                        'field': '_id',
                        'embeddable': True
                    }
                },
                'methods': {
                    'type': 'list',
                    'required': True,
                    'allowed': ['GET', 'PUT', 'POST', 'DELETE']
                }
            }
        },
    },
    'users': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'user' : {
                    'type': 'objectid',
                    'required': True,
                },
                'methods': {
                    'type': 'list',
                    'required': True,
                    'allowed': ['GET', 'PUT', 'POST', 'DELETE']
                }
            }
        }
    },
    'world': {
        'type': 'list',
        #'required': True,
        'allowed': ['GET',]
    },
    'is_free': {
        'type': 'boolean',
    }
}

nodes_schema = {
    'name': {
        'type': 'string',
        'minlength': 1,
        'maxlength': 128,
        'required': True,
    },
    'description': {
        'type': 'string',
    },
    'picture': {
        'type': 'objectid',
        'data_relation': {
           'resource': 'files',
           'field': '_id',
           'embeddable': True
        },
    },
    'order': {
        'type': 'integer',
        'minlength': 0,
    },
    'revision': {
        'type': 'integer',
    },
    'parent': {
        'type': 'objectid',
         'data_relation': {
            'resource': 'nodes',
            'field': '_id',
            'embeddable': True
         },
    },
    'project': {
        'type': 'objectid',
         'data_relation': {
            'resource': 'projects',
            'field': '_id',
            'embeddable': True
         },
    },
    'user': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'users',
            'field': '_id',
            'embeddable': True
        },
    },
    'node_type': {
        'type': 'string',
        'required': True
    },
    'properties': {
        'type' : 'dict',
        'valid_properties' : True,
        'required': True,
     },
    'permissions': {
        'type': 'dict',
        'schema': permissions_embedded_schema
    }
}

node_types_schema = {
    'name': {
        'type': 'string',
        'minlength': 1,
        'maxlength': 128,
        'required': True,
    },
    'description': {
        'type': 'string',
        'maxlength': 256,
    },
    'dyn_schema': {
        'type': 'dict',
        'required': True,
    },
    'form_schema': {
        'type': 'dict',
        'required': True,
    },
    'parent': {
        'type': 'dict',
        'required': True,
    },
    'permissions': {
        'type': 'dict',
        'required': True,
        'schema': permissions_embedded_schema
    }
}

tokens_schema = {
    'user': {
        'type': 'objectid',
        'required': True,
    },
    'token': {
        'type': 'string',
        'required': True,
    },
    'expire_time': {
        'type': 'datetime',
        'required': True,
    },
    'is_subclient_token': {
        'type': 'boolean',
        'required': False,
    }
}

files_schema = {
    # Name of the file after processing, possibly hashed.
    'name': {
        'type': 'string',
        'required': True,
    },
    'description': {
        'type': 'string',
    },
    'content_type': { # MIME type image/png video/mp4
        'type': 'string',
        'required': True,
    },
    # Duration in seconds, only if it's a video
    'duration': {
        'type': 'integer',
    },
    'size': { # xs, s, b, 720p, 2K
        'type': 'string'
    },
    'format': { # human readable format, like mp4, HLS, webm, mov
        'type': 'string'
    },
    'width': { # valid for images and video content_type
        'type': 'integer'
    },
    'height': {
        'type': 'integer'
    },
    'user': {
        'type': 'objectid',
        'required': True,
    },
    'length': { # Size in bytes
        'type': 'integer',
        'required': True,
    },
    'length_aggregate_in_bytes': {  # Size of file + all variations
        'type': 'integer',
        'required': False,  # it's computed on the fly anyway, so clients don't need to provide it.
    },
    'md5': {
        'type': 'string',
        'required': True,
    },

    # Original filename as given by the user, possibly cleaned-up to make it safe.
    'filename': {
        'type': 'string',
        'required': True,
    },
    'backend': {
        'type': 'string',
        'required': True,
        'allowed': ["attract-web", "pillar", "cdnsun", "gcs", "unittest"]
    },

    # Where the file is in the backend storage itself. In the case of GCS,
    # it is relative to the /_ folder. In the other cases, it is relative
    # to the root of that storage backend. required=False to allow creation
    # before uploading to a storage, in case the final path is determined
    # by that storage backend.
    'file_path': {
        'type': 'string',
    },
    'link': {
        'type': 'string',
    },
    'link_expires': {
        'type': 'datetime',
    },
    'project': {
        # The project node the files belongs to (does not matter if it is
        # attached to an asset or something else). We use the project id as
        # top level filtering, folder or bucket name. Later on we will be able
        # to join permissions from the project and verify user access.
        'type': 'objectid',
        'data_relation': {
            'resource': 'projects',
            'field': '_id',
            'embeddable': True
        },
    },
    'variations': { # File variations (used to be children, see above)
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'is_public': { # If True, the link will not be hashed or signed
                    'type': 'boolean'
                },
                'content_type': { # MIME type image/png video/mp4
                    'type': 'string',
                    'required': True,
                },
                'duration': {
                    'type': 'integer',
                },
                'size': { # xs, s, b, 720p, 2K
                    'type': 'string'
                },
                'format': { # human readable format, like mp4, HLS, webm, mov
                    'type': 'string'
                },
                'width': { # valid for images and video content_type
                    'type': 'integer'
                },
                'height': {
                    'type': 'integer'
                },
                'length': { # Size in bytes
                    'type': 'integer',
                    'required': True,
                },
                'md5': {
                    'type': 'string',
                    'required': True,
                },
                'file_path': {
                    'type': 'string',
                },
                'link': {
                    'type': 'string',
                }
            }
        }
    },
    'processing': {
        'type': 'dict',
        'schema': {
            'job_id': {
                'type': 'string' # can be int, depending on the backend
            },
            'backend': {
                'type': 'string',
                'allowed': ["zencoder", "local"]
            },
            'status': {
                'type': 'string',
                'allowed': ["pending", "waiting", "processing", "finished",
                    "failed", "cancelled"]
            },
        }
    },
    'status': {
        'type': 'string',
        'allowed': ['uploading', 'queued_for_processing', 'processing', 'complete', 'failed'],
        'required': False,
        'default': 'complete',  # default value for backward compatibility.
    },
}

groups_schema = {
    'name': {
        'type': 'string',
        'required': True
    }
}

projects_schema = {
    'name': {
        'type': 'string',
        'minlength': 1,
        'maxlength': 128,
        'required': True,
    },
    'description': {
        'type': 'string',
    },
    # Short summary for the project
    'summary': {
        'type': 'string',
        'maxlength': 128
    },
    # Logo
    'picture_square': _file_embedded_schema,
    # Header
    'picture_header': _file_embedded_schema,
    'user': {
        'type': 'objectid',
        'required': True,
        'data_relation': {
            'resource': 'users',
            'field': '_id',
            'embeddable': True
        },
    },
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
        'type': 'boolean',
        'default': True,
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
    'status': {
        'type': 'string',
        'allowed': [
            'published',
            'pending',
        ],
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
    },
    # Where Node type schemas for every projects are defined
    'node_types': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                # URL is the way we identify a node_type when calling it via
                # the helper methods in the Project API.
                'url': {'type': 'string'},
                'name': {'type': 'string'},
                'description': {'type': 'string'},
                # Allowed parents for the node_type
                'parent': {
                    'type': 'list',
                    'schema': {
                        'type': 'string'
                    }
                },
                'dyn_schema': {
                    'type': 'dict',
                    'allow_unknown': True
                },
                'form_schema': {
                    'type': 'dict',
                    'allow_unknown': True
                },
                'permissions': {
                    'type': 'dict',
                    'schema': permissions_embedded_schema
                }
            },

        }
    },
    'permissions': {
        'type': 'dict',
        'schema': permissions_embedded_schema
    }
}

activities_subscriptions_schema = {
    'user': _required_user_embedded_schema,
    'context_object_type': _activity_object_type,
    'context_object': {
        'type': 'objectid',
        'required': True
    },
    'notifications': {
        'type': 'dict',
        'schema': {
            'email': {
                'type': 'boolean',
            },
            'web': {
                'type': 'boolean',
                'default': True
            },
        }
    },
    'is_subscribed': {
        'type': 'boolean',
        'default': True
    }
}

activities_schema = {
    'actor_user': _required_user_embedded_schema,
    'verb': {
        'type': 'string',
        'required': True
    },
    'object_type': _activity_object_type,
    'object': {
        'type': 'objectid',
        'required': True
    },
    'context_object_type': _activity_object_type,
    'context_object': {
        'type': 'objectid',
        'required': True
    },
}

notifications_schema = {
    'user': _required_user_embedded_schema,
    'activity': {
        'type': 'objectid',
        'required': True,
    },
    'is_read': {
        'type': 'boolean',
    },
}

nodes = {
    'schema': nodes_schema,
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'soft_delete': True,
}

users = {
    'item_title': 'user',

    # We choose to override global cache-control directives for this resource.
    'cache_control': 'max-age=10,must-revalidate',
    'cache_expires': 10,

    'resource_methods': ['GET'],
    'item_methods': ['GET', 'PUT'],
    'public_item_methods': ['GET'],

    # By default don't include the 'auth' field. It can still be obtained
    # using projections, though, so we block that in hooks.
    'datasource': {'projection': {u'auth': 0}},

    'schema': users_schema
}

tokens = {
    'resource_methods': ['GET', 'POST'],

    # Allow 'token' to be returned with POST responses
    #'extra_response_fields': ['token'],

    'schema' : tokens_schema
}

files = {
    'resource_methods': ['GET', 'POST'],
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'schema': files_schema
}

groups = {
    'resource_methods': ['GET', 'POST'],
    'public_methods': ['GET'],
    'public_item_methods': ['GET'],
    'schema': groups_schema,
}

organizations = {
    'schema': organizations_schema,
    'public_item_methods': ['GET'],
    'public_methods': ['GET']
}

projects = {
    'schema': projects_schema,
    'public_item_methods': ['GET'],
    'public_methods': ['GET'],
    'soft_delete': True,
}

activities = {
    'schema': activities_schema,
}

activities_subscriptions = {
    'schema': activities_subscriptions_schema,
}

notifications = {
    'schema': notifications_schema,
}


DOMAIN = {
    'users': users,
    'nodes': nodes,
    'tokens': tokens,
    'files': files,
    'groups': groups,
    'organizations': organizations,
    'projects': projects,
    'activities': activities,
    'activities-subscriptions': activities_subscriptions,
    'notifications': notifications
}


MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = os.environ.get('MONGO_PORT', 27017)
MONGO_DBNAME = os.environ.get('MONGO_DBNAME', 'eve')
CACHE_EXPIRES = 60
HATEOAS = False
UPSET_ON_PUT = False  # do not create new document on PUT of non-existant URL.
X_DOMAINS = '*'
X_ALLOW_CREDENTIALS = True
X_HEADERS = 'Authorization'
XML = False

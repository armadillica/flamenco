node_type_storage = {
    'name': 'storage',
    'description': 'Entrypoint to a remote or local storage solution',
    'dyn_schema': {
        # The project ID, use for lookups in the storage backend. For example
        # when using Google Cloud Storage, the project id will be the name
        # of the bucket.
        'project': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'nodes',
                'field': '_id'
            },
        },
        # The entry point in a subdirectory of the main storage for the project
        'subdir': {
            'type': 'string',
        },
        # Which backend is used to store the files (gcs, pillar, bam, cdnsun)
        'backend': {
            'type': 'string',
        },
    },
    'form_schema': {
        'subdir': {},
        'project': {},
        'backend': {}
    },
    'parent': ['group', 'project'],
    'permissions': {
        # 'groups': [{
        #     'group': app.config['ADMIN_USER_GROUP'],
        #     'methods': ['GET', 'PUT', 'POST']
        # }],
        # 'users': [],
    }
}

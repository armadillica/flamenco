node_type_blog = {
    'name': 'blog',
    'description': 'Container for node_type post.',
    'dyn_schema': {
        # Path for a custom template to be used for rendering the posts
        'template': {
            'type': 'string',
        },
        'categories' : {
            'type': 'list',
            'schema': {
                'type': 'string'
            }
        }
    },
    'form_schema': {
        'categories': {},
        'template': {},
    },
    'parent': ['project',],
    'permissions': {
        # 'groups': [{
        #     'group': app.config['ADMIN_USER_GROUP'],
        #     'methods': ['GET', 'PUT', 'POST']
        # }],
        # 'users': [],
        # 'world': ['GET']
    }
}

node_type_comment = {
    'name': 'comment',
    'description': 'Comments for asset nodes, pages, etc.',
    'dyn_schema': {
        # The actual comment content (initially Markdown format)
        'content': {
            'type': 'string',
            'minlength': 5,
        },
        'status': {
            'type': 'string',
            'allowed': [
                'published',
                'flagged',
                'edited'
            ],
        },
        # Total count of positive ratings (updated at every rating action)
        'rating_positive': {
            'type': 'integer',
        },
        # Total count of negative ratings (updated at every rating action)
        'rating_negative': {
            'type': 'integer',
        },
        # Collection of ratings, keyed by user
        'ratings': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    'user': {
                        'type': 'objectid'
                    },
                    'is_positive': {
                        'type': 'boolean'
                    },
                    # Weight of the rating based on user rep and the context.
                    # Currently we have the following weights:
                    # - 1 auto null
                    # - 2 manual null
                    # - 3 auto valid
                    # - 4 manual valid
                    'weight': {
                        'type': 'integer'
                    }
                }
            }
        },
        'confidence': {'type': 'float'},
        'is_reply': {'type': 'boolean'}
    },
    'form_schema': {
        'content': {},
        'status': {},
        'rating_positive': {},
        'rating_negative': {},
        'ratings': {},
        'confidence': {},
        'is_reply': {}
    },
    'parent': ['asset', 'comment'],
    'permissions': {
    }
}

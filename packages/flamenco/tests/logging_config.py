LOGGING = {
    'version': 1,
    'formatters': {
        'default': {'format': '%(asctime)-15s %(levelname)8s %(name)36s %(message)s'}
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'stream': 'ext://sys.stderr',
        }
    },
    'loggers': {
        'pillar': {'level': 'DEBUG'},
        'attract': {'level': 'DEBUG'},
        'werkzeug': {'level': 'INFO'},
        'eve': {'level': 'WARNING'},
        # 'requests': {'level': 'DEBUG'},
    },
    'root': {
        'level': 'INFO',
        'handlers': [
            'console',
        ],
    }
}

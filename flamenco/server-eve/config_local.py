import os
from collections import defaultdict

SCHEME = 'http'
STORAGE_DIR = os.environ.get('STORAGE_DIR', '/data/storage/pillar')
SHARED_DIR = os.environ.get('SHARED_DIR', '/data/storage/shared')
PORT = 9999
HOST = '0.0.0.0'
DEBUG = True
CDN_USE_URL_SIGNING = True
CDN_SERVICE_DOMAIN_PROTOCOL = 'https'
CDN_SERVICE_DOMAIN = 'test-blendercloud.r.worldssl.net'
CDN_CONTENT_SUBFOLDER = ''
CDN_URL_SIGNING_KEY = 'LFq8QZJx043IIR6d'

CDN_STORAGE_USER = 'u41508580125621' # testing
# CDN_STORAGE_USER = 'u41502060271335' # production
CDN_STORAGE_ADDRESS = 'push-11.cdnsun.com'
CDN_SYNC_LOGS = '/data/storage/logs'
CDN_RSA_KEY = '/data/config/cdnsun_id_rsa'
CDN_KNOWN_HOSTS = '/data/config/known_hosts'

UPLOADS_LOCAL_STORAGE_THUMBNAILS = {
    's': {'size': (90, 90), 'crop': True},
    'b': {'size': (160, 160), 'crop': True},
    't': {'size': (160, 160), 'crop': False},
    'm': {'size': (320, 320), 'crop': False},
    'l': {'size': (1024, 1024), 'crop': False},
    'h': {'size': (2048, 2048), 'crop': False}
}

# BIN_FFPROBE = '/usr/bin/ffprobe'
BIN_FFPROBE = '/usr/local/bin/ffprobe'
# BIN_FFMPEG = '/usr/bin/ffmpeg'
BIN_FFMPEG = '/usr/local/bin/ffmpeg'
BIN_SSH = '/usr/bin/ssh'
BIN_RSYNC = '/usr/bin/rsync'

BLENDER_ID_ENDPOINT = os.environ.get(
    'BLENDER_ID_ENDPOINT', "https://www.blender.org/id").rstrip("/")

GCLOUD_APP_CREDENTIALS = '/Users/fsiddi/Documents/Kitematic/flamenco/config/google_app_dev.json'
GCLOUD_PROJECT = 'blender-cloud-dev'

ADMIN_USER_GROUP = '5596e975ea893b269af85c0e'
SUBSCRIBER_USER_GROUP = '5596e975ea893b269af85c0f'
BUGSNAG_API_KEY = ''

ALGOLIA_USER = '94FQ6RMSIC'
ALGOLIA_API_KEY = '6b0b6ff99ca991b08265aed7c409617d'
ALGOLIA_INDEX_USERS = 'dev_Users'
ALGOLIA_INDEX_NODES = 'dev_Nodes'

#47e0ffad54a7840c999b121d6ebab47b
ZENCODER_API_KEY = '856c4f96ff14a3e69f832cd099a78c42'
ZENCODER_NOTIFICATIONS_SECRET = '380f715d163c8edde52fa0d0edca4505'
ZENCODER_NOTIFICATIONS_URL = 'http://zencoderfetcher/'

ENCODING_BACKEND = 'zencoder' #local, flamenco

# Validity period of links, per file storage backend. Expressed in seconds.
# Shouldn't be more than a year, as this isn't supported by HTTP/1.1.
FILE_LINK_VALIDITY = defaultdict(
    lambda: 3600 * 24 * 30,  # default of 1 month.
    gcs=3600 * 23,  # 23 hours for Google Cloud Storage.
)

LOGGING = {
    'version': 1,
    'formatters': {
        'default': {'format': '%(asctime)-15s %(levelname)8s %(name)s %(message)s'}
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'default',
            'stream': 'ext://sys.stderr',
        }
    },
    'loggers': {
        'application': {'level': 'DEBUG'},
        'werkzeug': {'level': 'INFO'},
    },
    'root': {
        'level': 'WARNING',
        'handlers': [
            'console',
        ],
    }
}
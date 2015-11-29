import os

class Config(object):
    DEBUG = True
    USE_X_SENDFILE = os.getenv('USE_X_SENDFILE', False)
    FLAMENCO_SERVER = 'localhost:9999'
    PORT = 8888
    HOST = '0.0.0.0'


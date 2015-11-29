import os
import tempfile
import socket

class Config(object):
    DEBUG = True
    USE_X_SENDFILE = os.getenv('USE_X_SENDFILE', False)
    PORT = 7777
    HOST = '0.0.0.0' # or 'localhost'
    NAME = 'My Manager' # or use socket.gethostname()
    FLAMENCO_SERVER = 'localhost:9999'

    DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(__file__), '../')
    DATABASE_NAME = 'manager.sqlite'
    SQLALCHEMY_DATABASE_URI = os.path.join(DATABASE_URI, DATABASE_NAME)

    VIRTUAL_WORKERS = False # If true, the manager will not have a fixed number of workers
    IS_PRIVATE_MANAGER = False

    # If IS_PRIVATE_MANAGER is False, the following settings are not neede
    TMP_FOLDER = tempfile.gettempdir()
    THUMBNAIL_EXTENSIONS = set(['png'])

    MANAGER_STORAGE = '{0}/static/storage'.format(
        os.path.join(os.path.dirname(__file__)))

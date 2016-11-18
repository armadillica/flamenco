import os
import tempfile


class Config(object):
    DEBUG = True
    USE_X_SENDFILE = os.getenv('USE_X_SENDFILE', False)
    PORT = 7777
    HOST = '0.0.0.0'  # or 'localhost'
    NAME = 'My Manager'  # or use socket.gethostname()
    FLAMENCO_SERVER = 'http://pillar:5000/api/flamenco'
    FLAMENCO_SERVER_TOKEN = ''

    DATABASE_URI = 'mysql://root:root@mysql'
    DATABASE_NAME = 'flamenco_manager'
    SQLALCHEMY_DATABASE_URI = os.path.join(DATABASE_URI, DATABASE_NAME)

    # If true, the manager will not have a fixed number of workers
    VIRTUAL_WORKERS = False
    IS_PRIVATE_MANAGER = False

    # If IS_PRIVATE_MANAGER is False, the following settings are not needed
    TMP_FOLDER = tempfile.gettempdir()
    THUMBNAIL_EXTENSIONS = {'png'}

    MANAGER_STORAGE = '{0}/static/storage'.format(
        os.path.join(os.path.dirname(__file__)))

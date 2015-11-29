import os
import tempfile

class Config(object):
    DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(__file__), '../')
    DATABASE_NAME = 'server.sqlite'
    SQLALCHEMY_DATABASE_URI = os.path.join(DATABASE_URI, DATABASE_NAME)
    DEBUG = True
    USE_X_SENDFILE = os.getenv('USE_X_SENDFILE', False)
    PORT = 9999
    HOST = '0.0.0.0' # or 'localhost'
    TMP_FOLDER = tempfile.gettempdir()
    THUMBNAIL_EXTENSIONS = set(['png'])
    STORAGE_SERVER = '{0}/static/storage'.format(
        os.path.join(os.path.dirname(__file__)))

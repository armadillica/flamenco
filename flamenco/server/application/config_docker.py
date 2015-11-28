import os

class Config(object):
    DATABASE_URI = 'mysql://root:root@mysql_flamenco'
    DATABASE_NAME = 'server'
    SQLALCHEMY_DATABASE_URI = os.path.join(DATABASE_URI, DATABASE_NAME)
    THUMBNAIL_EXTENSIONS = set(['png', 'jpg', 'jpeg'])
    SERVER_STORAGE = '/data/storage/server'

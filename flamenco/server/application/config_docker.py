import os

class Config(object):
    DATABASE_URI = 'mysql://root:root@mysql'
    DATABASE_NAME = 'server'
    SQLALCHEMY_DATABASE_URI = os.path.join(DATABASE_URI, DATABASE_NAME)
    STORAGE_SERVER = '/data/storage/server'

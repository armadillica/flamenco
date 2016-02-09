import os

class Config(object):
    FLAMENCO_SERVER = 'flamenco_server:9999'
    DATABASE_URI = 'mysql://root:root@mysql'
    DATABASE_NAME = 'manager'
    SQLALCHEMY_DATABASE_URI = os.path.join(DATABASE_URI, DATABASE_NAME)
    MANAGER_STORAGE = '/data/storage/manager'

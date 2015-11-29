import os
import tempfile
import socket

class Config(object):
    FLAMENCO_MANAGER = 'localhost:7777'
    HOSTNAME = socket.gethostname()
    STORAGE_DIR = os.path.join(tempfile.gettempdir(),
        'flamenco-worker', HOSTNAME)


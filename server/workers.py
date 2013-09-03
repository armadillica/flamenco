from model import *
from utils import *

def update_worker(worker, worker_status, worker_connection, worker_config):
    if worker.connection != 'offline':
        worker.connection = 'online'
        worker.save()
    print worker.connection

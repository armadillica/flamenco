from model import *
from utils import *

def update_worker(worker, worker_status, worker_config):
    if worker.status != 'offline':
        worker.status = worker_status
        worker.save()
    print worker.status

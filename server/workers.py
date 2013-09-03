from model import *
from utils import *

def update_worker(worker, worker_data):
    if worker.connection != 'offline':
        worker.connection = 'online'
        worker.save()
    for key, val in worker_data.iteritems():
    	print key, val
    	if val:
    		setattr(worker, key, val)
    worker.save()
    print 'status', worker.status

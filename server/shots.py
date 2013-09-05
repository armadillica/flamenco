from model import *
from utils import *

def delete_shot(shot_id):
	try:
		shot = Shots.get(Shots.id == shot_id)
	except Exception, e:
	    print e
	    return 'error'
	shot.delete_instance()
	print 'deleted shot', shot_id

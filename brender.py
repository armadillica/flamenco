# brender functions

IS_DEBUG = True

def d_print(msg):
	"""Debug print function
	
	It will only print ifthe constant IS_DEBUG is True.
	
	"""
	if IS_DEBUG == False:
		pass
	else:
		print('[debug] ' + msg)


def slave_select(slave_id):
"""Selects a slave from the list"""

for slave in slaves_list:
	if slave.id == slave_id:
		return slave
	else:
		pass


def slave_status(slave_id, status):
	"""Set status of a connected slave"""
	
	slave_select(slave_id).socket.send(status)
	return


def slave_msg(slave_id, msg):
	slave = 
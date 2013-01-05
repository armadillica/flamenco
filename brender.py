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


# some random model functions

# load clients from database
# CRUD clients from database

# later on we will deal with jobs
# and orders
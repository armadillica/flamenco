# brender functions

IS_DEBUG = True

# debug print, will print only it IS_DEBUG is True
def d_print(msg):
	if IS_DEBUG == False:
		pass
	else:
		print('[debug] ' + msg)
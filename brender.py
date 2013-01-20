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


def json_output(format, table_rows_list):
	if format == 'dataTable':
		output = {"aaData": table_rows_list}
		return output
	else:
		output = {"data": table_rows_list}
		return str(output)

te = [["Trident","Internet Explorer 4.0","Win 95+","4","X"],
	["Trident","Internet Explorer 5.0","Win 95+","5","C"]]

#print(json_output('dataTable', te))

# later on we will deal with jobs
# and orders
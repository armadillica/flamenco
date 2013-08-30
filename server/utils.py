import urllib

def http_request(ip_address, method, post_params = False):
    # post_params must be a dictionay
    if post_params:
        params = urllib.urlencode(post_params)
        f = urllib.urlopen('http://' + ip_address + method, params)
    else:
        f = urllib.urlopen('http://' + ip_address + method)
    
    print 'message sent, reply follows:'
    print f.read()

def list_integers_string(string_list):
	"""Accepts comma separated string list of integers"""
	integers_list = string_list.split(',')
	integers_list = map(int, integers_list)
	return integers_list

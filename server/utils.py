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

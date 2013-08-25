import urllib
params = urllib.urlencode({'client': 1, 'eggs': 2})
#f = urllib.urlopen("http://brender-server:9999/connect", params)
f = urllib.urlopen("http://brender-server:9999/order", params)
print f.read()

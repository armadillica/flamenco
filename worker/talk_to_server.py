import urllib
params = urllib.urlencode({'client': 1, 'eggs': 2})
#f = urllib.urlopen("http://brender-server:9999/connect", params)
f = urllib.urlopen("http://localhost:5000/run_job", params)
print f.read()

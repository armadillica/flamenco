import urllib
worker_config = {'system' : 'linux', 'blender': 'local'}
params = urllib.urlencode({'id': '1,2', 'status': 'active', 'config' : worker_config})
f = urllib.urlopen("http://brender-server:9999/workers/edit", params)
#f = urllib.urlopen("http://localhost:5000/run_job", params)
print f.read()

import urllib
#worker_config = {'system' : 'linux', 'blender': 'local'}
#params = urllib.urlencode({'id': '438, 439', 'status': 'app', 'config' : worker_config})
params = urllib.urlencode({
	'blender_path_linux' : '/the/path', 
	'blender_path_osx' : '/the/path'})

f = urllib.urlopen(
		"http://brender-server:9999/settings/update", 
		params)
#f = urllib.urlopen("http://localhost:5000/run_job", params)
print f.read()

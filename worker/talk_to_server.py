import urllib
#worker_config = {'system' : 'linux', 'blender': 'local'}
#params = urllib.urlencode({'id': '438, 439', 'status': 'app', 'config' : worker_config})
params = urllib.urlencode({
    	'file_path': '/Users/fsiddi/Dropbox/brender/test_blends/cubes.blend',
        'blender_path' : '/Applications/Blender/buildbot/blender-2.69-r60745-OSX-10.6-x86_64/blender.app/Contents/MacOS/blender',
    	'start': 2,
    	'end': 8
    	})


f = urllib.urlopen(
		"http://127.0.0.1:5000/render_chunk", 
		params)
#f = urllib.urlopen("http://localhost:5000/run_job", params)
print f.read()

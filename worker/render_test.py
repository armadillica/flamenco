blender_path = "/Applications/blender/Blender_2_68/blender.app/Contents/MacOS/blender"
file_path = "/Users/o/Dropbox/brender/test_blends/monkey.blend"
options = "-s 1 -e 5 -a"

render_command = '%s -b %s %s' % (blender_path, file_path, options);
print render_command

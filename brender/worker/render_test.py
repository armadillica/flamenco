import subprocess
import sys
import time

blender_path = "/Applications/blender/Blender_2_68/blender.app/Contents/MacOS/blender"
file_path = "/Users/o/Dropbox/brender/test_blends/monkey.blend"
options = "-s 1 -e 2 -a"

render_command = '%s -b %s %s' % (blender_path, file_path, options)

subp = subprocess.Popen(render_command, stdout=subprocess.PIPE, shell=True)

#print(return_code)

#time.sleep(3)
#subp.terminate()

(output, err) = subp.communicate()
#print(output)
with open('log.log', 'w') as f:
    f.write(str(output))

while 1 == 3:
    out = subp.stdout.read(10)
    if out == '' and subp.poll() is not None:
        break
    if out != '':
        f = open('render.log', 'w')
        print(out)
        f.write(out)
        #sys.stdout.write(out)
        #sys.stdout.flush()

"""
for i in range(4):
    running = subp.poll()
    print("---------%s ---- %s" % (i,running))
    if running == None:
        print("RUNNING")
    time.sleep(1)

"""
#print(render_command)
#os.system(render_command)

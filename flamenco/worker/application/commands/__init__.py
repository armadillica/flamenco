import platform
import subprocess
PLATFORM = platform.system()


def cmd_sleep(duration=1):
    print('sleeping {} seconds'.format(duration))
    command = ['sleep', str(duration)]
    PROCESS = subprocess.Popen(command,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)

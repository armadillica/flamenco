import time
import argparse
from application.config_base import Config
parser = argparse.ArgumentParser(description='Run the Flamenco worker.')
parser.add_argument('-l', '--loop', default=5,
    help='Loop time. Default is 5 seconds.')
parser.add_argument('-m', '--manager', default='localhost:7777',
    help='Manager address. Default is localhost:7777.')
args = parser.parse_args()

# Override base config with command line options
from application.config_base import Config
Config.FLAMENCO_MANAGER = args.manager

if __name__ == "__main__":
    from application.controllers import worker_loop

    print ("""
      __ _
     / _| |
    | |_| | __ _ _ __ ___   ___ _ __   ___ ___
    | _ | |/ _` | '_ ` _ \ / _ \ '_ \ / __/ _ \\
    | | | | (_| | | | | | |  __/ | | | (_| (_) |
    |_| |_|\__,_|_| |_| |_|\___|_| |_|\___\___/

    """)

    while True:
        worker_loop()
        time.sleep(float(args.loop))

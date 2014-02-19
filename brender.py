#!/usr/bin/env python
import sys
import os
from threading import Thread
import socket
import time
import subprocess

try:
    import config
    print('[Info] Loading configuration from config.py')
    Server = config.Server
    Dashboard = config.Dashboard
    Worker = config.Worker
except ImportError:
    print('[Warning] No configuration file were found! Using default config settings.')
    print('[Warning] For more info see config.py. example file or README file.')
    Server = None
    Dashboard = None
    Worker = None

if len(sys.argv) < 2:
    sys.exit('Usage: %s component-name (i.e. server, dashboard or worker)' % sys.argv[0])
elif (sys.argv[1] == 'worker'):
    print 'running worker'
    import worker
    worker.serve(Worker)
elif (sys.argv[1] == 'dashboard'):
    print 'running dashboard'
    import dashboard
    dashboard.serve(Dashboard)
elif (sys.argv[1] == 'server'):
    print 'running server'
    import server
    server.serve(Server)
else:
    sys.exit('Usage: %s component-name (i.e. server, dashboard or worker)' % sys.argv[0])
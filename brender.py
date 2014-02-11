#!/usr/bin/python
import sys
import os
from threading import Thread
import socket
import time
import subprocess

if len(sys.argv) < 2:
    sys.exit('Usage: %s component-name (i.e. server, dashboard or worker)' % sys.argv[0])
elif (sys.argv[1] == 'worker'):
    print 'running worker'
    """
    # this is going to be an HTTP request to the server with all the info
    # for registering the render node
    def register_worker():
        import httplib
        while True:
            try:
                connection = httplib.HTTPConnection('127.0.0.1', PORT)
                connection.request("GET", "/info")
                break
            except socket.error:
                pass
            time.sleep(0.1)

        http_request('connect', {'mac_address': MAC_ADDRESS,
                                           'port': PORT,
                                           'hostname': HOSTNAME,
                                           'system': SYSTEM})
    """
    from worker import start_worker
    """
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        register_thread = Thread(target=register_worker)
        register_thread.setDaemon(False)
        register_thread.start()
    app.run(host='0.0.0.0')
    """
    start_worker()
elif (sys.argv[1] == 'dashboard'):
    print 'running dashboard'
    from dashboard import app
    app.run(host='0.0.0.0')
elif (sys.argv[1] == 'server'):
    print 'running server'
    from server import app
    app.run(host='0.0.0.0')
else:
    sys.exit('Usage: %s component-name (i.e. server, dashboard or worker)' % sys.argv[0])


#from server import app
#from server import db
#db.create_all()
#app.run()

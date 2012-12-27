brender
=======

Development repo for brender 2.0 (the original verions is here https://github.com/oenvoyage/brender)

## Installation
Basic requirement at the moment are:
* Python 2.7
* gevent (awesome lib for concurrency)

To install gevent on OSX, che this docs out:
* http://stackoverflow.com/questions/7630388/how-can-i-install-python-library-gevent-on-mac-osx-lion
* Install libevent (brew install libevent)
* Install gevent (easy_install gevent)

## Architecture
At the moment there are 3 files:
* master.py - the server that handles all the client connections and dispatches orders
* slave.py - a stupid client that connects to the master and waits for orders
* php_client.php - a test script to talk to the master from a php script (proof of concept for web interface)

Is is possible to connect to the master via telnet using the command `telent localhost 6000`.
A command prompt will appear and it will be possible to talk to the master.

## List of commands
No real commands are currently available. As soon as there is a good implementation for the enable/disable command it will be described here.

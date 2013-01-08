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
* Install peewee (easy_install peewee)

## Architecture
At the moment there are 3 files:
* master.py - the server that handles all the client connections and dispatches orders
* client.py - a stupid client that connects to the master and waits for orders
* php_client.php - a test script to talk to the master from a php script (proof of concept for web interface)

Is is possible to connect to the master via telnet using the command `telent localhost 6000`.
A command prompt will appear and it will be possible to talk to the master.

### Immediate future planning
The next milestone for the development is to achive a solid system for enabling and disabling clients (both via command line interface and web interface). This will be achieved in several steps:
* develop a versatile attributes CRUD API for the objects (both via CLI and WI)
* integrate an ORM such as `pewee` for handling a mirrored database with all the clients, jobs, etc
* create the foundation for the web interface and implement the basic client enable and disable features

### About the web interface
The idea is to use a light PHP framework that will allow the user to connect to the master and give inputs. All the database work related to the farm will not be directly accessible by the client. Web interface and master.py will talk to each other via socked using JSON strings.
This allows to keep data centralized and share an API across different interfaces (could be a native iOS/Android application for example).
After some quite intense research the framework of choice is CodeIgniter. A more detailed roadmap for the web interface will be published later on.

## List of commands
No real commands are currently available. At the moment only test inputs are available, but this is a list of possible inputs:
* `clients` - lists all available clients (could support filtering arguments, such as `all`, `enabled`, etc.)
* `enable` (plus filtering arguments) - enables selected clients
* `disable` (plus filtering arguments) - disables selected clients

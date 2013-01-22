brender
=======

Development repo for brender 2.0 (the original version is here https://github.com/oenvoyage/brender)

## Installation
Basic requirement at the moment are:

* Python 2.7
* gevent (awesome lib for concurrency)
* peewee (ORM library)
* PHP 5 (for the web interface)
* Apache (for the web interface)

To install gevent on OSX, check this docs out:

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
The idea is to use a light PHP framework that will allow the user to connect to the master and give inputs. All the database work related to the farm will not be directly accessible by the client. Web interface and master.py will talk to each other via sockets using JSON strings.
This allows to keep data centralized and share an API across different interfaces (could be a native iOS/Android application for example).
After some quite intense research we dropped the idea of using CodeIgniter as a framweork and built ourselves a simpler one. The current framework provides:

* fully configurable url routing
* web interface with dataDables and data loaded via AJAX
* JSON data output (was a pain to get it working)

### How to use the web interface
It's quite simple. The web interface is situated in the folder called `dashboard`. Set the Apache home directory in that folder and you should be able to see it via the web browser. Will add soon a diagram about what each file does.

Frameworks and tools used by the interface are:

* jQuery
* bootstrap
* dataTables 

## Implementation details
Here we explain how the software works in some of its most important parts.

### Startup
Before we start running the server we load from the database a list of clients and run them throug an inizialize_runtime_client function that create the client object we use in the application. These objects are appended to the runtime_clients list. We do this because accessing clients from memory is much faster!

### Client connection
When a client connects we check if it was there before (if it is in the runtime_clients list loaded from the database at startup). If it's there we enable it, if not, we: 

* first create a new entry in the database
* extract the entry and use the id to
* initialize a new runtime_client
* we append the client to the runtime_clients list and use it

### Shutdown
When we shut down brender we must save the current status of the runtime clients in the database. There is a save_to_database function that does that. At the moment that function is very slow, compared to the load_from_database, why? This has to be investigated.


## List of commands
No real commands are currently available. At the moment only test inputs are available, but this is a list of possible inputs:

* `clients` - lists all available clients (could support filtering arguments, such as `all`, `enabled`, etc.)
* `enable` (plus filtering arguments) - enables selected clients
* `disable` (plus filtering arguments) - disables selected clients

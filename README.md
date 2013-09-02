# brender-flask


Development repo for brender 2.0 (the original version is here https://github.com/oenvoyage/brender). This is the Flask-based version, a new direction taken after getting some feedback from Sergey and Keir.

## Developer installation
Basic requirement at the moment are:

* Python 2.7
* Flask
* peewee (ORM library)
* virtualenv (optional)

Following the Flask idea, we install the server, workers and dashboard unsing virtualenv. Text copied from the Flask guide. 

```
$ sudo easy_install virtualenv
```

Once you have virtualenv installed, just fire up a shell and create your own environment. You may want to create this folder inside of the brender folder:

```
$ cd brender
$ virtualenv venv
New python executable in venv/bin/python
Installing distribute............done.
```

Now, whenever you want to work on a project, you only have to activate the corresponding environment. On OS X and Linux, do the following:

```
$ . venv/bin/activate
```

Now you can just enter the following command to get Flask activated in your virtualenv:

```
$ pip install Flask
```

At this point you should install peewee as well:

```
$ easy_install install peewee
```


OUTATED: To install gevent on OSX, check this docs out:

* http://stackoverflow.com/questions/7630388/how-can-i-install-python-library-gevent-on-mac-osx-lion
* Install libevent (brew install libevent)
* Install gevent (easy_install gevent)
* Install peewee (easy_install peewee)

## Architecture
At the moment the content of the `brender` folder is quite messy due to refactoring. The important subfolders are:

* `server` containing the server files
* `worker` containing the worker files (render nodes)
* `dashboard` containing the dashboard (web interface to talk to the server)

This structure explains also the naming conventions adopted to distinguish the different parts of brender. 
Each folder contains an individual Falsk application. Server and Worker exchange JSON formatted message between each other via HTTP, using GET or POST methods.
Dashboard connect to the Server only and accepts connection from clients (Browsers).

At the moment we have the following addresses:

* http://brender-server:9999
* http://localhost:5000
* http://brender-flask 


### About the web interface
The idea is to use a light PHP framework that will allow the user to connect to the master and give inputs. All the database work related to the farm will not be directly accessible by the client. Web interface and master.py will talk to each other via sockets using JSON strings.
This allows to keep data centralized and share an API across different interfaces (could be a native iOS/Android application for example).
After some quite intense research we dropped the idea of using CodeIgniter as a framweork and built ourselves a simpler one. The current framework provides:

* fully configurable url routing
* web interface with dataTables and data loaded via AJAX
* JSON data output (was a pain to get it working because we forgot to close the socket once the query was completed)



Frameworks and tools used by the interface are:

* jQuery
* bootstrap
* dataTables 

## Implementation details
Here we explain how the software works in some of its most important parts.

### Startup
Before we start running the server we load from the database a list of clients and run them through an initialize_runtime_client function that create the client object we use in the application. These objects are appended to the runtime_clients list. We do this because accessing clients from memory is much faster!

### Client connection
When a client connects we check if it was there before (if it is in the runtime_clients list loaded from the database at startup). If it's there we enable it, if not, we: 

* first create a new entry in the database
* extract the entry and use the id to
* initialize a new runtime_client
* we append the client to the runtime_clients list and use it

### Shutdown
When we shut down brender we must save the current status of the runtime clients in the database. There is a save_to_database function that does that. At the moment that function is very slow, compared to the load_from_database, why? This has to be investigated.

### API
The brender API consists in the exchange of JSON strings between a client and the server. At the moment it works like this:

* Open a connection to the server (new socket)
* Send data to the server (as JSON)
* Get response
* Eventually close the connection

We build the JSON request by defining item, action, filter and values. Item and action are mandatory, whereas filter and values depend on the action. Here you have an example:

`{'item': 'client', 'action': 'update', 'filter': 'enabled', 'values': 'disabled'}`

The following table gives a better overview of the JSON string components.

<table>
    <thead>
   		<tr>
        	<th>Key</th>
        	<th>Type</th>
        	<th>Included</th>
        	<th>Example</th>
        </tr>
    </thead>
    <tbody>
    	<tr>
    		<td>item</td>
    		<td>string</td>
    		<td>ALWAYS</td>
    		<td>'clients'</td>
    	</tr>
    	<tr>
    		<td>action</td>
    		<td>string</td>
    		<td>ALWAYS</td>
    		<td>'update'</td>
    	</tr>
    	<tr>
    		<td>filters</td>
    		<td>dictionary</td>
    		<td>Read Update Delete</td>
    		<td>{'status': 'enabled'}</td>
    	</tr>
    	<tr>
    		<td>values</td>
    		<td>dictionary</td>
    		<td>Create Update</td>
    		<td>{'status': 'disabled'}</td>
    	</tr>
    </tbody>
</table>


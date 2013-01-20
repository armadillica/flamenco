#!/usr/bin/env python
"""Simple server

Connect to it with:
  telnet localhost 6000

"""
from gevent.server import StreamServer
from gevent.pool import Pool
import time
from brender import *
from model import *


# we set a pool to allow max 100 clients to connect to the server
pool = Pool(100)

# clients list that gets edited for every client connection and disconnection
# we will load this list from our database at startup and edit it at runtime
# TODO (fsiddi): implement what said above
clients_list = []
job_list = ['a', 'b', 'c']
client_index = 0

class Client(object):
	"""A client object will be instanced everytime this class is called.
	
	This is an important building block of brender. All the methods avalialbe
	here will be calling some model method (from specific classes). For the
	moment we do this internally. Methods that need implementation are:
	
	* set/get client status
	* start/pause/stop order
	* get render status
	* get various client information (such as hostname or memory usage)
	
	"""
	hostname = 'hostname' # provided by the client
	socket = 'socket' # provided by gevent at the handler creation
	status = 'enabled' # can be enabled, disabled, stopped
	mac_address = 0
	warning = False

	def __init__(self, **kwargs): # the constructor function called when object is created
		self._attributes = kwargs
	
	def set_attributes(self, key, value): # accessor Method
		self._attributes[key] = value
		return

	def get_attributes(self, key):
		return self._attributes.get(key, None)

	def is_online(self): # self is a reference to the object
		if self._attributes['socket'] == False:
			return 'Offline'
		else:
			return 'Online'

	def __hiddenMethod(self): # a hidden method
		print "Hard to Find"
		return


def client_select(key, value):
	"""Selects a client from the list.
	
	This is meant to be a general purpose method to be called in any other method
	that addresses a specific client.
	
	"""
	selected_clients = []
	d_print("Looking for client with %s: %s" % (key, value))
	for client in clients_list:
		if client.get_attributes(key) == value:
			# we only return the first match, maybe this is not ideal
			selected_clients.append(client)
		else:
			pass

	if len(selected_clients) > 0:
		return selected_clients
	else:
		print("[Warning] No client in the list matches the selection criteria")
		return False


def set_client_attribute(*attributes):
	"""Set attributes of a connected client
	
	This function accepts tuples as arguments. At the moment only two tuples
	are supported as input. See an example here:

	set_client_attribute(('status', 'disabled'), ('status', 'enabled'))
	set_client_attribute(('hostname', command[1]), ('status', 'disabled'))

	The first tuple is used for selecting one (and in the future more) clients
	from the clients_list and the second one sets the attributes to the
	selected client.
	Tis function makes use of the client_select function above and is limited
	by its functionality.

	"""

	selection_attribute = attributes[0]
	d_print('selection ' + selection_attribute[0] + " " + selection_attribute[1])
	target_attribute = attributes[1]
	d_print('target ' + target_attribute[0])
	client = client_select(selection_attribute[0], 
							selection_attribute[1]) # get the client object
	

	if (client):
		for c in client:
			c.set_attributes(target_attribute[0],
									target_attribute[1])

			print('setting %s for client %s to %s' % (
				target_attribute[0], 
				c.get_attributes('hostname'), 
				target_attribute[1]))
		return
	else:
		print("[Warning] The command failed")


def initialize_runtime_client(db_client):
	client = Client(id = db_client.id,
		hostname = db_client.hostname,
		mac_address = db_client.mac_address,
		socket = False,
		status = db_client.status,
		warning = db_client.warning,
		config = db_client.config)
	return client


def load_from_database():
	clients_database_list = load_clients()
	for db_client in clients_database_list:
			clients_list.append(initialize_runtime_client(db_client))
	print("[boot] " + str(len(clients_database_list)) + " clients loaded from database")
	return

def add_client_to_database(new_client_attributes):
	print("Adding a new client to the database")
	return initialize_runtime_client(create_client(new_client_attributes))


def save_to_database():
	for client in clients_list:
		save_runtime_client(client)
	print(str(len(clients_list)) + " clients saved successfully")


def LookForJobs():
	"""This is just testing code that never runs"""
	
	time.sleep(1)
	print('1\n')
	time.sleep(1)
	print('2\n')
	if len(job_list) > 0:
		print('removed job ' + str(job_list[0]))
		job_list.remove(job_list[0])
		return('next')
	else:
		print('no jobs at the moment')
		return('done')


# this handler will be run for each incoming connection in a dedicated greenlet
def handle(socket, address):
	print ('New connection from %s:%s' % address)
	# using a makefile because we want to use readline()
	fileobj = socket.makefile()	
	while True:
		line = fileobj.readline().strip()
				
		if line.lower() == 'identify_client':
			# we want to know if the cliend connected before
			fileobj.write('mac_addr')
			fileobj.flush()
			d_print("Waiting for mac address")
			line = fileobj.readline().strip().split()
			
			# if the client was connected in the past, there should be an instanced
			# object in the clients_list[]. We access it and set the is_online
			# variable to True, to make it run and accept incoming orders.
			# Since the client_select methog returns a list we have to select the
			# first and only item in order to make it work (that's why we have the
			# trailing [0] in the selection query for the mac_address here)
			
			client = client_select('mac_address', int(line[0]))[0]
			
			if client:
				d_print('This client connected before')
				client.set_attributes('socket', socket)
				
			else:
				d_print('This client never connected before')
				# create new client object with some defaults. Later on most of these
				# values will be passed as JSON object during the first connection
				new_client_attributes = {
					'hostname': line[1], 
					'mac_address': line[0], 
					'status': 'enabled', 
					'warning': False, 
					'config': 'bla'
				}

				client = add_client_to_database(new_client_attributes)
			
				# we assign the socket to the client and append it to the list
				client.set_attributes('socket', socket)
				clients_list.append(client)

			#d_print ('the socket for the client is: ' + str(client.get_attributes('socket')))
			#print ("the id for the client is: " + str(client.get_attributes('id')))
			while True:
				d_print('Client ' + str(client.get_attributes('hostname')) + ' is waiting')
				line = fileobj.readline().strip()
				if line.lower() == 'ready':
					print('Client is ready for a job')
					#if LookForJobs() == 'next':
					#	socket.send('done')
				else:
					print('break')
					clients_list.remove(client)
					break
					
		if line.lower() == 'clients':
			print('[<-] Sending list of clients to interface')
			for client in clients_list:
				list_of_clients = client.get_attributes('hostname') + " " + client.is_online()
				d_print(list_of_clients)
				fileobj.write(list_of_clients + '\n')
			fileobj.flush()
		
		elif line.lower().startswith('disable'):
			command = line.split()
			if len(command) > 1:
				if command[1] == 'ALL':
					set_client_attribute(('status', 'enabled'), ('status', 'disabled'))
				else:
					print(command[1])
					set_client_attribute(('hostname', command[1]), ('status', 'disabled'))
			else:
				fileobj.write('[Warning] No client selected. Specify a '
					'client name or use the \'ALL\' argument.\n')

		elif line.lower().startswith('enable'): # Here we have a lot of code duplication!
			command = line.split()
			if len(command) > 1:
				if command[1] == 'ALL':
					set_client_attribute(('status', 'disabled'), ('status', 'enabled'))
				else:
					#print(command[1])
					set_client_attribute(('hostname', command[1]), ('status', 'enabled'))
			else:
				fileobj.write('[Warning] No client selected. Specify a '
					'client name or use the \'ALL\' argument.\n')
				
		elif line.lower() == 'test':
			fileobj.write('test>')
		
		elif line.lower() == 'b':
			clients_list[0].send('command')
			
		elif line.lower() == 'k':
			clients_list[0].send('kill')

		elif line.lower() == 'save':
			save_to_database()
		
		elif line.lower() == 'quit':
			print('[x] Closed connection from %s:%s' % address)
			break
			
		elif not line:
			print ('[x] Client disconnected')
			break
		
		#print("line is " + line)
		#fileobj.write('> ')
		fileobj.flush()
		#print("done with the loop")
		#time.sleep(1)
		

if __name__ == '__main__':
	try:
		# we load the clients from the database into the list as objects
		print("[boot] Loading clients from database")
		load_from_database()
		# to make the server use SSL, pass certfile and keyfile arguments to the constructor
		server = StreamServer(('0.0.0.0', 6000), handle, spawn=pool)
		# to start the server asynchronously, use its start() method;
		# we use blocking serve_forever() here because we have no other jobs
		print ('[boot] Starting echo server on port 6000')
		server.serve_forever()
	except KeyboardInterrupt:
		save_to_database()
		print(" Quitting brender")
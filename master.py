#!/usr/bin/env python
"""Simple server

Connect to it with:
  telnet localhost 6000

"""
from gevent.server import StreamServer
from gevent.pool import Pool
import time
from brender import *

# we set a pool to allow max 100 clients to connect to the server
pool = Pool(100)

# clients list that gets edited for every cliend connection and disconnection
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
	
	"""
	__hostname = 'hostname' # provided by the client
	__socket = 'socket' # provided by gevent at the handler creation
	__status = 'enabled' # can be enabled, disabled, stopped
	__mac_address = 0
	__warning = False
	__is_online = False

	def __init__(self, **kwargs): # the constructor function called when object is created
		self._attributes = kwargs
	
	def set_attributes(self, key, value): # accessor Method
		self._attributes[key] = value
		return

	def get_attributes(self, key):
		return self._attributes.get(key, None)

	def say_hello(self): # self is a reference to the object
		print("hello") # you use self so you can access attributes of the object
		return

	def __hiddenMethod(self): # a hidden method
		print "Hard to Find"
		return


def client_select(key, value):
	"""Selects a client from the list.
	
	This is meant to be a general purpose method to be called in any other method
	that addresses a specific client.
	
	"""
	d_print("Looking for client with %s: %s" % (key, value))
	for client in clients_list:
		if client.get_attributes(key) == value:
			# we only return the first match, maybe this is not ideal
			return client
		else:
			print("no such client exists")
			return False
	d_print("[Warning] No client found")
	return False


def set_client_attribute(*attributes):
	"""Set attributes of a connected client
			
	set_client_attribute(('__status', 'disabled'), ('__status', 'enabled'))
	set_client_attribute(('__hostname', command[1]), ('__status', 'disabled'))

	"""

	selection_attribute = attributes[0]
	d_print('selection ' + selection_attribute[0] + " " + selection_attribute[1])
	target_attribute = attributes[1]
	d_print('target ' + target_attribute[0])
	client = client_select(selection_attribute[0], 
							selection_attribute[1]) # get the client object
								
	client.set_attributes(target_attribute[0],
							target_attribute[1])

	print('setting %s for client %s to %s' % (
		target_attribute[0], 
		client.get_attributes('__hostname'), 
		target_attribute[1]))
	return

		
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
			line = fileobj.readline().strip()
			
			# if the client was connected in the past, there should be an instanced
			# object in the clients_list[]. We access it and set the __is_online
			# variable to True, to make it run and accept incoming orders
			
			client = client_select('__mac_address', line)
			
			if client:
				d_print('This client connected before')
				client.set_attributes('__is_online', True)
				
			else:
				d_print('This client never connected before')
				# create new client object with some defaults. Later on most of these
				# values will be passed as JSON object during the first connection
				client = Client(__hostname = 'me',
								__mac_address = line,
								__socket = socket,
								__status = 'enabled',
								__warning = False,
								__is_online = True)
				# and append it to the list
				clients_list.append(client)

			#d_print ('the socket for the client is: ' + str(client.get_attributes('__socket')))
			#print ("the id for the client is: " + str(client.get_attributes('__id')))
			while True:
				d_print('Client ' + str(client.get_attributes('__hostname')) + ' is waiting')
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
			print('Sending list of clients to interface')
			for client in clients_list:
				print(client.get_attributes('__hostname'))
				fileobj.write(str(client) + '\n')
			fileobj.flush()
		
		elif line.lower().startswith('disable'):
			command = line.split()
			if len(command) > 1:
				if command[1] == 'ALL':
					set_client_attribute(('__status', 'disabled'), ('__status', 'disabled'))
				else:
					print(command[1])
					set_client_attribute(('__hostname', command[1]), ('__status', 'disabled'))
			else:
				fileobj.write('[Warning] No client selected\n')
				
		elif line.lower() == 'test':
			fileobj.write('test>')
		
		elif line.lower() == 'b':
			clients_list[0].send('command')
			
		elif line.lower() == 'k':
			clients_list[0].send('kill')
		
		elif line.lower() == 'quit':
			print('Closed connection from %s:%s' % address)
			break
			
		elif not line:
			print ('Client disconnected')
			break
		
		#print("line is " + line)
		fileobj.write('> ')
		fileobj.flush()
		#print("done with the loop")
		#time.sleep(1)
		

if __name__ == '__main__':
	# we load the clients from the database into the list as objects
	print("[boot] Loading clients from database")
	# to make the server use SSL, pass certfile and keyfile arguments to the constructor
	server = StreamServer(('0.0.0.0', 6000), handle, spawn=pool)
	# to start the server asynchronously, use its start() method;
	# we use blocking serve_forever() here because we have no other jobs
	print ('[boot] Starting echo server on port 6000')
	server.serve_forever()
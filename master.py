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

# slaves list that gets edited for every cliend connection and disconnection
# we will load this list from our database at startup and edit it at runtime
# TODO (fsiddi): implement what said above
slaves_list = []
job_list = ['a', 'b', 'c']
client_index = 0

class Slave(object):
	"""A slave object will be instanced everytime this class is called.
	
	This is an important building block of brender. All the methods avalialbe
	here will be calling some model method (from specific classes). For the
	moment we do this internally. Methods that need implementation are:
	
	* set/get slave status
	* start/pause/stop order
	
	"""
	__hostname = "hostname" # provided by the client
	__socket = "socket" # provided by gevent at the handler creation
	__status = "active" # can be active, inactive, stopped
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


def slave_select(key, value):
	"""Selects a slave from the list.
	
	This is meant to be a general purpose method to be called in any other method
	that addresses a specific client.
	
	"""
	d_print("Looking for client with %s: %s" % (key, value))
	for slave in slaves_list:
		if slave.get_attributes(key) == value:
			# we only return the first match, maybe this is not ideal
			return slave
		else:
			print('no such slave exists')
			return False
	d_print("No client found")
	return False


def set_slave_status(key, value, status):
	"""Set status of a connected slave"""
	
	slave = slave_select(key, value) # get the slave object
	slave.set_attributes('__status', status)
	print('setting status for client %s to %s' % (slave.get_attributes('__hostname'), status))
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


def LookForTasks():
	"""This is just testing code that never runs"""
	
	return 10


# this handler will be run for each incoming connection in a dedicated greenlet

def handle(socket, address):
	print ('New connection from %s:%s' % address)
	# using a makefile because we want to use readline()
	fileobj = socket.makefile()	
	while True:
		line = fileobj.readline().strip()
				
		if line.lower() == 'identify_slave':
			# we want to know if the cliend connected before
			fileobj.write('mac_addr')
			fileobj.flush()
			d_print("Waiting for mac address")
			line = fileobj.readline().strip()
			
			# if the client was connected in the past, there should be an instanced
			# object in the slaves_list[]. We access it and set the __is_online
			# variable to True, to make it run and accept incoming orders
			
			slave = slave_select('__mac_address', line)
			print (slave)
			
			if slave:
				d_print('This client connected before')
				slave.set_attributes('__is_online', True)
				
			else:
				d_print('This client never connected before')
				# create new client object with some defaults. Later on most of these
				# values will be passed as JSON object during the first connection
				slave = Slave(__socket = socket, 
								__status = 'active', 
								__is_online = True,
								__hostname = 'no hostname set')
				# and append it to the list
				slaves_list.append(slave)

			#d_print ('the socket for the client is: ' + str(slave.get_attributes('__socket')))
			#print ("the id for the client is: " + str(slave.get_attributes('__id')))
			while True:
				d_print('client ' + str(slave.get_attributes('__hostname')) + ' is waiting')
				line = fileobj.readline().strip()
				if line.lower() == 'ready':
					print('client is ready for a job')
					#if LookForJobs() == 'next':
					#	socket.send('done')
				else:
					print('break')
					slaves_list.remove(slave)
					break
					
		if line.lower() == 'slaves':
			print('Sending list of slaves to interface')
			for slave in slaves_list:
				print(slave.get_attributes('__hostname'))
				fileobj.write(str(slave) + '\n')
			fileobj.flush()
		
		elif line.lower() == 'disable':
			set_slave_status(1, 'inactive')
		
		elif line.lower() == 'test':
			fileobj.write('test>')
		
		elif line.lower() == 'b':
			slaves_list[0].send('command')
			
		elif line.lower() == 'k':
			slaves_list[0].send('kill')
		
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
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

class Slave:
	
	__hostname = "hostname"
	__socket = "socket"
	__status = "active"

	def __init__(self, **kvargs): # The constructor function called when object is created
		self._attributes = kvargs

	def set_attributes(self, key, value): # Accessor Method
		self._attributes[key] = value
		return

	def get_attributes(self, key):
		return self._attributes.get(key, None)

	def say_hello(self): # self is a reference to the object
		print("hello") # You use self so you can access attributes of the object
		return

	def __hiddenMethod(self): # A hidden method
		print "Hard to Find"
		return
		
def LookForJobs():
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
	return 10


# this handler will be run for each incoming connection in a dedicated greenlet
def handle(socket, address):
	print ('New connection from %s:%s' % address)
	# using a makefile because we want to use readline()
	fileobj = socket.makefile()	
	while True:
		line = fileobj.readline().strip()

		d_print (line)
		
		if line.lower() == 'identify_slave':
			#slaves_list.append(socket)
			slave = Slave()
			slaves_list.append(slave)
			slave.set_attributes('__socket', socket)
			slave.set_attributes('__hostname', 'the hostname')
			print ('the socket for the client is: ' + str(slave.get_attributes('__socket')))
			while True:
				print('client ' + str(socket) + ' is waiting')
				line = fileobj.readline().strip()
				if line.lower() == 'ready':
					print('ready for a job')
					#if LookForJobs() == 'next':
					#	socket.send('done')
				else:
					print('break')
					#slaves_list.remove(socket)
					slaves_list.remove(slave)
					break
					
		if line.lower() == 'slaves':
			print('Sending list of slaves to client')
			for slave in slaves_list:
				print(slave.get_attributes('__hostname'))
				fileobj.write(str(slave) + '\n')
			fileobj.flush()
		
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
	# to make the server use SSL, pass certfile and keyfile arguments to the constructor
	server = StreamServer(('0.0.0.0', 6000), handle, spawn=pool)
	# to start the server asynchronously, use its start() method;
	# we use blocking serve_forever() here because we have no other jobs
	print ('Starting echo server on port 6000')
	d_print ('test')
	server.serve_forever()
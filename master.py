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
slave_list = []
job_list = ['a', 'b', 'c']

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
	# socket.sendall('who are you')
	# using a makefile because we want to use readline()
	fileobj = socket.makefile()	
	while True:
		line = fileobj.readline().strip()

		d_print (line)
		
		if line.lower() == 'identify_slave':
			slave_list.append(socket)
			while True:
				print('client ' + str(socket) + ' is waiting')
				line = fileobj.readline().strip()
				if line.lower() == 'ready':
					print('ready for a job')
					#if LookForJobs() == 'next':
					#	socket.send('done')
				else:
					print('break')
					slave_list.remove(socket)
					break
					
		if line.lower() == 'slaves':
			print('Sending list of slaves')
			for slave in slave_list:
				fileobj.write(str(slave) + '\n')
			fileobj.flush()
		
		elif line.lower() == 'test':
			fileobj.write('test>')
		
		elif line.lower() == 'b':
			slave_list[0].send('command')
			
		elif line.lower() == 'k':
			slave_list[0].send('kill')
		
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
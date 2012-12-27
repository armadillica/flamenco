#!/usr/bin/env python
"""Simple server that listens on port 6000 and echos back every input to the client.

Connect to it with:
  telnet localhost 6000

Terminate the connection by terminating telnet (typically Ctrl-] and then 'quit').
"""
from gevent.server import StreamServer
import time


# this handler will be run for each incoming connection in a dedicated greenlet
def echo(socket, address):
	print ('New connection from %s:%s' % address)
	socket.sendall('who are you')
	print("we listen")
	data = socket.recv(2048)
	print("data " + data)
	# using a makefile because we want to use readline()
	while True:
		data = socket.recv(2048)
		if not data: 
			break
		else:
			print ("s")
		print("true loop")
		socket.sendall('command')
		time.sleep(1)



if __name__ == '__main__':
	# to make the server use SSL, pass certfile and keyfile arguments to the constructor
	server = StreamServer(('0.0.0.0', 6000), echo)
	# to start the server asynchronously, use its start() method;
	# we use blocking serve_forever() here because we have no other jobs
	print ('Starting echo server on port 6000')
	server.serve_forever()
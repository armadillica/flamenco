#!/usr/bin/env python
"""Simple client

The guy connects to the server and gets order from it. As soon as it gets
an order, if needed, it forks a process to run the desired command. This
way the communication channel with the server stays clean and it'server_socket always
possible to send other commands to the client. Some example commands that
need to be implemented.

* Enable/Disable client
* Execute order (like render frames chunk)
* Check client status
* Check order status
* Pause/Resume order
* Kill order

"""
import socket
import sys
import os
import time
import json
from uuid import getnode as get_mac
from brender import *


HOST = 'localhost'  # the remote host
PORT = 6000  # the same port as used by the server
server_socket = None
MAC_ADDR = get_mac()  # the MAC address of the client
HOSTNAME = socket.gethostname()

# we create the socket to connect to the server
for res in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM):
	af, socktype, proto, canonname, sa = res
	try:
		server_socket = socket.socket(af, socktype, proto)
	except socket.error as msg:
		server_socket = None
		continue
	try:
		server_socket.connect(sa)
	except socket.error as msg:
		server_socket.close()
		server_socket = None
		continue
	break

if server_socket is None:
	print('[error] Could not open socket: is the server running?')
	sys.exit(1)

try:
	# socket is now open and we identify as clients
	server_socket.send('identify_client\n')
	print('[info] Identifying as client with hostname: %server_socket' % (str(HOSTNAME)))
	d_print('Waiting for response')
	line = server_socket.recv(4096)
	if line == 'mac_addr':
		d_print('Sending MAC address')
		server_socket.send(str(MAC_ADDR) + ' ' + str(HOSTNAME) + '\n')
	else:
		print('[error] The identification procedure failed somehow')

	# we enter the main loop where we listen/reply to the server messages.
	while True:
		server_socket.send('ready\n')
		# we wait for an order (recv is blocking)
		print('Waiting...')
		line = server_socket.recv(4096)
		
		# we print the incoming command and then evalutate it
		print ('[info] Server said ' + str(line))
		if line == 'command':
			print('We will run commands here')
			
		elif line == 'mac_addr':
			server_socket.send(str(MAC_ADDR) + '\n')
			
		elif line == 'kill':
			server_socket.send('quit\n')
			time.sleep(2)
			sys.exit(0)

		elif line.startswith('{'):
			order = json.loads(line)

			if order['is_final'] == True:
				server_socket.send('finished\n')

			else:
				server_socket.send('busy\n')
			
		else:
			print('[info] Other command came in')	
			time.sleep(1)
			server_socket.send('busy\n')

except KeyboardInterrupt:
	print('\n')
	print('[shutdown] Quitting client')


#!/usr/bin/env python
"""Simple client

The client connects to the server and gets order from it. As soon as it gets
an order, if needed, it forks a process to run the desired command. This
way the communication channel with the server stays clean and it's always
possible to send other commands to the client. Some example commands that
need to be implemented.

* Enable/Disable client
* Execute order (like render a chunk of frames)
* Parse software log when rendering and store it
* Process image output to generate thumbnails
* Upload data to a shared folder (secure server, LAN, ect)
* Check client status
* Check order status
* Pause/Resume order (like pause the actual process - PID)
* Kill order

This client could be run as some sort of 'daemon', started as soon as the
operating system is booted.

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

	# we get a JSON string command for identification
	order = json.loads(line)
	if order['command'] == 'mac_address':
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

		# we make sure we are getting a JSON sring
		try:
			order = json.loads(line)
		except:
			break
		

		if order['type'] == 'system':
			if order['command'] == 'mac_addr':
				server_socket.send(str(MAC_ADDR) + '\n')
			
			elif order['command'] == 'kill':
				server_socket.send('quit\n')
				time.sleep(2)
				sys.exit(0)

		elif order['type'] == 'render':
			current_frame = order['current_frame']
			print current_frame, order['chunk_end']
			while current_frame < order['chunk_end'] + 1:
				print current_frame
				current_frame = current_frame + 1
				server_socket.send('busy\n')

			d_print(str(order['is_final']))

			if order['is_final'] == False:
				server_socket.send('chunk_finished\n')
			else:
				server_socket.send('job_finished\n')
				print('[info] The job has been completed')
			
		else:
			print('[info] Other command came in')	
			time.sleep(1)
			server_socket.send('busy\n')

except KeyboardInterrupt:
	print('\n')
	print('[shutdown] Quitting client')


#!/usr/bin/env python
"""Simple client

The guy connects to the server and gets order from it. As soon as it gets
an order, if needed, it forks a process to run the desired command. This
way the communication channel with the server stays clean and it's always
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
from uuid import getnode as get_mac
from brender import *


HOST = 'localhost'  # the remote host
PORT = 6000  # the same port as used by the server
s = None
MAC_ADDR = get_mac()  # the MAC address of the client
HOSTNAME = socket.gethostname()

# we create the socket to connect to the server
for res in socket.getaddrinfo(HOST, PORT, socket.AF_UNSPEC, socket.SOCK_STREAM):
	af, socktype, proto, canonname, sa = res
	try:
		s = socket.socket(af, socktype, proto)
	except socket.error as msg:
		s = None
		continue
	try:
		s.connect(sa)
	except socket.error as msg:
		s.close()
		s = None
		continue
	break

if s is None:
	print('[Error] Could not open socket')
	sys.exit(1)
	
# socket is now open and we identify as clients
s.send('identify_client\n')
print("identifying as client with hostname: %s" % (str(HOSTNAME)))
d_print("Waiting for response")
line = s.recv(4096)
if line == 'mac_addr':
	d_print("Sending MAC address")
	s.send(str(MAC_ADDR) + ' ' + str(HOSTNAME) + '\n')
else:
	print("[Error] The identification procedure failed somehow")

# we enter the main loop where we listen/reply to the server messages.
while True:
	s.send("ready\n")
	# we wait for an order (recv is blocking)
	print("waiting...")
	line = s.recv(4096)
	
	# we print the incoming command and then evalutate it
	print ("master said " + str(line))
	if line == 'command':
		print('We will run commands here')
		
	elif line == 'mac_addr':
		s.send(str(MAC_ADDR) + '\n')
		
	elif line == 'kill':
		s.send("quit\n")
		time.sleep(2)
		sys.exit(0)
		
	else:
		print('other command came in')	


#!/usr/bin/env python
"""Simple slave

The guy connects to the server and gets order from it. As soon as it gets
an order, if needed, it forks a process to run the desired command. This
way the communication channel with the server stays clean and it's always
possible to send other commands to the slave. Some example commands that
need to be implemented.

* Enable/Disable slave
* Execute order (like render frames chunk)
* Check slave status
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
MAC_ADDR = get_mac()  # the MAC address of the slave
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
	print('could not open socket')
	sys.exit(1)
	
# socket is now open and we identify as slaves
s.send('identify_slave\n')
print('identifying as slave with hostname: %s' % (str(HOSTNAME)))
d_print('we should be waiting')
line = s.recv(4096)
if line == 'mac_addr':
	d_print("we got " + line)
	s.send((str(MAC_ADDR) + '\n'))
else:
	print('dasd')

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
		s.send((str(MAC_ADDR) + '\n'))
		
	elif line == 'kill':
		s.send("quit\n")
		time.sleep(2)
		sys.exit(0)
		
	else:
		print('other command came in')	


# Echo client program
import socket
import sys
import os
import time

HOST = 'localhost'    # The remote host
PORT = 6000              # The same port as used by the server
s = None
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
	
## socket is now open
s.send('identify_slave\n')
print('identify as slave')

while True:
	s.send("ready\n")
	## we wait for an order (recv is blocking)
	print("waiting...")
	line = s.recv(4096)
	
	## we print the incoming command and then evalutate it
	print ("master said " + str(line))
	if line == 'command':
		print('awesome')
	elif line == 'kill':
		s.send("quit\n")
		time.sleep(2)
		break
	else:
		print('other command came in')	


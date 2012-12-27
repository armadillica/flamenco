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
	
# socket is now open
s.send("identify_client\n")

while True:
	s.send("app\n")
	#break
	print("waiting...")
	line = s.recv(4096)
	print (line)
	


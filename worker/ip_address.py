import socket
print socket.gethostname()
print socket.gethostbyname(socket.gethostname() + '.local')

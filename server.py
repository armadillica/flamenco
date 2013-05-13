#!/usr/bin/env python
"""Simple server

Connect to it with:
  telnet localhost 6000

"""
from gevent.server import StreamServer
from gevent.pool import Pool
import time
import json
from brender import *
from model import *


# we set a pool to allow max 100 clients to connect to the server
pool = Pool(100)

# clients list that gets edited for every client connection and disconnection
# we will load this list from our database at startup and edit it at runtime
# TODO (fsiddi): implement what said above
clients_list = []
job_list = ['a', 'b', 'c']
client_index = 0

class Client(object):
	"""A client object will be instanced everytime this class is called.
	
	This is an important building block of brender. All the methods avalialbe
	here will be calling some model method (from specific classes). For the
	moment we do this internally. Methods that need implementation are:
	
	* set/get client status
	* start/pause/stop order
	* get render status
	* get various client information (such as hostname or memory usage)
	
	"""
	hostname = 'hostname' # provided by the client
	socket = 'socket' # provided by gevent at the handler creation
	status = 'enabled' # can be enabled or disabled
	mac_address = 0
	warning = False

	def __init__(self, **kwargs): # the constructor function called when object is created
		self._attributes = kwargs
	
	def set_attributes(self, key, value): # accessor Method
		self._attributes[key] = value
		return

	def get_attributes(self, key):
		return self._attributes.get(key, None)

	def get_status(self): # self is a reference to the object
		if self._attributes['socket'] == False:
			return 'offline'
		else:
			return 'online'

	def __hiddenMethod(self): # a hidden method
		print "Hard to Find"
		return


def client_select(key, value):
	"""Selects a client from the list.
	
	This is meant to be a general purpose method to be called in any other method
	that addresses a specific client.
	
	"""
	selected_clients = []
	d_print("Looking for client with %s: %s" % (key, value))
	for client in clients_list:
		if client.get_attributes(key) == value:
			# we only return the first match, maybe this is not ideal
			selected_clients.append(client)
		else:
			pass

	if len(selected_clients) > 0:
		return selected_clients
	else:
		print("[Warning] No client in the list matches the selection criteria")
		return False


def set_client_attribute(*attributes):
	"""Set attributes of a connected client
	
	This function accepts tuples as arguments. At the moment only two tuples
	are supported as input. See an example here:

	set_client_attribute(('status', 'disabled'), ('status', 'enabled'))
	set_client_attribute(('hostname', command[1]), ('status', 'disabled'))

	The first tuple is used for selecting one (and in the future more) clients
	from the clients_list and the second one sets the attributes to the
	selected client.
	Tis function makes use of the client_select function above and is limited
	by its functionality.

	"""

	selection_attribute = attributes[0]
	d_print('selection ' + selection_attribute[0] + " " + str(selection_attribute[1]))
	target_attribute = attributes[1]
	d_print('target ' + target_attribute[0])
	client = client_select(selection_attribute[0], 
							selection_attribute[1]) # get the client object
	
	if (client):
		for c in client:
			c.set_attributes(target_attribute[0],
									target_attribute[1])

			print('setting %s for client %s to %s' % (
				target_attribute[0], 
				c.get_attributes('hostname'), 
				target_attribute[1]))
		return
	else:
		print("[Warning] The command failed")


def json_io(fileobj, json_input):

	# d_print(str(json_input))

	# we are going to check for the keys in the json_input. Based on that,
	# we initialize the variables needed to run the actual commands
	"""
	This code tries to be too smart at the moment.

	for key in json_input.keys():
		if key == 'item':
			item = json_input['item']
		elif key == 'action':
			action = json_input['action']
		elif key == 'filters':
			filters = json_input['filters']
		elif key == 'values':
			values = json_input['values']
		else:
			d_print("[Warning] Unkown keys injected!")
	"""

	item = json_input['item']
	action = json_input['action']
	filters = json_input['filters']
	values = json_input['values']

	if item == 'client':
		if action == 'read':
			if len(filters) == 0:
				# assume parameter is 'all'
				print('[<-] Sending list of clients to interface')
				table_rows = []
				for client in clients_list:
					connection = client.get_status()
					table_rows.append({
						"DT_RowId": "client_" + str(client.get_attributes('id')),
						"DT_RowClass": connection,
						"0" : client.get_attributes('hostname'),
						"1" : client.get_attributes('status'),
						"2" : connection})
				table_data = json.dumps(json_output('dataTable', table_rows))
				fileobj.write(table_data + '\n')
				fileobj.flush()
				fileobj.close() # very important, otherwise PHP does not get EOF

			else:
				for key in filters:
					pass # do the filtering
		elif action == 'create':
			d_print("[Error] Can't perform this action via JSON")
			pass
			if key in values:
				pass # use the settings
		elif action == 'delete':
			if len(filters) == 0:
				pass # assume parameter is 'all'
			else:
				for key in filters:
					pass # do the filtering and KILL THEM
		elif action == 'update':
			if len(filters) == 0:
				pass # assume parameter is 'all'
				filters_key = 'status'
				filters_value = 'enabled'
			else:
				if len(filters.keys()) == 1:
					filters_key = filters.keys()[0]
					filters_value = filters[filters_key]
				else:
					for key in filters.keys():
						pass # do the filtering

			if len(values) == 0:
				pass # FAIL
			else:
				if len(values.keys()) == 1:
					values_key = values.keys()[0]
					values_value = values[values_key]
				else:
					for key in values.keys():
						pass # do the filtering

			#print (values_key, values_value, filters_key,filters_value)
			set_client_attribute((filters_key, filters_value), (values_key, values_value))



	elif item == 'brender_server':
		pass


	elif item == 'project':
		if action == 'create':
			if len(values) > 0:
				Projects.create(
					name = values['name'],
					description = values['description'],
					project_path = values['project_path'],
					render_output_path = values['render_output_path'],
					render_engine_path = values['render_engine_path'],
					is_active = values['is_active'],
					settings = values['settings'])
			else:
				pass
		elif action == 'read':
			if len(filters) == 0:
				# assume parameter is 'all'
				print('[<-] Sending list of projects to interface')
				table_rows = []
				for project in Projects.select():
					table_rows.append({
					"DT_RowId": project.id,
					"DT_RowClass": project.is_active,
					"0" : project.name,
					"1" : project.description,
					"2" : project.settings,
					"3" : project.is_active})
				table_data = json.dumps(json_output('dataTable', table_rows))
				fileobj.write(table_data + '\n')
				fileobj.flush()
				fileobj.close() # very important, otherwise PHP does not get EOF
		elif action == 'update':
			if len(values) > 0:
				if len(filters) > 0:
					pass
				else: 
					pass # apply to all

			else:
				pass #can't update with not new values!
		elif action == 'delete':
			pass
		else:
			pass


	elif item == 'sequence':
		if action == 'create':
			if len(values) > 0:
				Sequences.create(
					project = values['fk_project'],
					name = values['name'],
					description = values['description'])
				print ("[info] Sequence %s created" % (values['name']))
			else:
				pass
		elif action == 'read':
			if len(filters) == 0:
				# assume parameter is 'all'
				print('[<-] Sending list of sequences to interface')
				table_rows = []
				for sequence in Sequences.select():
					table_rows.append({"DT_RowId": sequence.id,
					"0" : sequence.project.name,
					"1" : sequence.name,
					"2" : sequence.description})
				table_data = json.dumps(json_output('dataTable', table_rows))
				fileobj.write(table_data + '\n')
				fileobj.flush()
				fileobj.close() # very important, otherwise PHP does not get EOF
		elif action == 'update':
			if len(values) > 0:
				if len(filters) > 0:
					pass
				else: 
					pass # apply to all

			else:
				pass #can't update with not new values!
		elif action == 'delete':
			pass
		else:
			pass


	elif item == 'shot':
		if action == 'create':
			if len(values) > 0:
				Shots.create(
					sequence = values['fk_sequence'],
					name = values['name'],
					description = values['description'],
					frame_start = values['frame_start'],
					frame_end = values['frame_end'],
					chunk_size = values['chunk_size'],
					settings = values['settings'],
					stage = values['stage'],
					notes = values['notes'],
					status = values['status'])
				print ("[info] Shot %s created" % (values['name']))
			else:
				pass
		elif action == 'read':
			if len(filters) == 0:
				# assume parameter is 'all'
				print('[<-] Sending list of shots to interface')
				table_rows = []
				for shot in Shots.select():
					table_rows.append({"DT_RowId": shot.id,
					"0" : shot.sequence.name,
					"1" : shot.name,
					"2" : shot.description,
					"3" : shot.status,
					"4" : shot.stage,
					"5" : shot.notes})
				table_data = json.dumps(json_output('dataTable', table_rows))
				fileobj.write(table_data + '\n')
				fileobj.flush()
				fileobj.close() # very important, otherwise PHP does not get EOF
		elif action == 'update':
			if len(values) > 0:
				if len(filters) > 0:
					pass
				else: 
					pass # apply to all

			else:
				pass #can't update with not new values!
		elif action == 'delete':
			pass
		else:
			pass


	elif item == 'job':
		if action == 'create':
			if len(values) > 0:	
				Jobs.create(
					shot = 1,
					frame_start = 2,
					frame_end = 50,
					chunk_size = 5,
					current_frame = 2,
					filepath = 'path',
					render_settings = 'will refer to settins table',
					status = 'running',
					priority = 10,
					owner = 'fsiddi')
				print ("[info] Shot %s created" % (values['name']))
			else:
				pass
		elif action == 'read':
			if len(filters) == 0:
				# assume parameter is 'all'
				print('[<-] Sending list of jobs to interface')
				table_rows = []
				for job in Jobs.select():
					table_rows.append({"DT_RowId": job.id,
					"0" : job.shot.name,
					"1" : job.frame_start,
					"2" : job.frame_end,
					"3" : job.render_settings,
					"4" : job.status,
					"5" : job.owner})
				table_data = json.dumps(json_output('dataTable', table_rows))
				fileobj.write(table_data + '\n')
				fileobj.flush()
				fileobj.close() # very important, otherwise PHP does not get EOF
		elif action == 'update':
			if len(values) > 0:
				if len(filters) > 0:
					pass
				else: 
					pass # apply to all

			else:
				pass #can't update with not new values!
		elif action == 'delete':
			pass
		else:
			pass


def initialize_runtime_client(db_client):
	client = Client(id = db_client.id,
		hostname = db_client.hostname,
		mac_address = db_client.mac_address,
		socket = False,
		status = db_client.status,
		warning = db_client.warning,
		config = db_client.config)
	return client


def load_from_database():
	clients_database_list = load_clients()
	for db_client in clients_database_list:
			clients_list.append(initialize_runtime_client(db_client))
	print("[boot] " + str(len(clients_database_list)) + " clients loaded from database")
	return


def add_client_to_database(new_client_attributes):
	print("Adding a new client to the database")
	return initialize_runtime_client(create_client(new_client_attributes))


def save_to_database():
	for client in clients_list:
		save_runtime_client(client)
	print("\n[shutdown] " + str(len(clients_list)) + " clients saved successfully")


def look_for_jobs():
	""" 
	With this function we get in a loop until there is no job left to do 
	in the database 
	"""
	
	if Jobs.select().count() > 0:
		time.sleep(1) # For debug we wait 1 second
		d_print('selecting jobs')
		order = {"is_final": False }

		for job in Jobs.select():
			if job.status == 'running':

				# If the job is at the very first chunk
				if job.frame_start == job.current_frame:
					chunk_start = job.frame_start
					chunk_end = chunk_start + job.chunk_size
					
					job.current_frame = chunk_end
					job.save()		

				else:
					# If any we update the current frame for the job
					chunk_start = job.current_frame + 1
					chunk_end = chunk_start + job.chunk_size
					d_print('updated current frame ' + str(chunk_end))

					# Any chunk within start and end frame
					if chunk_end < job.frame_end:
						job.current_frame = chunk_end
						job.save()

					# If the job is at the very last chunk
					else:
						job.current_frame = job.frame_end
						chunk_end = job.frame_end
						job.status = 'finishing'
						job.save()

						order.update({"is_final": True})

				order.update({
					"job_id": job.id,
					"filepath": job.filepath,
					"chunk_start": chunk_start,
					"chunk_end": chunk_end,
					"current_frame": chunk_start})
				
				return json.dumps(order)
	else:
		print("[info] No jobs at the moment, feed the farm")
		return False



# this handler will be run for each incoming connection in a dedicated greenlet
def handle(socket, address):
	#print ('New connection from %s:%s' % address)
	# using a makefile because we want to use readline()
	fileobj = socket.makefile()	
	while True:
		line = fileobj.readline().strip()
				
		if line.lower() == 'identify_client':
			print ('New connection from %s:%s' % address)
			# we want to know if the cliend connected before
			fileobj.write('mac_addr')
			fileobj.flush()
			d_print("Waiting for mac address")
			line = fileobj.readline().strip().split()
			
			# if the client was connected in the past, there should be an instanced
			# object in the clients_list[]. We access it and set the get_status
			# variable to True, to make it run and accept incoming orders.
			# Since the client_select methog returns a list we have to select the
			# first and only item in order to make it work (that's why we have the
			# trailing [0] in the selection query for the mac_address here)
			
			#client = client_select('mac_address', int(line[0]))[0]
			client = client_select('mac_address', int(line[0]))
			
			if client:
				client = client[0]
				d_print('This client connected before')
				client.set_attributes('socket', socket)
				
			else:
				d_print('This client never connected before')
				# create new client object with some defaults. Later on most of these
				# values will be passed as JSON object during the first connection
				new_client_attributes = {
					'hostname': line[1], 
					'mac_address': line[0], 
					'status': 'enabled', 
					'warning': False, 
					'config': 'bla'
				}

				client = add_client_to_database(new_client_attributes)
			
				# we assign the socket to the client and append it to the list
				client.set_attributes('socket', socket)
				clients_list.append(client)

			#d_print ('the socket for the client is: ' + str(client.get_attributes('socket')))
			#print ("the id for the client is: " + str(client.get_attributes('id')))
			while True:
				d_print('Client ' + str(client.get_attributes('hostname')) + ' is waiting')
				line = fileobj.readline().strip()
				if line.lower() == 'ready':
					print('Client is wating for an order')
					order = look_for_jobs()
					if order:
						socket.send(str(order))
					else:
						print("[info] no orders generated")

				elif line.lower() == 'busy':
					print('Order successfully executed - frame delivered')
					line = fileobj.readline().strip()
					while line.lower() == 'busy':
						print('Order successfully executed - frame delivered')
						line = fileobj.readline().strip()

					if line == 'chunk_finished':
						print('Chunk finished')
					elif line == 'job_finished':
						print('Job finished') #add id and more info
					# TODO next step is to save order to database
					# and then save frames into database

				# Only run at the very last fram of a job
				elif line.lower() == 'finished':
					print('Order successfully executed - last frame of the job delivered')

				elif line.lower() == 'warning':
					print('[warning] the client seems to have issues')
					client.set_attributes('warning', True)

				else:
					print('Clients is being disconnected')
					client.set_attributes('socket', False)
					break
					
		if line.lower() == 'clients':
			print('[<-] Sending list of clients to interface')
			table_rows = []
			for client in clients_list:
				connection = client.get_status()
				table_rows.append({"DT_RowId": client.get_attributes('id'),
				"DT_RowClass": connection,
				"0" : client.get_attributes('hostname'),
				"1" : client.get_attributes('status'),
				"2" : connection})
			table_data = json.dumps(json_output('dataTable', table_rows))
			fileobj.write(table_data + '\n')
			fileobj.flush()
			fileobj.close() # very important, otherwise PHP does not get EOF
			break

		elif line.lower().startswith('disable'):
			command = line.split()
			if len(command) > 1:
				if command[1] == 'ALL':
					set_client_attribute(('status', 'enabled'), ('status', 'disabled'))
				else:
					print(command[1])
					set_client_attribute(('hostname', command[1]), ('status', 'disabled'))
			else:
				fileobj.write('[Warning] No client selected. Specify a '
					'client name or use the \'ALL\' argument.\n')

		elif line.lower().startswith('enable'): # Here we have a lot of code duplication!
			command = line.split()
			if len(command) > 1:
				if command[1] == 'ALL':
					set_client_attribute(('status', 'disabled'), ('status', 'enabled'))
				else:
					#print(command[1])
					set_client_attribute(('hostname', command[1]), ('status', 'enabled'))
			else:
				fileobj.write('[Warning] No client selected. Specify a '
					'client name or use the \'ALL\' argument.\n')
				
		elif line.lower() == 'test':
			fileobj.write('test>')
		
		# This will actually replace any way to talk to the server ('clients', 'save', ect).
		elif line.startswith('{'):
			#line = dict(line)
			#line = {'item': 'client', 'action': 'read', 'filters': ''}
			line = json.loads(line)
			json_io(fileobj, line)
			break

		elif line.lower() == 'save':
			save_to_database()
		
		elif line.lower() == 'quit':
			print('[x] Closed connection from %s:%s' % address)
			break
			
		elif not line:
			print ('[x] Client disconnected')
			break
		
		#print("line is " + line)
		#fileobj.write('> ')
		fileobj.flush()
				

if __name__ == '__main__':
	try:
		# we load the clients from the database into the list as objects
		# might be wise to just read them all the time from the database
		# instead of putting them in memory. To be decided.
		print("[boot] Loading clients from database")
		load_from_database()
		# to make the server use SSL, pass certfile and keyfile arguments to the constructor
		server = StreamServer(('0.0.0.0', 6000), handle, spawn=pool)
		# to start the server asynchronously, use its start() method;
		# we use blocking serve_forever() here because we have no other jobs
		print ('[boot] Starting echo server on port 6000')
		server.serve_forever()
	except KeyboardInterrupt:
		save_to_database()
		print("[shutdown] Quitting brender")
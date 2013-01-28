from peewee import *
from datetime import date
import random

db = SqliteDatabase('brender.sqlite')

class Clients(Model):
	mac_address = IntegerField()
	hostname = CharField()
	status = CharField()
	warning = BooleanField()
	config = CharField()

	class Meta:
		database = db


class Projects(Model):
	name = CharField()
	description = CharField()
	project_path = CharField()
	render_engine_path = CharField()
	is_active = BooleanField()
	config = CharField()

	class Meta:
		database = db


class Sequences(Model):
	project = ForeignKeyField(Projects, related_name='fk_project')
	name = CharField()
	description = CharField()
	config = CharField()

	class Meta:
		database = db


class Shots(Model):
	sequence = ForeignKeyField(Sequences, related_name='fk_sequence')
	name = CharField()
	description = CharField()
	frame_start = IntegerField()
	frame_end = IntegerField()
	chunk_size = IntegerField()
	settings = CharField() # yolo settings
	stage = CharField() # lighting
	notes = CharField() # add more realism
	status = CharField() # started and waiting / stopped / running / paused

	class Meta:
		database = db


class Frames(Model):
	shot = ForeignKeyField(Shots, related_name='fk_shot')
	command = CharField()
	stats = CharField()

	class Meta:
		database = db


class Jobs(Model):
	client = ForeignKeyField(Clients, related_name='fk_client')
	#shot = ForeignKeyField(Shots, related_name='fk_shot')
	command = CharField() 

	class Meta:
		database = db


def create_databases():
	"""Create the required databases during installation.

	Based on the classes specified above (currently Clients and Jobs)
	"""
	Clients.create_table()
	Projects.create_table()
	Sequences.create_table()
	Shots.create_table()
	Frames.create_table()
	Jobs.create_table()


def create_clients(clients_amount):
	"""Create the specified amount of clients.

	Assigns some random values as hostname and mac_address. Used only
	for testing purposes.
	"""
	for i in range(clients_amount):
		Clients.create(mac_address = 123 + i,
			hostname = 'client_' + str(i),
			status = 'enabled',
			warning = False,
			config ='JSON string')
	print("Database filled with " + str(clients_amount) + " clients.")


def delete_clients(clients):
	"""Removes all clients found in the clients table.

	Should be refactored?
	"""
	if clients == 'ALL':
		clients_count = Clients.select().count()
		for client in Clients.select():
			print("Removing client " + client.hostname)
			client.delete_instance()
		print("Removed all the " + str(clients_count) + " clients")
	else:
		print("Specify client id")


def create_jobs(jobs_amount):
	"""Creates the specified amount of jobs.

	Jobs are fake and get randomly assigned do the existing clients
	by picking their row id from a list generate on the fly.
	"""
	clients_count = Clients.select().count()
	if clients_count > 0:
		# We build an index of the client ids
		client_ids = []
		for client in Clients.select():
			client_ids.append(client.id)

		for i in range(jobs_amount):
			random_id = random.choice(client_ids)
			Jobs.create(client = random_id,
				command = "hello " + str(random_id))

		print("Added " + str(jobs_amount) + " jobs.")
	else:
		print("[warning] No clients available")


def disable_clients():
	for client in Clients.select():
		client.status = 'disabled'
		client.save()
		print("Changing status to 'disabled' for client " + str(client.hostname))


def load_clients():
	clients_list = []
	for client in Clients.select():
		clients_list.append(client)
	
	return clients_list


def create_client(attributes):
	new_client = Clients.create(mac_address = attributes['mac_address'],
		hostname = attributes['hostname'],
		status = attributes['status'],
		warning = attributes['warning'],
		config =attributes['config'])
	print("New client " + attributes['hostname'] + " was added")
	return new_client


def show_clients():
	for client in Clients.select():
		print client.hostname, client.fk_client.count(), 'fk_client'
		for order in client.fk_client:
			print '    ', order.order


def save_runtime_client(client):
	db_client = Clients.get(Clients.id == client.get_attributes('id'))
	db_client.hostname = client.get_attributes('hostname')
	db_client.status = client.get_attributes('status')
	db_client.warning = client.get_attributes('warning')
	db_client.config = client.get_attributes('config')
	db_client.save()

#create_databases()

#create_clients(10)
#delete_clients('ALL')
#create_jobs(10)
#disable_clients()

#show_clients()

#print Clients.select().count()


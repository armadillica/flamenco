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

class Jobs(Model):
	shot = IntegerField()
	frame_start = IntegerField()
	frame_end = IntegerField()
	chunk_size = IntegerField()
	current_frame = IntegerField()
	filepath = CharField() 
	render_settings = CharField() # yolo settings (pre render / render / post)
	status = CharField() # started and waiting / stopped / running / paused
	priority = IntegerField()
	owner = CharField() # will eventually become a foreign field

	class Meta:
		database = db


class Orders(Model):
	"""docstring for Orders"""

	job = ForeignKeyField(Jobs, related_name='fk_job')
	client = ForeignKeyField(Clients, related_name='fk_client')
	chunk_start = IntegerField()
	chunk_end = IntegerField()
	current_frame = IntegerField()

	class Meta:
		database = db



def create_databases():
	"""Create the required databases during installation.

	Based on the classes specified above (currently Clients and Jobs)
	"""
	Clients.create_table()
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


def add_random_jobs(jobs_amount):
	"""Creates the specified amount of jobs.

	Jobs are fake and get randomly assigned do the existing clients
	by picking their row id from a list generate on the fly.
	"""
	shots_count = Shots.select().count()
	if shots_count > 0:
		# We build an index of the shot ids
		shot_ids = []
		for shot in Shots.select():
			shot_ids.append(shot.id)

		for i in range(jobs_amount):
			random_id = random.choice(shot_ids)
			Jobs.create(shot = random_id,
				frame_start = 2,
				frame_end = 50,
				chunk_size = 5,
				current_frame = 2,
				filepath = 'path',
				render_settings = 'will refer to settins table',
				status = 'running',
				priority = 10,
				owner = 'fsiddi')

		print("Added " + str(jobs_amount) + " shots.")
	else:
		print("[warning] No shots available")




def fill_with_data():

	Projects.create(name = 'Test project',
		description = 'Test project',
		project_path = '{"linux":"/path","osx":"/path","windows":"/path"}',
		render_output_path = '{"linux":"/path","osx":"/path","windows":"/path"}',
		render_engine_path = '{"linux":"/path","osx":"/path","windows":"/path"}',
		is_active = True,
		settings = '{"framerate":24,"use_svn":False,"use_dropbox":False}')

	print "project created"

	Sequences.create(project = 1,
		name = '01_01',
		description = 'Sequence 1')

	create_shots(10)

	Jobs.create(shot = 1,
		frame_start = 2,
		frame_end = 50,
		chunk_size = 5,
		current_frame = 2,
		filepath = 'path',
		render_settings = 'will refer to settings table',
		status = 'running',
		priority = 10,
		owner = 'fsiddi')


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


def install_brender():
	create_databases()
	create_clients(10)
	fill_with_data()


#install_brender()

#create_shots(20)
#delete_clients('ALL')
#create_jobs(10)
#disable_clients()

#add_random_jobs(10)

#show_clients()

#print Clients.select().count()


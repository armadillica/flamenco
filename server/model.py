from peewee import *
from datetime import date
import random

db = SqliteDatabase('brender.sqlite')

class Workers(Model):
	mac_address = IntegerField()
	hostname = CharField()
	status = CharField()
	warning = BooleanField()
	config = CharField()
	ip_address = CharField()
	port = IntegerField()

	class Meta:
		database = db

class Jobs(Model):
	shot_id = IntegerField()
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
	worker = ForeignKeyField(Workers, related_name='fk_worker')
	chunk_start = IntegerField()
	chunk_end = IntegerField()
	current_frame = IntegerField()

	class Meta:
		database = db



def create_databases():
	"""Create the required databases during installation.

	Based on the classes specified above (currently Workers and Jobs)
	"""
	Workers.create_table()
	Jobs.create_table()



def create_workers(workers_amount):
	"""Create the specified amount of workers.

	Assigns some random values as hostname and mac_address. Used only
	for testing purposes.
	"""
	for i in range(workers_amount):
		Workers.create(mac_address = 123 + i,
			hostname = 'worker_' + str(i),
			status = 'enabled',
			warning = False,
			config ='JSON string')
	print("Database filled with " + str(workers_amount) + " workers.")


def delete_workers(workers):
	"""Removes all workers found in the workers table.

	Should be refactored?
	"""
	if workers == 'ALL':
		workers_count = Workers.select().count()
		for worker in Workers.select():
			print("Removing worker " + worker.hostname)
			worker.delete_instance()
		print("Removed all the " + str(workers_count) + " workers")
	else:
		print("Specify worker id")


def add_random_jobs(jobs_amount):
	"""Creates the specified amount of jobs.

	Jobs are fake and get randomly assigned do the existing workers
	by picking their row id from a list generate on the fly.
	"""

	shot_ids = [2,3,4,5,5,6]

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


def create_worker(attributes):
	new_worker = Workers.create(mac_address = attributes['mac_address'],
		hostname = attributes['hostname'],
		status = attributes['status'],
		warning = attributes['warning'],
		config =attributes['config'])
	print("New worker " + attributes['hostname'] + " was added")
	return new_worker


def show_workers():
	for worker in Workers.select():
		print worker.hostname, worker.fk_worker.count(), 'fk_worker'
		for order in worker.fk_worker:
			print '    ', order.order


def install_brender():
	create_databases()
	create_workers(10)
	fill_with_data()


#install_brender()

#create_shots(20)
#delete_workers('ALL')
#create_jobs(10)
#disable_workers()

#add_random_jobs(10)

#show_workers()

#print Workers.select().count()


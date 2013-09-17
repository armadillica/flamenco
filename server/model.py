from peewee import *
from datetime import date
import random

DATABASE = 'brender.sqlite'

db = SqliteDatabase(DATABASE)

# create a base model class that our application's models will extend
class BaseModel(Model):
    class Meta:
        database = db


class Workers(BaseModel):
	"""Workers are the render nodes of the farm

	The creation of a Worker in the database happens automatically a soon
	as it connects to the server and its MAC address does not match any
	of the one alreay present in the database.
	"""
	mac_address = IntegerField()
	hostname = CharField()
	status = CharField()
	warning = BooleanField()
	config = CharField()
	ip_address = CharField()
	connection = CharField()


class Shots(BaseModel):
	"""A Shot one of the basic units of brender

	The creation of a shot can happen in different ways:
	* within brender (using a shot creation form)
	* via a query from an external software (e.g. Attract)
	"""
	production_shot_id = IntegerField()
	frame_start = IntegerField()
	frame_end = IntegerField()
	chunk_size = IntegerField()
	current_frame = IntegerField()
	shot_name = CharField() 
	filepath = CharField() 
	render_settings = CharField() # yolo settings (pre render / render / post)
	status = CharField() # started and waiting / stopped / running / paused
	priority = IntegerField()
	owner = CharField() # will eventually become a foreign field


class Jobs(BaseModel):
	"""Jobs are created after a Shot is added

	Jobs can be reassigned individually to a different worker, but can be
	deleted and recreated all together. A job is made of "orders" or
	instructions, for example:
	* Check out SVN revision 1954
	* Clean the /tmp folder
	* Render frames 1 to 5 of scene_1.blend
	* Send email with results to user@brender-farm.org
	"""
	#shot = ForeignKeyField(Shots, related_name='fk_shot')
	#worker = ForeignKeyField(Workers, related_name='fk_worker')
	shot_id = IntegerField()
	worker_id = IntegerField()
	chunk_start = IntegerField()
	chunk_end = IntegerField()
	current_frame = IntegerField()
	status = CharField()
	priority = IntegerField()


def create_tables():
	"""Create the required databases during installation.

	Based on the classes specified above. This function is embedded in
	the install_brender function.
	"""
	Workers.create_table()
	Shots.create_table()
	Jobs.create_table


def add_random_workers(workers_amount):
	"""Create the specified amount of workers.

	Assigns some random values as hostname and mac_address. Used only
	for testing purposes.
	TODO: make sure that all the properties of a worker are added here
	"""
	for i in range(workers_amount):
		Workers.create(mac_address = 123 + i,
			hostname = 'worker_' + str(i),
			status = 'enabled',
			warning = False,
			config ='JSON string')
	print("Database filled with " + str(workers_amount) + " workers.")



def create_database():
	"""Checks if the database exists

	We check for the existence of the file on disc. If the file is not 
	found we create one an we pupulate it with the brender schema from
	this file.

	"""
	try:
	    with open(DATABASE): pass
	except IOError:
	    print '[Info] Creating brender.sqlite database'
	    open(DATABASE, 'a').close()
	    create_tables()
	    print '[Info] Database created'


create_database()

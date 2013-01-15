from peewee import *
from datetime import date
import random

db = SqliteDatabase('brender.sqlite')

class Clients(Model):
    mac_address = IntegerField()
    hostname = CharField()
    status = CharField()
    warning = BooleanField()
    is_online = BooleanField()
    config = CharField()

    class Meta:
        database = db

class Orders(Model):
    client = ForeignKeyField(Clients, related_name='fk_client')
    order = CharField()

    class Meta:
        database = db


def create_databases():
	"""Create the required databases during installation.

	Based on the classes specified above (currently Clients and Orders)
	"""
	Clients.create_table()
	Orders.create_table()


def create_clients(clients_amount):
	"""Create the specified amount of clients.

	Assigns some random values as hostname and mac_address. Used only
	for testing purposes.
	"""
	for i in range(clients_amount):
		Clients.create(mac_address = 123 + i,
			hostname = 'asd_' + str(i),
			status = 'enabled',
			warning = False,
			is_online = False,
			config ='JSON string')
	print("Database filled with " + str(clients_amount) + " clients.")


def remove_clients():
	"""Removes all clients found in the clients table.

	Should be refactored?
	"""
	for client in Clients.select():
		print("Removing client " + client.hostname)
		client.delete_instance()
	print("Removed all the clients")


def create_orders(orders_amount):
	"""Creates the specified amount of orders.

	Orders are fake and get randomly assigned do the existing clients
	by picking their row id from a list generate on the fly.
	"""
	clients_count = Clients.select().count()
	if clients_count > 0:
		# We build an index of the client ids
		client_ids = []
		for client in Clients.select():
			client_ids.append(client.id)

		for i in range(orders_amount):
			random_id = random.choice(client_ids)
			Orders.create(client = random_id,
				order = "hello " + str(random_id))

		print("Added " + str(orders_amount) + " orders.")
	else:
		print("[warning] No clients available")

def disable_clients():
	for client in Clients.select():
		client.status = 'disabled'
		client.save()
		print("Changing status to 'disabled' for client " + str(client.hostname))


#create_databases()

#create_clients(10)
#remove_clients()
#create_orders(5)
#disable_clients()

"""
for client in Clients.select():
	print client.hostname, client.asd.count(), 'orders'
	for order in client.asd:
		print '    ', order.order
"""
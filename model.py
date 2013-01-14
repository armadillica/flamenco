from peewee import *
from datetime import date

db = SqliteDatabase('brender.sqlite')

class Clients(Model):
    mac_address = IntegerField()
    hostname = CharField()
    warning = BooleanField()
    is_online = BooleanField()
    config = CharField()

    class Meta:
        database = db

class Orders(Model):
    client = ForeignKeyField(Clients, related_name='asd')
    order = CharField()

    class Meta:
        database = db


for client in Clients.select():
	print client.hostname, client.asd.count(), 'orders'
	for order in client.asd:
		print '    ', order.order

for order in Orders.select():
	mac = order.client.asd.hostname.select()
	print mac


"""
CREATE TABLE "orders" (
	"id" INTEGER PRIMARY KEY  NOT NULL ,
	"client_id" INTEGER, 
	"order" VARCHAR,
	FOREIGN KEY(client_id) REFERENCES clients(id)
)

CREATE TABLE "clients" (
	"id" INTEGER PRIMARY KEY  AUTOINCREMENT  NOT NULL , 
	"mac_address" INTEGER NOT NULL , 
	"hostname" VARCHAR, 
	"warning" BOOL, 
	"is_online" BOOL, 
	"config" 
)

"""
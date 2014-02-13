from peewee import *
from datetime import date
import random
DATABASE = None

db = SqliteDatabase(DATABASE)


# create a base model class that our application's models will extend
class BaseModel(Model):
    class Meta:
        database = db


class Workers(BaseModel):
    """
    Workers are the render nodes of the farm

    The creation of a Worker in the database happens automatically a soon
    as it connects to the server and its MAC address does not match any
    of the one alreay present in the database.
    """
    mac_address = IntegerField()
    hostname = CharField()
    status = CharField()
    warning = BooleanField()
    config = CharField()
    system = CharField()
    ip_address = CharField()
    connection = CharField()


class Shows(BaseModel):
    """Production project folders

    This is a temporary table to get quickly up and running with projects
    suport in brender. In the future, project definitions could come from
    attract or it could be defined in another way.
    """
    name = CharField()
    path_server = TextField()
    path_linux = TextField()
    path_osx = TextField()


class Shots(BaseModel):
    """
    A Shot one of the basic units of brender

    The creation of a shot can happen in different ways:
    * within brender (using a shot creation form)
    * via a query from an external software (e.g. Attract)
    """
    attract_shot_id = IntegerField()
    show_id = IntegerField()
    frame_start = IntegerField()
    frame_end = IntegerField()
    chunk_size = IntegerField()
    current_frame = IntegerField()
    shot_name = CharField()
    filepath = CharField()
    render_settings = CharField()  # yolo settings (pre render / render / post)
    status = CharField()  # started and waiting / stopped / running / paused
    priority = IntegerField()
    owner = CharField()  # will eventually become a foreign field


class Jobs(BaseModel):
    """
    Jobs are created after a Shot is added

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


class Settings(BaseModel):
    """
    General brender settings

    At the momen the structure of this table is very generic. This could
    even be turned into a config file later on.
    """
    name = CharField()
    value = CharField()


def create_tables():
    """
    Create the required databases during installation.

    Based on the classes specified above. This function is embedded in
    the install_brender function.
    """
    Workers.create_table()
    Shows.create_table()
    Shots.create_table()
    Jobs.create_table()
    Settings.create_table()


def add_random_workers(workers_amount):
    """
    Create the specified amount of workers.

    Assigns some random values as hostname and mac_address. Used only
    for testing purposes.
    TODO: make sure that all the properties of a worker are added here
    """
    for i in range(workers_amount):
        Workers.create(mac_address=123 + i,
                       hostname='worker_' + str(i),
                       status='enabled',
                       ip_address='192.168.1.' + str(i),
                       connection='offline',
                       warning=False,
                       config='JSON string')
    print("Database filled with " + str(workers_amount) + " workers.")


def create_database():
    """
    Checks if the database exists

    We check for the existence of the file on disc. If the file is not
    found we create one and we populate it with the brender schema from
    this file.

    """
    try:
        with open(DATABASE):
            pass
    except IOError:
        print('[Info] Creating brender.sqlite database')
        open(DATABASE, 'a').close()
        create_tables()
        print('[Info] Database created')

    db.init(DATABASE)
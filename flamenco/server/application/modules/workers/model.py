"""from application import db
from urllib import urlopen

class Worker(db.Model):
    ""Workers are the render nodes of the farm

    The creation of a Worker in the database happens automatically as soon
    as it connects to the server and its MAC address does not match any
    of the one already present in the database.
    ""
    id = db.Column(db.Integer, primary_key=True)
    mac_address = db.Column(db.Integer())
    hostname = db.Column(db.String(120))
    status = db.Column(db.String(60))
    warning = db.Column(db.Boolean())
    config = db.Column(db.String(120))
    system = db.Column(db.String(120))
    ip_address = db.Column(db.String(32), unique=True)
    connection = db.Column(db.String(64))

    def __repr__(self):
        return '<Worker %r>' % self.hostname"""

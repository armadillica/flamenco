import datetime
from application import db

class Manager(db.Model):
    """Model for the managers connected to the server. When a manager
    connects, we check if it is sending a token. If no token is provided we
    assume it's a new manager and proceed to register it. In the response we
    provide a token that the manager should use for every future request.

    While we support manager automatic registration, we migth also make it a
    manual process, were the server user has to create a manager and send the
    token to the manager user so that it can set it in the properties.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    logo = db.Column(db.String(128))
    host = db.Column(db.String(128))
    ip_address = db.Column(db.String(15))
    has_virtual_workers = db.Column(db.SmallInteger(), default=0)
    token = db.Column(db.String(128), unique=True)
    token_expires = db.Column(db.DateTime())


    def __repr__(self):
        return '<Manager %r>' % self.id

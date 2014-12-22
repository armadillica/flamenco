from application import db
from urllib import urlopen
from sqlalchemy import UniqueConstraint

class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(15))
    port = db.Column(db.Integer())
    hostname = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20))
    connection = db.Column(db.String(20))
    system = db.Column(db.String(20))

    __table_args__ = (UniqueConstraint('ip_address', 'port', name='connection_uix'),)

    @property
    def host(self):
        return self.ip_address + ':' + str(self.port)

    @property
    def is_connected(self):
        try:
            urlopen("http://" + self.host)
            return True
        except:
            print "[Warning] Worker %s is not online" % self.host
            return False

    def __repr__(self):
        return '<Worker %r>' % self.id

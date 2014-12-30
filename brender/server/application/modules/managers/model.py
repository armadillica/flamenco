from application import db
from urllib import urlopen
from sqlalchemy import UniqueConstraint

class Manager(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(15))
    port = db.Column(db.Integer)
    name = db.Column(db.String(50), nullable=True)

    # This represent the total number of worker that
    # this manager holds. If total_workers < 0 then,
    # the manager can handle an infinity of worker
    total_workers = db.Column(db.Integer())

    # Number of running task in the manager
    running_tasks = 0

    __table_args__ = (UniqueConstraint('ip_address', 'port', name='connection_uix'),)

    @property
    def host(self):
        return self.ip_address + ':' + str(self.port)

    def is_available(self):
        return self.total_workers - self.running_tasks > 0 or self.total_workers == -1

    @property
    def is_connected(self):
        try:
            urlopen("http://" + self.host)
            return True
        except:
            print "[Warning] Manager %s is not online" % self.name
            return False


    def __repr__(self):
        return '<Manager %r>' % self.id

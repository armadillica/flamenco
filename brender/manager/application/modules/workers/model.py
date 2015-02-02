import requests
import logging
from requests.exceptions import Timeout
from requests.exceptions import ConnectionError
from requests.exceptions import HTTPError
from application import db
from sqlalchemy import UniqueConstraint

class Worker(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(15))
    port = db.Column(db.Integer())
    hostname = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(20))
    connection = db.Column(db.String(20))
    system = db.Column(db.String(20))
    current_task = db.Column(db.String(20))

    __table_args__ = (UniqueConstraint('ip_address', 'port', name='connection_uix'),)

    @property
    def host(self):
        return self.ip_address + ':' + str(self.port)

    @property
    def is_connected(self):
        try:
            r = requests.get("http://" + self.host, timeout=0.5)
            r.raise_for_status()
            info = r.json()
            self.status = info['status']
            print info['status']
            db.session.commit()
            return True
        except Timeout:
            logging.warning("Worker {0} is not online (Timeout)".format(self.host))
            return False
        except ConnectionError:
            logging.warning("Worker {0} is not online (Connection Error)".format(self.host))
            return False
        except HTTPError:
            logging.warning("Worker {0} is not online (HTTP Error)".format(self.host))
            return False

    def __repr__(self):
        return '<Worker %r>' % self.id

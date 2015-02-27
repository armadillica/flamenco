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
    activity = db.Column(db.String(64))
    log = db.Column(db.Text())
    time_cost = db.Column(db.Integer())

    __table_args__ = (UniqueConstraint('ip_address', 'port', name='connection_uix'),)

    @property
    def host(self):
        return self.ip_address + ':' + str(self.port)

    @property
    def is_connected(self):
        try:
            r = requests.get("http://" + self.host + '/info', timeout=1)
            r.raise_for_status()
            info = r.json()
            if self.status == 'disabled' and info['status'] != 'error':
                self.status = info['status']
            self.activity = info['activity']
            self.log = info['log']
            self.time_cost = info['time_cost']
            if info['status'] == 'error':
                self.connection = 'offline'
                db.session.commit()
                return False
            db.session.commit()
            return True
        except Timeout:
            logging.warning("iWorker {0} is offline (Timeout)".format(self.host))
            if self.status!='busy':
                self.connection = 'offline'
                db.session.commit()
            return False
        except ConnectionError:
            logging.warning("Worker {0} is offline (Connection Error)".format(self.host))
            if self.status!='busy':
                self.connection = 'offline'
                db.session.commit()
            return False
        except HTTPError:
            logging.warning("Worker {0} is offline (HTTP Error)".format(self.host))
            if self.status!='busy':
                self.connection = 'offline'
                db.session.commit()
            return False

    def __repr__(self):
        return '<Worker %r>' % self.id

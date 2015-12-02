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
    system = db.Column(db.String(50))
    current_task = db.Column(db.String(20))
    child_task = db.Column(db.String(20))
    activity = db.Column(db.String(64))
    log = db.Column(db.Text())
    time_cost = db.Column(db.Integer())
    last_activity = db.Column(db.DateTime())
    job_types = db.relationship("WorkerJobType", backref="worker")

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
            logging.warning("Worker {0} is offline (Timeout)".format(self.host))
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

    @property
    def job_types_list(self):
        """We search for Job Types associated with the worker and deliver a list
        with the names"""
        return [j.job_type.name for j in self.job_types]


class WorkerJobType(db.Model):
    """Association table that connects Job Types with workers, so that once a
    worker is free, the manager can ask the server for the right task type
    according to the worker's capabilities.
    """
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('worker.id'), primary_key=True)
    job_type_id = db.Column(db.Integer, db.ForeignKey('job_type.id'), primary_key=True)
    # TODO: add slots for each job type
    job_type = db.relationship("JobType", backref="worker_job_type")

import datetime
from application import db

from application.modules.managers.model import Manager

class Job(db.Model):
    """A Job is the basic work unit of Flamenco

    The creation of a job can happen in different ways:
    * within Flamenco (using the job creation form)
    * via a query from an external software (e.g. Attract)
    * withing Blender itself
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    project = db.relationship('Project',
        backref=db.backref('jobs', lazy='dynamic'))
    name = db.Column(db.String(120))
    status = db.Column(db.String(64))
    priority = db.Column(db.Integer())
    settings = db.Column(db.Text())
    creation_date = db.Column(db.DateTime(), default=datetime.datetime.now)
    type = db.Column(db.String(64))

    def __repr__(self):
        return '<Job %r>' % self.name

class JobManagers(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer(), db.ForeignKey('job.id'))
    job = db.relationship('Job', backref=db.backref('manager_list', lazy='dynamic'))
    manager_id = db.Column(db.Integer(), db.ForeignKey('manager.id'))
    manager = db.relationship('Job', backref=db.backref('jobs_list', lazy='dynamic'))

# TODO: look into the benefits of using the standard many to many
# job_managers_table = db.Table('job_managers', db.Model.metadata,
#     db.Column('job_id', db.Integer, db.ForeignKey('jon.id', ondelete='CASCADE')),
#     db.Column('manager_id', db.Integer, db.ForeignKey('manager.id'))
#     )

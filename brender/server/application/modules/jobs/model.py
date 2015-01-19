from application import db

from application.modules.managers.model import Manager

class Job(db.Model):
    """A Shot is one of the basic units of brender

    The creation of a shot can happen in different ways:
    * within brender (using a shot creation form)
    * via a query from an external software (e.g. Attract)
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    project = db.relationship('Project',
        backref=db.backref('jobs', lazy='dynamic'))
    frame_start = db.Column(db.Integer())
    frame_end = db.Column(db.Integer())
    chunk_size = db.Column(db.Integer())
    current_frame = db.Column(db.Integer())
    name = db.Column(db.String(120))
    filepath = db.Column(db.String(256))
    render_settings = db.Column(db.String(120))
    format = db.Column(db.String(10))
    # yolo settings (pre render / render / post)
    status = db.Column(db.String(64))
    # started and waiting / stopped / running / paused
    priority = db.Column(db.Integer())

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

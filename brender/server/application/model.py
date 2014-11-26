from datetime import date
from application import db

class Shot(db.Model):
    """A Shot is one of the basic units of brender

    The creation of a shot can happen in different ways:
    * within brender (using a shot creation form)
    * via a query from an external software (e.g. Attract)
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    project = db.relationship('Project',
        backref=db.backref('shots', lazy='dynamic'))
    frame_start = db.Column(db.Integer())
    frame_end = db.Column(db.Integer())
    chunk_size = db.Column(db.Integer())
    current_frame = db.Column(db.Integer())
    name = db.Column(db.String(120))
    filepath = db.Column(db.String(256))
    render_settings = db.Column(db.String(120))
    extension = db.Column(db.String(10))
    # yolo settings (pre render / render / post)
    status = db.Column(db.String(64))
    # started and waiting / stopped / running / paused
    priority = db.Column(db.Integer())


    def __repr__(self):
        return '<Shot %r>' % self.name


class Job(db.Model):
    """Jobs are created after a Shot is added

    Jobs can be reassigned individually to a different worker, but can be
    deleted and recreated all together. A job is made of "orders" or
    instructions, for example:
    * Check out SVN revision 1954
    * Clean the /tmp folder
    * Render frames 1 to 5 of scene_1.blend
    * Send email with results to user@brender-farm.org
    """
    id = db.Column(db.Integer, primary_key=True)
    shot_id = db.Column(db.Integer, db.ForeignKey('shot.id'))
    shot = db.relationship('Shot',
        backref=db.backref('jobs', lazy='dynamic'))
    worker_id = db.Column(db.Integer())
    chunk_start = db.Column(db.Integer())
    chunk_end = db.Column(db.Integer())
    current_frame = db.Column(db.Integer())
    status = db.Column(db.String(64))
    priority = db.Column(db.Integer())


    def __repr__(self):
        return '<Job %r>' % self.id


class Setting(db.Model):
    """General brender settings

    At the moment the structure of this table is very generic. This could
    even be turned into a config file later on.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    value = db.Column(db.String(128))

    def __repr__(self):
        return '<Setting %r>' % self.name



from datetime import date
from server import db

class Worker(db.Model):
    """Workers are the render nodes of the farm

    The creation of a Worker in the database happens automatically a soon
    as it connects to the server and its MAC address does not match any
    of the one alreay present in the database.
    """
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
        return '<Worker %r>' % self.hostname


class Show(db.Model):
    """Production project folders

    This is a temporary table to get quickly up and running with projects
    suport in brender. In the future, project definitions could come from
    attract or it could be defined in another way.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    path_server = db.Column(db.Text())
    path_linux = db.Column(db.Text())
    path_osx = db.Column(db.Text())

    def __repr__(self):
        return '<Show %r>' % self.name


class Shot(db.Model):
    """A Shot is one of the basic units of brender

    The creation of a shot can happen in different ways:
    * within brender (using a shot creation form)
    * via a query from an external software (e.g. Attract)
    """
    id = db.Column(db.Integer, primary_key=True)
    show_id = db.Column(db.Integer, db.ForeignKey('show.id'))
    show = db.relationship('Show',
        backref=db.backref('shots', lazy='dynamic'))
    frame_start = db.Column(db.Integer())
    frame_end = db.Column(db.Integer())
    chunk_size = db.Column(db.Integer())
    current_frame = db.Column(db.Integer())
    name = db.Column(db.String(120))
    filepath = db.Column(db.String(256))
    render_settings = db.Column(db.String(120))
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



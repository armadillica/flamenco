from application import db

class Task(db.Model):
    """Tasks are created after a Shot is added

    Tasks can be reassigned individually to a different worker, but can be
    deleted and recreated all together. A task is made of "orders" or
    instructions, for example:
    * Check out SVN revision 1954
    * Clean the /tmp folder
    * Render frames 1 to 5 of scene_1.blend
    * Send email with results to user@flamenco-farm.org
    """
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'))
    job = db.relationship('Job',
        backref=db.backref('tasks', lazy='dynamic'))
    manager_id = db.Column(db.Integer())
    name = db.Column(db.String(64))
    status = db.Column(db.String(64))
    priority = db.Column(db.Integer())
    type = db.Column(db.String(64))
    settings = db.Column(db.Text())
    log = db.Column(db.Text())
    activity = db.Column(db.String(256))
    child_id = db.Column(db.Integer())
    parser = db.Column(db.String(64))
    time_cost = db.Column(db.Integer())
    last_activity = db.Column(db.DateTime())
    # Currently the hostname, later will be a serialized dictionary, storing
    # id and hostname of a worker
    worker = db.Column(db.String(128))


    def __repr__(self):
        return '<Task %r>' % self.id

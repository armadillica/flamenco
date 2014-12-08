from application import db

class Task(db.Model):
    """Tasks are created after a Shot is added

    Tasks can be reassigned individually to a different worker, but can be
    deleted and recreated all together. A task is made of "orders" or
    instructions, for example:
    * Check out SVN revision 1954
    * Clean the /tmp folder
    * Render frames 1 to 5 of scene_1.blend
    * Send email with results to user@brender-farm.org
    """
    id = db.Column(db.Integer, primary_key=True)
    shot_id = db.Column(db.Integer, db.ForeignKey('shot.id'))
    shot = db.relationship('Shot',
        backref=db.backref('tasks', lazy='dynamic'))
    worker_id = db.Column(db.Integer())
    chunk_start = db.Column(db.Integer())
    chunk_end = db.Column(db.Integer())
    current_frame = db.Column(db.Integer())
    status = db.Column(db.String(64))
    priority = db.Column(db.Integer())


    def __repr__(self):
        return '<Task %r>' % self.id

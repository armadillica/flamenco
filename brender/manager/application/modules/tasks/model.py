from application import db

class TaskType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    url = db.Column(db.String(128), nullable=False)
    pre_command = db.Column(db.String())
    post_command = db.Column(db.String())


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer)
    priority = db.Column(db.Integer)
    frame_start = db.Column(db.Integer, nullable=True)
    frame_end = db.Column(db.Integer, nullable=True)
    frame_current = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(10))
    format = db.Column(db.String(10))
    file_path = db.Column(db.String(256))
    settings = db.Column(db.String(50))

    def __repr__(self):
        return '<Task %r of type %r>' % (self.id, self.task_type.id)

from application import db

class TaskType(db.model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    url = db.Column(db.String(128), nullable=False)
    pre_command = db.Column(db.String())
    post_command = db.Column(db.String())


class Task(db.model):
    id = db.Column(db.Integer, primary_key=True)
    task_type_id = db.Column(db.Integer, db.ForeignKey('task_type.id'))
    task_type = db.relationship('TaskType',
            backref=db.backref('tasks', lazy='dynamic'))
    worker_id = db.Column(db.Integer)
    priority = db.Column(db.Integer)
    frame_start = db.Column(db.Integer, nullable=True)
    frame_end = db.Column(db.Integer, nullable=True)
    frame_current = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(10))

    def __repr__(self):
        return '<Task %r of type %r>' % (self.id, self.task_type.id)

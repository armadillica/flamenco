from application import db

class JobType(db.Model):
    """List of job types supported by the manager
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    #: The job properties that are used by the task compiler to generate tasks
    # for the workers. It has to be a dictionary.

    # An example JobType property would look like this:
    # {"commands": {
    #     "default": {
    #         "Windows": "/abs/path/to/shared/windows/blender",
    #         "Darwin": "/abs/path/to/shared/osx/blender",
    #         "Linux": "/abs/path/to/shared/linux/blender",
    #         }
    #     }
    # }
    properties = db.Column(db.Text(), nullable=False)
    status = db.Column(db.String(128))

    def __repr__(self):
        return '<JobType %r>' % self.name

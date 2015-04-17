import datetime

from application import db

class Log(db.Model):
    """Store actions performed by users or by the system on different
    entities. The entity gets mapped back via the category (add mixing).
    """
    id = db.Column(db.Integer, primary_key=True)
    #: gets mapped with mixing
    item_id = db.Column(db.Integer(), nullable=False)
    #: category connection, like User, Job, Task, Manager
    category = db.Column(db.String(64), nullable=False)
    log = db.Column(db.Text())
    creation_date = db.Column(db.DateTime(), default=datetime.datetime.now)

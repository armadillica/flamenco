import datetime

from application import db

class Log(db.Model):
    """Store actions performed by users or by the system on different
    entities. The entity gets mapped back via the category (add mixing).

    """
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer(), nullable=False) # Gets mapped with mixing
    category = db.Column(db.String(64), nullable=False) # User, Job, Task, Manager
    log = db.Column(db.Text())
    creation_date = db.Column(db.DateTime(), default=datetime.datetime.now)

from application import db

class Setting(db.Model):
    """General manager settings. Currently cointaining the UUID of the manager.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    value = db.Column(db.Text())

    def __repr__(self):
        return '<Setting %r>' % self.name

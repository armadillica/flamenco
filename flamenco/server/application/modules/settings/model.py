from application import db

class Setting(db.Model):
    """General flamenco settings

    At the moment the structure of this table is very generic. This could
    even be turned into a config file later on.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    value = db.Column(db.String(128))

    def __repr__(self):
        return '<Setting %r>' % self.name

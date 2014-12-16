from application import db

class Worker(db.model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(15), unique=True)
    hostname = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(10))


    def __repr__(self):
        return '<Worker %r>' % self.id

import datetime
from application import db
from application.modules.settings.model import Setting


class Project(db.Model):
    """The project model is used mostly for overview queries on jobs. Most of
    the configuration values that were originally associated with a project
    have been moved to the managers.
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    status = db.Column(db.String(80))
    creation_date = db.Column(db.DateTime(), default=datetime.datetime.now)


    @property
    def is_active(self):
        active_project = Setting.query.filter_by(name='active_project').first()
        if active_project:
            return int(active_project.value) == self.id
        else:
            return False

    def __repr__(self):
        return '<Project %r>' % self.name

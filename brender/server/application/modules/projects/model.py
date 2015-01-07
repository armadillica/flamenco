from datetime import date
from application import db
from application.modules.settings.model import Setting


class Project(db.Model):
    """Production project folders

    This is a temporary table to get quickly up and running with projects
    suport in brender. In the future, project definitions could come from
    attract or it could be defined in another way.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120))
    path_server = db.Column(db.Text())
    path_linux = db.Column(db.Text())
    path_win = db.Column(db.Text())
    path_osx = db.Column(db.Text())
    render_path_server = db.Column(db.Text())
    render_path_linux = db.Column(db.Text())
    render_path_win = db.Column(db.Text())
    render_path_osx = db.Column(db.Text())

    @property
    def is_active(self):
        active_project = Setting.query.filter_by(name='active_project').first()
        if active_project:
            return int(active_project.value) == self.id
        else:
            return False

    def __repr__(self):
        return '<Project %r>' % self.name

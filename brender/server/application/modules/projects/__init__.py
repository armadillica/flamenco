from flask import jsonify
from flask import request
from flask.ext.restful import Resource
from flask.ext.restful import fields
from flask.ext.restful import marshal_with
from flask.ext.restful import reqparse
from application import db
from application.modules.projects.model import Project
from application.modules.settings.model import Setting
from application.modules.jobs.model import Job


parser = reqparse.RequestParser()
parser.add_argument('name', type=str)
parser.add_argument('path_server', type=str)
parser.add_argument('path_linux', type=str)
parser.add_argument('path_win', type=str)
parser.add_argument('path_osx', type=str)
parser.add_argument('render_path_server', type=str)
parser.add_argument('render_path_linux', type=str)
parser.add_argument('render_path_win', type=str)
parser.add_argument('render_path_osx', type=str)
parser.add_argument('is_active', type=bool)


project_fields = {
    'id' : fields.Integer,
    'name' : fields.String,
    'path_server' : fields.String,
    'path_linux' : fields.String,
    'path_win' : fields.String,
    'path_osx' : fields.String,
    'render_path_server' : fields.String,
    'render_path_linux' : fields.String,
    'render_path_win' : fields.String,
    'render_path_osx' : fields.String,
    'is_active' :fields.Boolean
}


class ProjectListApi(Resource):
    def get(self):
        projects = {}
        count = Project.query.count()
        if count == 0:
            project = Project(name="Default Project")
            db.session.add(project)
            db.session.commit()

        for project in Project.query.all():
            projects[project.id] = dict(
                name=project.name)
        """path_server=project.path_server,
        path_linux=project.path_linux,
        path_win=project.path_win,
        path_osx=project.path_osx,
        render_path_server=project.render_path_server,
        render_path_linux=project.render_path_linux,
        render_path_win=project.render_path_win,
        render_path_osx=project.render_path_osx)"""
        return jsonify(projects)

    @marshal_with(project_fields)
    def post(self):
        args = parser.parse_args()
        project = Project(
            name=args['name'])
        """path_server=args['path_server'],
        path_linux=args['path_linux'],
        path_win=args['path_win'],
        path_osx=args['path_osx'],
        render_path_server=args['render_path_server'],
        render_path_linux=args['render_path_linux'],
        render_path_win=args['render_path_win'],
        render_path_osx=args['render_path_osx'])"""
        db.session.add(project)
        db.session.commit()

        if args['is_active'] is not None:
            if args['is_active'] == True:
                # Check if the setting already exists
                setting_active_project = Setting.query.filter_by(name='active_project').first()
                if setting_active_project:
                    setting_active_project.value = project.id
                else:
                    setting_active_project = Setting(
                        name='active_project',
                        value=str(project.id))
                    db.session.add(setting_active_project)
                db.session.commit()
        return project, 201


class ProjectApi(Resource):
    @marshal_with(project_fields)
    def get(self, project_id):
        project = Project.query.get_or_404(project_id)
        return project

    def delete(self, project_id):
        setting_active_project = Setting.query.filter_by(name='active_project').first()
        if setting_active_project:
            if setting_active_project.value == str(project_id):
                setting_active_project.value = None
        jobs_project = Job.query.filter_by(project_id = project_id).all()
        for job_project in jobs_project:
            # print '[Debug] Deleting job (%s) for project %s ' % (job_project.job_name, job_project.project_id)
            db.session.delete(job_project)
            db.session.commit()
        project = Project.query.get_or_404(project_id)
        db.session.delete(project)
        db.session.commit()
        return '', 204

    @marshal_with(project_fields)
    def put(self, project_id):
        args = parser.parse_args()
        project = Project.query.get_or_404(project_id)
        project.path_server = args['path_server']
        project.path_linux = args['path_linux']
        project.path_win = args['path_win']
        project.path_osx = args['path_osx']
        project.render_path_server = args['render_path_server']
        project.render_path_linux = args['render_path_linux']
        project.render_path_win = args['render_path_win']
        project.render_path_osx = args['render_path_osx']
        if args['name']:
            project.name = args['name']
        if args['is_active']:
            pass
        db.session.commit()
        return project, 201


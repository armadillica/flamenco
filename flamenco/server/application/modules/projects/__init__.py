from flask.ext.restful import Resource
from flask.ext.restful import fields
from flask.ext.restful import marshal_with
from flask.ext.restful import reqparse
from application import db
from application.modules.projects.model import Project
from application.modules.settings.model import Setting
from application.modules.jobs.model import Job


parser_project = reqparse.RequestParser()
parser_project.add_argument('name', type=str)
parser_project.add_argument('is_active', type=bool)

project_fields = {
    'id' : fields.Integer,
    'name' : fields.String,
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
        return projects

    @marshal_with(project_fields)
    def post(self):
        args = parser_project.parse_args()
        project = Project(
            name=args['name'])
        db.session.add(project)
        db.session.commit()

        if args['is_active'] is not None:
            if args['is_active'] == True:
                # Check if the setting already exists
                setting_active_project = Setting.query.filter_by(
                    name='active_project').first()
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
        setting_active_project = Setting.query.filter_by(
            name='active_project').first()
        if setting_active_project:
            if setting_active_project.value == str(project_id):
                setting_active_project.value = None
        jobs_project = Job.query.filter_by(project_id=project_id).all()
        for job_project in jobs_project:
            db.session.delete(job_project)
            db.session.commit()
        project = Project.query.get_or_404(project_id)
        db.session.delete(project)
        db.session.commit()
        return '', 204

    @marshal_with(project_fields)
    def put(self, project_id):
        args = parser_project.parse_args()
        project = Project.query.get_or_404(project_id)
        if args['name']:
            project.name = args['name']
        if args['is_active']:
            pass
        db.session.commit()
        return project, 201


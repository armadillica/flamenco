#!/usr/bin/env python

"""
Welcome to the flamenco test suite. Simply run python test.py and check
that all tests pass.

Individual tests can be run with the following syntax:

    python tests.py ServerTestCase.test_job_delete

"""

import os

from application import app
from application import db
from application.modules.managers.model import Manager
from application.modules.jobs.model import Job
from application.modules.projects.model import Project
from application.modules.settings.model import Setting
import unittest
import tempfile
import json

class ServerTestingUtils:

    def add_project(self, is_active=True):
        project = Project(
            name='Auto project')
        db.session.add(project)
        db.session.commit()

        if is_active:
            setting = Setting(
                name='active_project',
                value=str(project.id))
            db.session.add(setting)
            db.session.commit()
        return project.id

    def add_job(self, project_id=None):
        job = Job(
            project_id=1,
            frame_start=1,
            frame_end=10,
            chunk_size=5,
            name='Auto Job',
            format='PNG',
            status='created')
        if project_id:
            job.project_id = project_id
        db.session.add(job)
        db.session.commit()
        return job.id


class ServerTestCase(unittest.TestCase):

    utils = ServerTestingUtils()

    def setUp(self):
        #self.db_fd,
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/server_test.sqlite'
        app.config['TESTING'] = True
        self.app = app.test_client()
        db.create_all()

    def tearDown(self):
        #os.close(self.db_fd)
        os.unlink('/tmp/server_test.sqlite')

    def test_project_create(self):
        cr = self.app.post('/projects', data=dict(name='test',))
        project = json.loads(cr.data)
        assert project['id'] == 1
        assert project['name'] == 'test'

    def test_project_create_default(self):
        cr = self.app.post('/projects', data=dict(name='test', is_active=True))
        project = json.loads(cr.data)
        assert project['is_active'] == True

    def test_project_delete(self):
        project_id = self.utils.add_project(is_active=True)
        rm = self.app.delete('/projects/{0}'.format(project_id))
        assert rm.status_code == 204

    def test_project_update(self):
        cr = self.app.post('/projects', data=dict(name='test', is_active=True))
        ed = self.app.put('/projects/1', data=dict(name='test_edit'))
        assert ed.status_code == 201
        project = json.loads(ed.data)
        assert project['name'] == 'test_edit'

    def test_project_update_default(self):
        cr = self.app.post('/projects', data=dict(name='test', is_active=True))
        ed = self.app.put('/projects/1', data=dict(name='test_edit', is_active=False))
        assert ed.status_code == 201
        project = json.loads(ed.data)
        assert project['name'] == 'test_edit'

    def test_manager_get_informations(self):
        cr = self.app.get('/managers')
        manager = json.loads(cr.data)
        assert manager['debian']['name'] == 'debian'
        assert manager['debian']['ip_address'] == '127.0.0.1'
        assert manager['debian']['port'] == 5000

    def test_settings_create(self):
        cr = self.app.post('/settings',
            data=dict(
                blender_path_linux='/home/flamenco/blender',
                render_settings_path_linux='/home/flamenco/render'))
        assert cr.status_code == 204
        ed = self.app.get('/settings')
        settings = json.loads(ed.data)
        assert settings['blender_path_linux'] == '/home/flamenco/blender'
        assert settings['render_settings_path_linux'] == '/home/flamenco/render'

    def test_job_create(self):
        project_id = self.utils.add_project(is_active=True)
        job = {
            'project_id' : project_id,
            'frame_start' : 1,
            'frame_end' : 100,
            'chunk_size' : 10,
            'current_frame' : 1,
            'name' : 'job_1',
            'format' : 'PNG',
            'status' : 'running'
        }

        cr = self.app.post('/jobs', data=job)
        assert cr.status_code == 201

    def test_job_update(self):
        # Create one job
        job_id = self.utils.add_job()

        data = { 'name' : 'job_2'}
        up = self.app.put('/jobs/{0}'.format(job_id), data=data)
        job = json.loads(up.data)
        assert 'job_2' == job['name']

        re = self.app.get('/jobs/{0}'.format(job_id))
        job = json.loads(re.data)
        assert 'job_2' == job['name']

    def test_job_delete(self):
        # Create one job
        project_id = self.utils.add_project(is_active=True)
        job_id = self.utils.add_job(project_id=project_id)
        # Delete the job (using the returned job id)
        cr = self.app.delete('/jobs/{0}'.format(job_id))
        assert cr.status_code == 204

    def test_job_start(self):
        # Create one job
        project_id = self.utils.add_project(is_active=True)
        job_id = self.utils.add_job(project_id=project_id)

        data = { 'command' : 'start'}
        up = self.app.put('/jobs/{0}'.format(job_id), data=data)
        job = json.loads(up.data)
        assert 'running' == job['status']

    def test_job_stop(self):
        # Create one job
        project_id = self.utils.add_project(is_active=True)
        job_id = self.utils.add_job(project_id=project_id)

        data = { 'command' : 'start'}
        up = self.app.put('/jobs/{0}'.format(job_id), data=data)

        data = { 'command' : 'stop'}
        up = self.app.put('/jobs/{0}'.format(job_id), data=data)
        job = json.loads(up.data)
        assert 'canceled' == job['status']


if __name__ == '__main__':
    unittest.main()

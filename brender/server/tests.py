import os
from application import app
from application import db
import unittest
import tempfile
import json


class ServerTestCase(unittest.TestCase):

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
        cr = self.app.post('/projects', data=dict(name='test', is_active=True))
        rm = self.app.delete('/projects/1')
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


if __name__ == '__main__':
    unittest.main()

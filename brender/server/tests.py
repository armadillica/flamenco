import os
from application import app
from application import db
from application.modules.workers.model import Worker
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
        # add fake worker
        worker = Worker(mac_address=42,
                hostname="debian",
                status="enabled",
                system="Linux",
                ip_address="127.0.0.1:5000",
                connection="offline")
        db.session.add(worker)
        db.session.commit()

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

    def test_worker_get_informations(self):
        cr = self.app.get("/workers")
        worker = json.loads(cr.data)
        assert worker['debian']['hostname'] == "debian"
        assert worker['debian']['ip_address'] == "127.0.0.1:5000"
        assert worker['debian']['connection'] == "offline"

    def test_worker_change_status(self):
        cr = self.app.post("/workers", data=dict(id="1", status="disabled"))
        assert cr.status_code == 204
        ed = self.app.get("/workers")
        worker = json.loads(ed.data)
        assert worker['debian']['status'] == "disabled"

    def test_settings_create(self):
        cr = self.app.post("/settings", data=dict(blender_path_linux="/home/brender/blender",
                                                  render_settings_path_linux="/home/brender/render"))
        assert cr.status_code == 204
        ed = self.app.get("/settings")
        settings = json.loads(ed.data)
        assert settings['blender_path_linux'] == "/home/brender/blender"
        assert settings['render_settings_path_linux'] == "/home/brender/render"

if __name__ == '__main__':
    unittest.main()

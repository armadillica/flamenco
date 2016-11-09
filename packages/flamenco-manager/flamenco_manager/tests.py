#!/usr/bin/env python

"""
Welcome to the flamenco test suite. Simply run python test.py and check
that all tests pass.

Individual tests can be run with the following syntax:

    python tests.py ManagerTestCase.test_task_delete

"""

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
        worker = Worker(hostname='debian',
                status='enabled',
                connection='offline',
                system='Linux',
                ip_address='127.0.0.1',
                port=5000)
        db.session.add(worker)
        db.session.commit()

    def tearDown(self):
        #os.close(self.db_fd)
        os.unlink('/tmp/server_test.sqlite')


    def test_worker_get_informations(self):
        cr = self.app.get('/workers')
        worker = json.loads(cr.data)
        assert worker['debian']['hostname'] == 'debian'
        assert worker['debian']['ip_address'] == '127.0.0.1'
        assert worker['debian']['port'] == 5000


    def test_worker_change_status(self):
        cr = self.app.patch('/workers/1', data=dict(status='disabled'))
        worker = json.loads(cr.data)
        assert worker['status'] == 'disabled'



if __name__ == '__main__':
    unittest.main()

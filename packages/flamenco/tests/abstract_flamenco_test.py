# -*- encoding: utf-8 -*-
import copy

from eve.methods.post import post_internal

import pillarsdk
import pillar.tests
import pillar.auth
import pillar.tests.common_test_data as ctd
from pillar.tests import PillarTestServer, AbstractPillarTest


class FlamencoTestServer(PillarTestServer):
    def __init__(self, *args, **kwargs):
        PillarTestServer.__init__(self, *args, **kwargs)

        from flamenco import FlamencoExtension
        self.load_extension(FlamencoExtension(), '/flamenco')


class AbstractFlamencoTest(AbstractPillarTest):
    pillar_server_class = FlamencoTestServer

    def setUp(self, **kwargs):
        AbstractPillarTest.setUp(self, **kwargs)
        self.tmngr = self.flamenco.task_manager
        self.jmngr = self.flamenco.job_manager

        self.proj_id, self.project = self.ensure_project_exists()

        self.sdk_project = pillarsdk.Project(pillar.tests.mongo_to_sdk(self.project))

    def tearDown(self):
        self.unload_modules('flamenco')
        AbstractPillarTest.tearDown(self)

    @property
    def flamenco(self):
        return self.app.pillar_extensions['flamenco']

    def ensure_project_exists(self, project_overrides=None):
        from flamenco.setup import setup_for_flamenco

        project_overrides = dict(
            picture_header=None,
            picture_square=None,
            **(project_overrides or {})
        )
        proj_id, project = AbstractPillarTest.ensure_project_exists(
            self, project_overrides)

        with self.app.test_request_context():
            flamenco_project = setup_for_flamenco(
                project['url'], replace=True)

        return proj_id, flamenco_project

    def create_manager(self):

        mngr_doc = {
            'name': u'tēst mānēgūr',
            'description': u'£euk h€',
            'host': 'https://[::1]:8123/',
            'job_types': {
                'sleep_simple': {
                    'vars': {}
                }
            },
        }
        with self.app.test_request_context():
            r, _, _, status = post_internal('flamenco.managers', mngr_doc)

        self.assertEqual(201, status, 'Status %i creating manager: %s' % (status, r))

        mngr_doc.update(r)
        return mngr_doc

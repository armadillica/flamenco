# -*- encoding: utf-8 -*-

import pillarsdk
import pillar.tests
import pillar.auth

from pillar.tests import PillarTestServer, AbstractPillarTest
from pillar.tests import common_test_data as ctd


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

    def create_manager_service_account(
            self,
            email=u'testmanager@example.com',
            name=u'tēst mānēgūr',
            url=u'https://username:password@[fe80::42:99ff:fe66:91bd]:5123/path/to/'):
        from flamenco.setup import create_manager
        from pillar.api.utils.authentication import force_cli_user

        # Main project will have a manager, job, and tasks.
        with self.app.test_request_context():
            force_cli_user()
            mngr_doc, account, token = create_manager(email, name, u'descr', url)

        return mngr_doc, account, token

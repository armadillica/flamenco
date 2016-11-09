from pillar.tests import PillarTestServer, AbstractPillarTest

MOCK_SVN_URL = 'svn://biserver/mocked'


class AttractTestServer(PillarTestServer):
    def __init__(self, *args, **kwargs):
        PillarTestServer.__init__(self, *args, **kwargs)

        from attract import AttractExtension
        self.load_extension(AttractExtension(), '/attract')


class AbstractAttractTest(AbstractPillarTest):
    pillar_server_class = AttractTestServer

    def tearDown(self):
        from attract import subversion

        subversion.task_logged._clear_state()
        self.unload_modules('attract')

        AbstractPillarTest.tearDown(self)

    def ensure_project_exists(self, project_overrides=None):
        from attract.setup import setup_for_attract

        project_overrides = dict(
            picture_header=None,
            picture_square=None,
            **(project_overrides or {})
        )
        proj_id, project = AbstractPillarTest.ensure_project_exists(self, project_overrides)

        with self.app.test_request_context():
            attract_project = setup_for_attract(project['url'],
                                                replace=True,
                                                svn_url=MOCK_SVN_URL)

        return proj_id, attract_project

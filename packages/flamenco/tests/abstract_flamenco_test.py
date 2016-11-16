from pillar.tests import PillarTestServer, AbstractPillarTest

MOCK_SVN_URL = 'svn://biserver/mocked'


class FlamencoTestServer(PillarTestServer):
    def __init__(self, *args, **kwargs):
        PillarTestServer.__init__(self, *args, **kwargs)

        from flamenco import FlamencoExtension
        self.load_extension(FlamencoExtension(), '/flamenco')


class AbstractFlamencoTest(AbstractPillarTest):
    pillar_server_class = FlamencoTestServer

    def tearDown(self):

        self.unload_modules('flamenco')

        AbstractPillarTest.tearDown(self)

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
            flamenco_project = setup_for_flamenco(project['url'],
                                                replace=True,
                                                svn_url=MOCK_SVN_URL)

        return proj_id, flamenco_project

from pathlib import Path

from test_runner import AbstractCommandTest


class MergeProgressiveRendersCommandTest(AbstractCommandTest):
    def setUp(self):
        super().setUp()

        from flamenco_worker.runner import MergeProgressiveRendersCommand
        import tempfile

        self.tmpdir = tempfile.TemporaryDirectory()
        self.mypath = Path(__file__).parent

        self.cmd = MergeProgressiveRendersCommand(
            worker=self.fworker,
            task_id='12345',
            command_idx=0,
        )

    def tearDown(self):
        super().tearDown()
        del self.tmpdir

    def test_happy_flow(self):
        output = Path(self.tmpdir.name) / 'merged.exr'

        settings = {
            'blender_cmd': self.find_blender_cmd(),
            'input1': str(self.mypath / 'Corn field-1k.exr'),
            'input2': str(self.mypath / 'Deventer-1k.exr'),
            'weight1': 20,
            'weight2': 100,
            'output': str(output)
        }

        task = self.cmd.run(settings)
        ok = self.loop.run_until_complete(task)
        self.assertTrue(ok)

        # Assuming that if the files exist, the merge was ok.
        self.assertTrue(output.exists())
        self.assertTrue(output.is_file())
        self.assertTrue(output.with_suffix('.jpg').exists())
        self.assertTrue(output.with_suffix('.jpg').is_file())

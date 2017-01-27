from test_runner import AbstractCommandTest


class MoveOutOfWayTest(AbstractCommandTest):
    def setUp(self):
        super().setUp()

        from flamenco_worker.runner import MoveOutOfWayCommand
        import tempfile

        self.tmpdir = tempfile.TemporaryDirectory()
        self.cmd = MoveOutOfWayCommand(
            worker=self.fworker,
            task_id='12345',
            command_idx=0,
        )

    def tearDown(self):
        del self.tmpdir

    def test_nonexistant_source(self):
        from pathlib import Path

        src = Path(self.tmpdir.name) / 'nonexistant-dir'
        task = self.cmd.run({'src': str(src)})
        ok = self.loop.run_until_complete(task)

        self.assertTrue(ok)
        self.assertFalse(src.exists())

    def test_existing_source(self):
        from pathlib import Path
        import os

        src = Path(self.tmpdir.name) / 'existing-dir'
        src.mkdir()
        os.utime(str(src), (1330712280, 1330712292))  # fixed (atime, mtime) for testing

        task = self.cmd.run({'src': str(src)})
        ok = self.loop.run_until_complete(task)
        self.assertTrue(ok)

        dst = src.with_name('existing-dir-2012-03-02T19:18:12')
        self.assertTrue(dst.exists())
        self.assertFalse(src.exists())

    def test_source_is_file(self):
        from pathlib import Path
        import os

        src = Path(self.tmpdir.name) / 'existing-file'
        src.touch(exist_ok=False)
        os.utime(str(src), (1330712280, 1330712292))  # fixed (atime, mtime) for testing

        task = self.cmd.run({'src': str(src)})
        ok = self.loop.run_until_complete(task)
        self.assertTrue(ok)

        dst = src.with_name('existing-file-2012-03-02T19:18:12')
        self.assertTrue(dst.exists())
        self.assertTrue(dst.is_file())
        self.assertFalse(src.exists())

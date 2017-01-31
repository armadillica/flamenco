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
        super().tearDown()
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
        (src / 'src-contents').touch()

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

    def test_existing_source_and_dest(self):
        from pathlib import Path
        import os

        src = Path(self.tmpdir.name) / 'existing-dir'
        src.mkdir()
        (src / 'src-contents').touch()
        os.utime(str(src), (1330712280, 1330712292))  # fixed (atime, mtime) for testing

        existing_dst = src.with_name('existing-dir-2012-03-02T19:18:12')
        existing_dst.mkdir()
        (existing_dst / 'dst-existing-contents').touch()

        existing_dst2 = src.with_name('existing-dir-2012-03-02T19:18:12-2')
        existing_dst2.mkdir()
        (existing_dst2 / 'dst2-existing-contents').touch()

        existing_dst4 = src.with_name('existing-dir-2012-03-02T19:18:12-4')
        existing_dst4.mkdir()
        (existing_dst4 / 'dst4-existing-contents').touch()

        task = self.cmd.run({'src': str(src)})
        ok = self.loop.run_until_complete(task)
        self.assertTrue(ok)

        # The existing destination directories should not have been touched.
        self.assertTrue(existing_dst.exists())
        self.assertTrue(existing_dst2.exists())
        self.assertTrue(existing_dst4.exists())
        self.assertTrue((existing_dst / 'dst-existing-contents').exists())
        self.assertTrue((existing_dst2 / 'dst2-existing-contents').exists())
        self.assertTrue((existing_dst4 / 'dst4-existing-contents').exists())

        # The source should have been moved to the new destination.
        new_dst = existing_dst.with_name('existing-dir-2012-03-02T19:18:12-5')
        self.assertTrue(new_dst.exists())
        self.assertTrue((new_dst / 'src-contents').exists())

        self.assertFalse(src.exists())

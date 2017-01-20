from unittest.mock import patch, call

from test_runner import AbstractCommandTest


class BlenderRenderTest(AbstractCommandTest):
    def setUp(self):
        super().setUp()

        from flamenco_worker.runner import BlenderRenderCommand

        self.cmd = BlenderRenderCommand(
            worker=self.fworker,
            task_id='12345',
            command_idx=0,
        )

    def test_re_time(self):
        line = '| Time:00:04.17 |'
        m = self.cmd.re_time.search(line)

        self.assertEqual(m.groupdict(), {
            'hours': None,
            'minutes': '00',
            'seconds': '04',
            'hunds': '17',
        })

    def test_parse_render_line(self):
        line = 'Fra:10 Mem:17.52M (0.00M, Peak 33.47M) | Time:00:04.17 | Remaining:00:00.87 | ' \
               'Mem:1.42M, Peak:1.42M | Scene, RenderLayer | Path Tracing Tile 110/135'
        self.assertEqual(
            self.cmd.parse_render_line(line),
            {'fra': 10,
             'mem': '17.52M',
             'peakmem': '33.47M',
             'time_sec': 4.17,
             'remaining_sec': 0.87,
             'status': 'Path Tracing Tile 110/135',
             }
        )

        line = 'Fra:003 Mem:17.52G (0.00M, Peak 33G) | Time:03:00:04.17 | Remaining:44:00:00.87 | ' \
               'Mem:1.42M, Peak:1.42M | Séance, RenderLëør | Computing cosmic flöw 110/13005'
        self.assertEqual(
            self.cmd.parse_render_line(line),
            {'fra': 3,
             'mem': '17.52G',
             'peakmem': '33G',
             'time_sec': 3 * 3600 + 4.17,
             'remaining_sec': 44 * 3600 + 0.87,
             'status': 'Computing cosmic flöw 110/13005',
             }
        )

    def test_missing_files(self):
        """Missing files should not abort the render."""

        line = 'Warning: Unable to open je moeder'
        self.loop.run_until_complete(self.cmd.process_line(line))
        self.fworker.register_task_update.assert_called_once_with(activity=line)

        self.fworker.register_task_update.reset_mock()
        line = "Warning: Path 'je moeder' not found"
        self.loop.run_until_complete(self.cmd.process_line(line))
        self.fworker.register_task_update.assert_called_once_with(activity=line)

    @patch('pathlib.Path')
    def test_cli_args(self, mock_path):
        """Test that CLI arguments in the blender_cmd setting are handled properly."""
        import subprocess
        from mock_responses import CoroMock

        settings = {
            'blender_cmd': '/path/to/blender --with --cli="args for CLI"',
            'chunk_size': 100,
            'frames': '1..2',
            'format': 'JPEG',
            'filepath': '/path/to/output',
        }

        mock_path.Path.exists.side_effect = [True, True]

        cse = CoroMock()
        cse.coro.return_value.wait = CoroMock(return_value=0)
        with patch('asyncio.create_subprocess_exec', new=cse) as mock_cse:
            self.loop.run_until_complete(self.cmd.run(settings))

            mock_path.assert_has_calls([
                call('/path/to/blender'),
                call().exists(),
                call().exists().__bool__(),
                call('/path/to/output'),
                call().exists(),
                call().exists().__bool__(),
            ])

            mock_cse.assert_called_once_with(
                '/path/to/blender',
                '--with',
                '--cli=args for CLI',
                '--enable-autoexec',
                '-noaudio',
                '--background',
                '/path/to/output',
                '--render-format', 'JPEG',
                '--render-frame', '1..2',
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

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

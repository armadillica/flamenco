from unittest import TestCase


class SomeCommandsTest(TestCase):
    def test_blender_render_name(self):
        from flamenco.job_compilers.commands import BlenderRender

        self.assertEqual('blender_render', BlenderRender.cmdname())

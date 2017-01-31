import unittest


class AbstractWorkerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import logging

        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)-15s %(levelname)8s %(name)s %(message)s',
        )

    def find_blender_cmd(self):
        import os
        import platform

        if platform.system() == 'Windows':
            blender = 'blender.exe'
        else:
            blender = 'blender'

        for path in os.getenv('PATH').split(os.path.pathsep):
            full_path = path + os.sep + blender
            if os.path.exists(full_path):
                return full_path

        self.fail('Unable to find "blender" executable on $PATH')

import unittest


class AbstractWorkerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import logging

        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)-15s %(levelname)8s %(name)s %(message)s',
        )

#!/usr/bin/env python

"""
Welcome to the brender test suite. Simply run python test.py and check
that all tests pass.

Individual tests can be run with the following syntax:

    python tests.py ManagerTestCase.test_task_delete

"""

import os

from application import app
from application import db
import unittest
import tempfile
import json


if __name__ == '__main__':
    unittest.main()

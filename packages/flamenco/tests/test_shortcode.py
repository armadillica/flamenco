# -*- coding=utf-8 -*-


from __future__ import absolute_import

import collections
import datetime
import logging.config
import unittest

from dateutil.tz import tzutc
import mock
import svn.common

from pillar.tests import common_test_data as ctd

import logging_config
from flamenco import subversion
from abstract_flamenco_test import AbstractFlamencoTest

SVN_SERVER_URL = 'svn://biserver/agent327'


class ShortcodeTest(AbstractFlamencoTest):
    def setUp(self, **kwargs):
        AbstractFlamencoTest.setUp(self, **kwargs)

        self.mngr = self.app.pillar_extensions['flamenco'].task_manager
        self.proj_id, self.project = self.ensure_project_exists()

    def test_increment_simple(self):

        from flamenco import shortcodes

        with self.app.test_request_context():
            code = shortcodes.generate_shortcode(self.proj_id, u'jemoeder', u'ø')
        self.assertEqual(u'ø1', code)

        with self.app.test_request_context():
            code = shortcodes.generate_shortcode(self.proj_id, u'jemoeder', u'č')
        self.assertEqual(u'č2', code)

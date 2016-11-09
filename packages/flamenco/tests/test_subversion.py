# -*- coding=utf-8 -*-

"""Unit test for SVN interface."""

from __future__ import absolute_import

import collections
import datetime
import logging.config
import unittest

from dateutil.tz import tzutc
import mock
import svn.common

import logging_config
from abstract_attract_test import AbstractAttractTest

SVN_SERVER_URL = 'svn://biserver/agent327'

logging.config.dictConfig(logging_config.LOGGING)

# Unfortunately, the svn module doesn't use classes, but uses in-function-defined
# namedtuples instead. As a result, we can't import them, but have to recreate.
LogEntry = collections.namedtuple('LogEntry', ['date', 'msg', 'revision', 'author', 'changelist'])

SVN_LOG_BATCH_1 = [
    LogEntry(date=datetime.datetime(2016, 4, 5, 10, 8, 5, 19211, tzinfo=tzutc()),
             msg='Initial commit', revision=43, author='fsiddi', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 8, 13, 5, 39, 42537, tzinfo=tzutc()),
             msg='Initial commit of layout files', revision=44, author='hjalti', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 8, 13, 6, 18, 947830, tzinfo=tzutc()),
             msg=None, revision=45, author='andy', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 8, 14, 22, 24, 411916, tzinfo=tzutc()),
             msg="Add the eye lattices to the main group\n\nOtherwise when you link the agent group, those two lattices would be\nlinked as regular objects, and you'd need to move both proxy+lattices\nindividually.\n\n\n",
             revision=46, author='pablo', changelist=None),
]

SVN_LOG_BATCH_2 = [
    LogEntry(date=datetime.datetime(2016, 4, 13, 17, 54, 50, 244305, tzinfo=tzutc()),
             msg='first initial agent model rework.', revision=47, author='andy', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 14, 15, 57, 30, 951714, tzinfo=tzutc()),
             msg='third day of puching verts around', revision=48, author='andy', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 21, 8, 21, 19, 390478, tzinfo=tzutc()),
             msg='last weeks edit. a couple of facial expression tests.\nstarting to modify the agent head heavily... W A R N I N G',
             revision=49, author='andy', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 25, 9, 18, 17, 23841, tzinfo=tzutc()),
             msg='some expression tests.', revision=50, author='andy', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 25, 10, 12, 23, 233796, tzinfo=tzutc()),
             msg='older version of the layout', revision=51, author='hjalti', changelist=None),
]

SVN_LOG_BATCH_WITH_TASK_MARKERS = [
    LogEntry(date=datetime.datetime(2016, 4, 5, 10, 8, 5, 19211, tzinfo=tzutc()),
             msg='Initial commit', revision=1, author='fsiddi', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 8, 13, 5, 39, 42537, tzinfo=tzutc()),
             msg='[T1234] modeled Hendrik IJzerbroot', revision=2, author='andy', changelist=None),
    LogEntry(date=datetime.datetime(2016, 4, 8, 13, 6, 18, 947830, tzinfo=tzutc()),
             msg='[T4415] scene layout, which also closes [T4433]', revision=3, author='hjalti',
             changelist=None),
]


class TestCommitLogObserver(unittest.TestCase):
    def setUp(self):
        from attract import subversion

        self.client = subversion.obtain(SVN_SERVER_URL)
        # Passing in a real client to Mock() will ensure that isinstance() checks return True.
        self.mock_client = mock.Mock(self.client, name='svn_client')
        self.observer = subversion.CommitLogObserver(self.mock_client)

    def _test_actual(self):
        """For performing a quick test against the real SVN server.

        Keep the underscore in the name when committing, and don't call it from
        anywhere. Unit tests shouldn't be dependent on network connections.
        """
        from attract import subversion

        observer = subversion.CommitLogObserver(self.client)
        observer.fetch_and_observe()

    def test_empty_log(self):
        self.mock_client.log_default = mock.Mock(name='log_default', return_value=[])
        self.observer.fetch_and_observe()

        self.mock_client.log_default.assert_called_once_with(revision_from=1)

        # Should not have changed from the default.
        self.assertEqual(self.observer.last_seen_revision, 0)

    def test_two_log_calls(self):
        self.mock_client.log_default = mock.Mock(name='log_default')
        self.mock_client.log_default.side_effect = [
            # First call, only four commits.
            SVN_LOG_BATCH_1,
            # Second call, five commits.
            SVN_LOG_BATCH_2
        ]

        self.observer.last_seen_revision = 42

        self.observer.fetch_and_observe()
        self.mock_client.log_default.assert_called_with(revision_from=43)
        self.assertEqual(self.observer.last_seen_revision, 46)

        self.observer.fetch_and_observe()
        self.mock_client.log_default.assert_called_with(revision_from=47)

        self.assertEqual(self.observer.last_seen_revision, 51)

    def test_task_markers(self):
        from attract import subversion

        self.mock_client.log_default = mock.Mock(name='log_default',
                                                 return_value=SVN_LOG_BATCH_WITH_TASK_MARKERS)
        blinks = []

        def record_blink(sender, **kwargs):
            self.assertIs(self.observer, sender)
            blinks.append(kwargs)

        subversion.task_logged.connect(record_blink)

        self.observer.fetch_and_observe()

        self.assertEqual(3, len(blinks))
        self.assertEqual({'log_entry': SVN_LOG_BATCH_WITH_TASK_MARKERS[1], 'shortcode': 'T1234'},
                         blinks[0])
        self.assertEqual({'log_entry': SVN_LOG_BATCH_WITH_TASK_MARKERS[2], 'shortcode': 'T4415'},
                         blinks[1])
        self.assertEqual({'log_entry': SVN_LOG_BATCH_WITH_TASK_MARKERS[2], 'shortcode': 'T4433'},
                         blinks[2])

    def test_svn_error(self):
        """SVN errors should not crash the observer."""
        from attract import subversion

        self.mock_client.log_default = mock.Mock(name='log_default',
                                                 side_effect=svn.common.SvnException('unittest'))

        record_blink = mock.Mock(name='record_blink',
                                 spec={'__name__': 'record_blink'})
        subversion.task_logged.connect(record_blink)

        self.observer.fetch_and_observe()

        record_blink.assert_not_called()
        self.mock_client.log_default.assert_called_once()

    def test_create_log_entry(self):
        from attract import subversion

        entry = subversion.create_log_entry(date_text=u'2016-10-21 17:40:17 +0200',
                                            msg=u'Ünicøde is good',
                                            revision='123',
                                            author=u'børk',
                                            changelist='nothing')
        self.assertEqual(tuple(entry), (
            datetime.datetime(2016, 10, 21, 15, 40, 17, 0, tzinfo=tzutc()),
            u'Ünicøde is good',
            '123',
            u'børk',
            'nothing'
        ))

        self.assertRaises(ValueError, subversion.create_log_entry,
                          date_text='Unparseable date',
                          msg=u'Ünicøde is good',
                          revision='123',
                          author=u'børk',
                          changelist='nothing')

        entry = subversion.create_log_entry(date_text=u'2016-10-21 17:40:17 +0200',
                                            msg=u'Ünicøde is good',
                                            revision='123',
                                            author=u'børk')
        self.assertEqual(tuple(entry), (
            datetime.datetime(2016, 10, 21, 15, 40, 17, 0, tzinfo=tzutc()),
            u'Ünicøde is good',
            '123',
            u'børk',
            None
        ))

        entry = subversion.create_log_entry(
            date=datetime.datetime(2016, 10, 21, 15, 40, 17, 0, tzinfo=tzutc()),
            msg=u'Ünicøde is good',
            revision='123',
            author=u'børk')
        self.assertEqual(tuple(entry), (
            datetime.datetime(2016, 10, 21, 15, 40, 17, 0, tzinfo=tzutc()),
            u'Ünicøde is good',
            '123',
            u'børk',
            None
        ))


class PushCommitTest(AbstractAttractTest):
    def setUp(self, **kwargs):
        AbstractAttractTest.setUp(self, **kwargs)

        self.mngr = self.app.pillar_extensions['attract'].task_manager
        self.proj_id, self.project = self.ensure_project_exists()

    def test_push_happy(self):
        from attract import cli, subversion

        with self.app.test_request_context():
            _, token = cli.create_svner_account('svner@example.com', self.project['url'])

        blinks = []

        def record_blink(sender, **kwargs):
            blinks.append(kwargs)

        subversion.task_logged.connect(record_blink)

        push_data = {
            'repo': u'strange-repo™',
            'revision': '4',
            'msg': u'မြန်မာဘာသာ is beautiful.\n\nThis solves task [T431134]',
            'author': 'Haha',
            'date': '2016-10-21 17:40:17 +0200',
        }

        self.post('/attract/api/%s/subversion/log' % self.project['url'],
                  json=push_data,
                  auth_token=token['token'])

        self.assertEqual(1, len(blinks))
        self.assertEqual(u'T431134', blinks[0]['shortcode'])
        self.assertEqual(u'မြန်မာဘာသာ is beautiful.\n\nThis solves task [T431134]',
                         blinks[0]['log_entry'].msg)
        self.assertEqual(datetime.datetime(2016, 10, 21, 15, 40, 17, 0, tzinfo=tzutc()),
                         blinks[0]['log_entry'].date)

"""Subversion interface."""

from __future__ import absolute_import

import collections
import dateutil.parser
import re

import attr
import blinker
import svn.remote
import svn.common
from pillar import attrs_extra

task_logged = blinker.NamedSignal('task_logged')
marker_re = re.compile(r'\[(?P<codetype>[TS])(?P<shortcode>[0-9a-zA-Z]+)\]')

signals = {
    'T': task_logged,
}

# Copy of namedtuple defined in svn.common.log_default().
LogEntry = collections.namedtuple(
    'LogEntry',
    ['date', 'msg', 'revision', 'author', 'changelist']
)


def create_log_entry(**namedfields):
    date = namedfields.pop('date', None)
    date_text = namedfields.pop('date_text', None)
    if bool(date) == bool(date_text):
        raise ValueError('Either date or date_text must be given.')

    if date_text is not None:
        date = dateutil.parser.parse(date_text)
    changelist = namedfields.pop('changelist', None)

    return LogEntry(date=date, changelist=changelist, **namedfields)


def obtain(server_location):
    """Returns a Connection object for the given server location."""

    return svn.remote.RemoteClient(server_location)


@attr.s
class CommitLogObserver(object):
    svn_client = attr.ib(default=None,
                         validator=attr.validators.optional(
                             attr.validators.instance_of(svn.remote.RemoteClient)))
    last_seen_revision = attr.ib(default=0, validator=attr.validators.instance_of(int))
    _log = attrs_extra.log('%s.CommitLogObserver' % __name__)

    def fetch_and_observe(self):
        """Obtains task IDs from SVN logs."""

        self._log.debug('%s: fetch_and_observe()', self)

        try:
            svn_log = self.svn_client.log_default(revision_from=self.last_seen_revision + 1)
            for log_entry in svn_log:
                self._log.debug('- %r', log_entry)

                # assumption: revisions are always logged in strictly increasing order.
                self.last_seen_revision = log_entry.revision

                # Log entries can be None.
                if not log_entry.msg:
                    continue

                self.process_log(log_entry)

        except svn.common.SvnException:
            # The SVN library just raises a SvnException when something goes wrong,
            # without any structured indication of the error. There isn't much else
            # we can do, except to log the error and return.
            self._log.exception('Error calling self.svn_client.log_default()')
            return

    def process_log(self, log_entry):
        """Obtains task IDs without accessing the SVN server directly.

        :type log_entry: LogEntry
        """

        self._log.debug('%s: process_log() rev=%s, author=%s',
                        self, log_entry.revision, log_entry.author)
        tasks_found = 0
        for codetype, shortcode in self._find_ids(log_entry.msg):
            signal = signals[codetype]
            self._log.debug('Sending signal %s with shortcode=%s%s', signal, codetype, shortcode)
            signal.send(self, shortcode='%s%s' % (codetype, shortcode), log_entry=log_entry)
            tasks_found += 1

    def _find_ids(self, message):
        # Parse the commit log to see if there are any task/shot markers.
        for match in marker_re.finditer(message[:1024]):
            codetype = match.group('codetype')
            shortcode = match.group('shortcode')
            yield codetype, shortcode

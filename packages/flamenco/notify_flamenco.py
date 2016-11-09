#!/usr/bin/env python3

"""To be called as SVN post-commit hook.

Stupidly simple, only pushes this commit, doesn't register which commits were
pushed and which weren't, doesn't retry anything later.

Example call:
    notify_flamenco.py "$REPOS" "$REV"
"""

import json
import os.path
import subprocess
import sys

try:
    # Try Python 3 import first
    from urllib import parse
except ImportError:
    # If it fails, fall back to Python 2
    import urlparse as parse

import requests

# ################# CONFIGURE THIS FOR YOUR OWN PROJECT/FLAMENCO ##############################
AUTH_TOKEN = 'SRVNZNxzvaDnnewyoq7IGiHufcrT4nsXiay2W8Jz3AxA8A'
PILLAR_URL = 'http://pillar-web:5001/'
PROJECT_URLS = {  # Mapping from SVN repository name to Flamenco project URL.
    'repo': 'sybren',
}
# ################# END OF CONFIGURATION ##############################

svn_repo = sys.argv[1]
svn_revision = int(sys.argv[2])

repo_basename = os.path.basename(svn_repo)
try:
    project_url = PROJECT_URLS[repo_basename]
except KeyError:
    raise SystemExit('Not configured for repository %r' % repo_basename)

url = parse.urljoin(PILLAR_URL, '/flamenco/api/%s/subversion/log' % project_url)


def svnlook(subcmd):
    info = subprocess.check_output(['/usr/bin/svnlook', subcmd, svn_repo, '-r', str(svn_revision)])
    return info.decode('utf8').strip()


data = {
    'repo': svn_repo,
    'revision': svn_revision,
    'msg': svnlook('log'),
    'author': svnlook('author'),
    'date': svnlook('date').split(' (', 1)[0],
}

print('POSTing to %s' % url)
print('DATA:')
print(json.dumps(data, indent=4))
resp = requests.post(url, json=data, auth=(AUTH_TOKEN, ''))
sys.stderr.write(resp.text)

#!/usr/bin/env python3
import json
import pprint

import requests

job_attrs = {
    'status': 'queued',
    'priority': 50,
    'name': 'sleepy',
    'settings': {
        'cmd': '/bin/sleep 30'
    },
    'job_type': 'exec-command',
    'user': '580f8c66983773759afdb20e',
    'manager': '59a8226d98377348c35af177',
    'project': '57bc5c2e98377312f0c4d564',
}

resp = requests.post('http://cloud.local:5001/api/flamenco/jobs', json=job_attrs,
                     auth=('s2iEzlBo0rHmBGZSTOXbdK6E2FwWl9', ''))
if resp.status_code == 204:
    print('Job created.')
    print(resp.headers)
else:
    print('Response:')
    if resp.headers['content-type'] == 'application/json':
        pprint.pprint(resp.json())
    else:
        print(resp.text)

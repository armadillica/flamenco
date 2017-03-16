#!/usr/bin/python3

import requests
import pprint
import gzip
import base64

data = [{
    '_id': '000000009837737431cd0d43',
    'task_id': '58919fce9837737431cd0d43',
    'received_on_manager': '2017-01-18T09:49:45.459+0100',
    'gz_log': base64.b64encode(gzip.compress('je moeder'.encode('utf8'))).decode('ascii'),
}]

resp = requests.post(
    'http://pillar-web:5001/api/flamenco/managers/585a795698377345814d2f68/task-update-batch',
    json=data,
    auth=('SRVlyGuyoYwIUGdZRmyGdLJjLvcBgNFt5h42DdX2IW0ZTI', ''),
)
resp.raise_for_status()

pprint.pprint(resp.json())

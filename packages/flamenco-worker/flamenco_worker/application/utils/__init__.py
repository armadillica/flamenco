import logging
import requests

def http_request(ip_address, command, method, params=None, files=None):
    global CONNECTIVITY
    if method == 'delete':
        r = requests.delete('http://' + ip_address + command)
    elif method == 'post':
        r = requests.post('http://' + ip_address + command, data=params, files=files)
    elif method == 'get':
        r = requests.get('http://' + ip_address + command)
    elif method == 'put':
        r = requests.put('http://' + ip_address + command, data=params)
    elif method == 'patch':
        r = requests.patch('http://' + ip_address + command, data=params)

    if r.status_code == 404:
        return '', 404

    # Only for debug
    if r.status_code == 400:
        for chunk in r.iter_content(50):
            print chunk
        return '', 404

    if r.status_code == 204:
        return '', 204

    if r.status_code >= 500:
        logging.debug("STATUS CODE: %d" % r.status_code)
        return '', 500

    return r.json()

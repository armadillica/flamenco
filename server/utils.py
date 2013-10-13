import urllib

def http_request(ip_address, command, post_params = None):
    # post_params must be a dictionay
    if post_params:
        params = urllib.urlencode(post_params)
        f = urllib.urlopen('http://' + ip_address + command, params)
    else:
        f = urllib.urlopen('http://' + ip_address + command)

    print 'message sent, reply follows:'
    print f.read()

def list_integers_string(string_list):
    """Accepts comma separated string list of integers"""
    integers_list = string_list.split(',')
    integers_list = map(int, integers_list)
    return integers_list

def frame_percentage(item):
    if item.frame_start == item.current_frame:
            return 0
    else:
        frame_count = item.frame_end - item.frame_start + 1
        current_frame = item.current_frame - item.frame_start + 1
        percentage_done = 100 / frame_count * current_frame
        return percentage_done

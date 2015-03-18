import datetime

def seconds_to_time(seconds):
    if not type(seconds) in [int, float]:
        return
    return str(datetime.timedelta(seconds=seconds))

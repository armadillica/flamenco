
from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Patch


class Job(List, Find, Patch):
    """Job class wrapping the REST nodes endpoint
    """
    path = 'flamenco/jobs'
    ensure_query_projections = {'project': 1}


from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Patch


class Manager(List, Find, Patch):
    """Manager class wrapping the REST nodes endpoint
    """
    path = 'flamenco/managers'
    ensure_query_projections = {'projects': 1}

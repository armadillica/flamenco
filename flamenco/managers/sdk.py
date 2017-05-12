from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Patch
from pillarsdk import Resource, Project


class Manager(List, Find, Patch):
    """Manager class wrapping the REST nodes endpoint
    """
    path = 'flamenco/managers'
    ensure_query_projections = {'projects': 1}

    def linked_projects(self, *, page=1, max_results=250, api) -> Resource:
        """Returns the projects linked to this Manager."""

        if not self.projects:
            return Resource({
                '_items': [],
                '_meta': {
                    'total': 0,
                    'page': 1,
                    'max_results': 250,
                }
            })

        fetched = Project.all(
            {
                'where': {
                    '_id': {'$in': self.projects}
                },
                'projection': {
                    '_id': 1,
                    'name': 1,
                    'url': 1,
                },
                'page': page,
                'max_results': max_results,
            },
            api=api)
        return fetched

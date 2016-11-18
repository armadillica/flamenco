from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Create
from pillarsdk.resource import Post
from pillarsdk.resource import Update
from pillarsdk.resource import Delete
from pillarsdk.resource import Replace
from . import Api

class Task(List, Find, Create, Post, Update, Delete, Replace):
    """Task class wrapping the REST nodes endpoint
    """
    path = "tasks"
    ensure_query_projections = {'project': 1}


    @classmethod
    def get_new(cls, api=None):
        scheduler_path = 'scheduler/tasks'
        api = api or Api.Default()
        response = api.get(scheduler_path)
        return cls(response)

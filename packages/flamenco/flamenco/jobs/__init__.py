"""Job management."""

import attr
import flask_login
import pillarsdk
from pillar import attrs_extra
from pillar.web.system_util import pillar_api

from pillarsdk.resource import List
from pillarsdk.resource import Find
from pillarsdk.resource import Create
from pillarsdk.resource import Post
from pillarsdk.resource import Update
from pillarsdk.resource import Delete
from pillarsdk.resource import Replace
from pillarsdk.exceptions import ResourceNotFound
from pillarsdk import utils as pillarsdk_utils
from pillarsdk import Api


class Job(List, Find, Create, Post, Update, Delete, Replace):
    """Job class wrapping the REST nodes endpoint
    """
    path = 'flamenco/jobs'
    ensure_query_projections = {'project': 1}

    @classmethod
    def find_one(cls, params, api=None):
        """Get one resource starting from parameters different than the resource
        id. TODO if more than one match for the query is found, raise exception.
        """
        api = api or Api.Default()

        # Force delivery of only 1 result
        params['max_results'] = 1
        cls._ensure_projections(params, cls.ensure_query_projections)
        url = pillarsdk_utils.join_url_params(cls.path, params)

        response = api.get(url)
        # Keep the response a dictionary, and cast it later into an object.
        if response['_items']:
            item = pillarsdk_utils.convert_datetime(response['_items'][0])
            return cls(item)
        else:
            raise ResourceNotFound(response)


@attr.s
class JobManager(object):
    _log = attrs_extra.log('%s.JobManager' % __name__)

    def create_job(self, project, job_type):
        """Creates a new job, owned by the current user.

        :rtype: pillarsdk.Node
        """

        api = pillar_api()

        job = dict(
            name='New job',
            job_type=job_type,
            project=project['_id'],
            user=flask_login.current_user.objectid,
            settings={},
        )

        job = pillarsdk.Resource(job)
        job.path = 'flamenco/jobs'
        job.create(api=api)
        return job

    def edit_job(self, job_id, **fields):
        """Edits a job.

        :type job_id: str
        :type fields: dict
        :rtype: pillarsdk.Node
        """

        api = pillar_api()
        job = pillarsdk.Node.find(job_id, api=api)

        job._etag = fields.pop('_etag')
        job.name = fields.pop('name')
        job.description = fields.pop('description')
        job.status = fields.pop('status')
        job.properties.job_type = fields.pop('job_type', '').strip() or None

        users = fields.pop('users', None)
        job.properties.assigned_to = {'users': users or []}

        self._log.info('Saving job %s', job.to_dict())

        if fields:
            self._log.warning('edit_job(%r, ...) called with unknown fields %r; ignoring them.',
                              job_id, fields)

        job.update(api=api)
        return job

    def delete_job(self, job_id, etag):
        api = pillar_api()

        self._log.info('Deleting job %s', job_id)
        job = pillarsdk.Resource({'_id': job_id, '_etag': etag})
        job.path = 'flamenco/jobs'
        job.delete(api=api)

    def jobs_for_user(self, user_id):
        """Returns the jobs for the given user.

        :returns: {'_items': [job, job, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()

        # TODO: also include jobs assigned to any of the user's groups.
        jobs = pillarsdk.resource.List()
        jobs.list_class.path = 'flamenco/jobs'
        j = jobs.all({
            'where': {
                'user': user_id,
            }
        }, api=api)

        return j

    def jobs_for_project(self, project_id):
        """Returns the jobs for the given project.

        :returns: {'_items': [job, job, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()
        jobs = pillarsdk.resource.List()
        jobs.list_class.path = 'flamenco/jobs'
        j = jobs.all({
            'where': {
                'project': project_id,
            }}, api=api)
        return j


def setup_app(app):
    from . import eve_hooks

    eve_hooks.setup_app(app)

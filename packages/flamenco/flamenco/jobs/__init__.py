"""Job management."""

import attr
import flask
import flask_login

import pillarsdk
from pillar import attrs_extra
from pillar.api.activities import register_activity
from pillar.web.system_util import pillar_api
from pillar.api.utils import authentication

from flamenco.node_types.job import node_type_job


@attr.s
class JobManager(object):
    _log = attrs_extra.log('%s.JobManager' % __name__)

    def create_job(self, project, job_type=None, parent=None):
        """Creates a new job, owned by the current user.

        :rtype: pillarsdk.Node
        """

        from pillar.web.jinja import format_undertitle

        api = pillar_api()
        node_type = project.get_node_type(node_type_job['name'])
        if not node_type:
            raise ValueError('Project %s not set up for Flamenco' % project._id)

        node_props = dict(
            name='New job',
            project=project['_id'],
            user=flask_login.current_user.objectid,
            node_type=node_type['name'],
            properties={
                'status': node_type['dyn_schema']['status']['default'],
            },
        )

        if job_type:
            node_props['name'] = format_undertitle(job_type)
            node_props['properties']['job_type'] = job_type
        if parent:
            node_props['parent'] = parent

        job = pillarsdk.Node(node_props)
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
        job.properties.status = fields.pop('status')
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
        job = pillarsdk.Node({'_id': job_id, '_etag': etag})
        job.delete(api=api)

    def jobs_for_user(self, user_id):
        """Returns the jobs for the given user.

        :returns: {'_items': [job, job, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()

        # TODO: also include jobs assigned to any of the user's groups.
        jobs = pillarsdk.Node.all({
            'where': {
                'properties.assigned_to.users': user_id,
                'node_type': node_type_job['name'],
            }
        }, api=api)

        return jobs

    def jobs_for_project(self, project_id):
        """Returns the jobs for the given project.

        :returns: {'_items': [job, job, ...], '_meta': {Eve metadata}}
        """

        api = pillar_api()
        jobs = pillarsdk.Node.all({
            'where': {
                'project': project_id,
                'node_type': node_type_job['name'],
            }}, api=api)
        return jobs

    def api_job_for_shortcode(self, shortcode):
        """Returns the job for the given shortcode.

        :returns: the job Node, or None if not found.
        """

        db = flask.current_app.db()
        job = db['nodes'].find_one({
            'properties.shortcode': shortcode,
            'node_type': node_type_job['name'],
        })

        return job


def setup_app(app):
    from . import eve_hooks

    eve_hooks.setup_app(app)

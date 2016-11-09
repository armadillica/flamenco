"""Shot management."""

import collections
import logging

import attr
import flask
import flask_login
from bson import ObjectId
from eve.methods.put import put_internal
from werkzeug import exceptions as wz_exceptions

import pillarsdk
import pillar.api.utils
from pillar.web.system_util import pillar_api
from pillar.api.nodes.custom import register_patch_handler
from pillar import attrs_extra

from flamenco.node_types import node_type_shot, node_type_task

# From patch operation name to fields that operation may edit.
VALID_PATCH_FIELDS = {
    u'from-blender': {
        u'name',
        u'picture',
        u'properties.trim_start_in_frames',
        u'properties.duration_in_edit_in_frames',
        u'properties.cut_in_timeline_in_frames',
        u'properties.status',
        u'properties.used_in_edit',
    },
    u'from-web': {
        u'properties.status',
        u'properties.notes',
        u'description',
    },
}

VALID_PATCH_OPERATIONS = {
    u'from-blender', u'from-web', u'unlink', u'relink',
}

log = logging.getLogger(__name__)


class ProjectSummary(object):
    """Summary of the shots in a project."""

    def __init__(self):
        self._counts = collections.defaultdict(int)
        self._total = 0

    def count(self, status):
        self._counts[status] += 1
        self._total += 1

    def percentages(self):
        """Generator, yields (status, percentage) tuples.

        The percentage is on a 0-100 scale.
        """

        remaining = 100
        last_index = len(self._counts) - 1

        for idx, status in enumerate(sorted(self._counts.keys())):
            if idx == last_index:
                yield (status, remaining)
                continue

            perc = float(self._counts[status]) / self._total
            whole_perc = int(round(perc * 100))
            remaining -= whole_perc

            yield (status, whole_perc)


@attr.s
class ShotManager(object):
    _log = attrs_extra.log('%s.ShotManager' % __name__)

    def create_shot(self, project):
        """Creates a new shot, owned by the current user.

        :rtype: pillarsdk.Node
        """
        from flamenco import shortcodes

        project_id = project['_id']
        self._log.info('Creating shot for project %s', project_id)

        api = pillar_api()
        node_type = project.get_node_type(node_type_shot['name'])
        if not node_type:
            raise ValueError('Project %s not set up for Flamenco' % project_id)

        node_props = dict(
            name='New shot',
            project=project_id,
            user=flask_login.current_user.objectid,
            node_type=node_type['name'],
            properties={
                'status': node_type['dyn_schema']['status']['default'],
            },
        )

        shot = pillarsdk.Node(node_props)
        shot.create(api=api)
        return shot

    def tasks_for_shots(self, shots, known_task_types):
        """Returns a dict of tasks for each shot.

        :param shots: list of shot nodes.
        :param known_task_types: Collection of task type names. Any task with a
            type not in this list will map the None key.
        :returns: a dict {shot id: tasks}, where tasks is a dict in which the keys are the
            task types, and the values are sets of tasks of that type.
        :rtype: dict

        """

        api = pillar_api()

        id_to_shot = {}
        shot_id_to_tasks = {}
        for shot in shots:
            shot_id = shot['_id']
            id_to_shot[shot_id] = shot
            shot_id_to_tasks[shot_id] = collections.defaultdict(set)

        found = pillarsdk.Node.all({
            'where': {
                'node_type': node_type_task['name'],
                'parent': {'$in': list(id_to_shot.keys())},
            }
        }, api=api)

        known = set(known_task_types)  # for fast lookups

        # Now put the tasks into the right spot.
        for task in found['_items']:
            task_type = task.properties.task_type
            if task_type not in known:
                task_type = None
            shot_id_to_tasks[task.parent][task_type].add(task)

        return shot_id_to_tasks

    def edit_shot(self, shot_id, **fields):
        """Edits a shot.

        :type shot_id: str
        :type fields: dict
        :rtype: pillarsdk.Node
        """

        api = pillar_api()
        shot = pillarsdk.Node({'_id': shot_id})

        patch = {
            'op': 'from-web',
            '$set': {
                'description': fields.pop('description', '').strip() or None,
                'properties.notes': (fields.pop('notes', '') or '').strip() or None,
                'properties.status': fields.pop('status'),
            }
        }
        # shot._etag = fields.pop('_etag')

        self._log.info('Saving shot %s', shot.to_dict())

        if fields:
            self._log.warning('edit_shot(%r, ...) called with unknown fields %r; ignoring them.',
                              shot_id, fields)

        shot.patch(patch, api=api)

    def shot_status_summary(self, project_id):
        """Returns number of shots per shot status for the given project.

        :rtype: ProjectSummary
        """

        api = pillar_api()

        # TODO: turn this into an aggregation call to do the counting on MongoDB.
        shots = pillarsdk.Node.all({
            'where': {
                'node_type': node_type_shot['name'],
                'project': project_id,
            },
            'projection': {
                'properties.status': 1,
            },
            'order': [
                ('properties.status', 1),
            ],
        }, api=api)

        # FIXME: this breaks when we hit the pagination limit.
        summary = ProjectSummary()
        for shot in shots['_items']:
            summary.count(shot['properties']['status'])

        return summary


def node_setattr(node, key, value):
    """Sets a node property by dotted key.

    Modifies the node in-place. Deletes None values.
    """

    set_on = node
    while key and '.' in key:
        head, key = key.split('.', 1)
        set_on = set_on[head]

    if value is None:
        set_on.pop(key, None)
    else:
        set_on[key] = value


@register_patch_handler(node_type_shot['name'])
def patch_shot(node_id, patch):
    assert_is_valid_patch(patch)
    log.info('Patching node %s: %s', node_id, patch)

    # Find the full node, so we can PUT it through Eve for validation.
    nodes_coll = flask.current_app.data.driver.db['nodes']
    node_query = {'_id': node_id,
                  'node_type': node_type_shot['name']}
    node = nodes_coll.find_one(node_query)
    if node is None:
        log.warning('How can node %s not be found?', node_id)
        raise wz_exceptions.NotFound('Node %s not found' % node_id)

    op = patch['op']
    if op in VALID_PATCH_FIELDS:
        # Set the fields
        for key, value in patch['$set'].items():
            node_setattr(node, key, value)
    else:
        # Remaining operations are for marking as 'in use' or 'not in use'.
        if node.get('_deleted', False) and op == u'unlink':
            # We won't undelete a node in response to an unlink request.
            return pillar.api.utils.jsonify({'_deleted': True,
                                             '_etag': node['_etag'],
                                             '_id': node['_id']})

        used_in_edit = {
            u'unlink': False,
            u'relink': True,
        }[op]
        node['properties']['used_in_edit'] = used_in_edit

    node = pillar.api.utils.remove_private_keys(node)
    r, _, _, status = put_internal('nodes', node, _id=node_id)
    return pillar.api.utils.jsonify(r, status=status)


def assert_is_valid_patch(patch):
    """Raises an exception when the patch isn't valid."""

    try:
        op = patch['op']
    except KeyError:
        raise wz_exceptions.BadRequest("PATCH should have a key 'op' indicating the operation.")

    if op not in VALID_PATCH_OPERATIONS:
        valid_ops = u', '.join(sorted(VALID_PATCH_OPERATIONS))
        raise wz_exceptions.BadRequest(u'Operation should be one of %s' % valid_ops)

    if op not in VALID_PATCH_FIELDS:
        # Valid operation, and we don't have to check the fields.
        return

    allowed_fields = VALID_PATCH_FIELDS[op]
    try:
        fields = set(patch['$set'].keys())
    except KeyError:
        raise wz_exceptions.BadRequest("PATCH should have a key '$set' "
                                       "indicating the fields to set.")

    disallowed_fields = fields - allowed_fields
    if disallowed_fields:
        raise wz_exceptions.BadRequest(u"Operation '%s' does not allow you to set fields %s" % (
            op, disallowed_fields
        ))


def setup_app(app):
    from . import eve_hooks

    eve_hooks.setup_app(app)

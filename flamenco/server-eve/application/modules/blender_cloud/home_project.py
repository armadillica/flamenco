import copy
import logging
import datetime

from bson import ObjectId, tz_util
from eve.methods.post import post_internal
from eve.methods.put import put_internal
from eve.methods.get import get
from flask import Blueprint, g, current_app, request
from werkzeug import exceptions as wz_exceptions

from application.modules import projects
from application import utils
from application.utils import authentication, authorization

blueprint = Blueprint('blender_cloud.home_project', __name__)
log = logging.getLogger(__name__)

# Users with any of these roles will get a home project.
HOME_PROJECT_USERS = set()

# Users with any of these roles will get full write access to their home project.
HOME_PROJECT_WRITABLE_USERS = {u'subscriber', u'demo'}

HOME_PROJECT_DESCRIPTION = ('# Your home project\n\n'
                            'This is your home project. It allows synchronisation '
                            'of your Blender settings using the [Blender Cloud addon]'
                            '(https://cloud.blender.org/services#blender-addon).')
HOME_PROJECT_SUMMARY = 'This is your home project. Here you can sync your Blender settings!'
# HOME_PROJECT_DESCRIPTION = ('# Your home project\n\n'
#                             'This is your home project. It has functionality to act '
#                             'as a pastebin for text, images and other assets, and '
#                             'allows synchronisation of your Blender settings.')
# HOME_PROJECT_SUMMARY = 'This is your home project. Pastebin and Blender settings sync in one!'
SYNC_GROUP_NODE_NAME = u'Blender Sync'
SYNC_GROUP_NODE_DESC = ('The [Blender Cloud Addon](https://cloud.blender.org/services'
                        '#blender-addon) will synchronize your Blender settings here.')


def create_blender_sync_node(project_id, admin_group_id, user_id):
    """Creates a node for Blender Sync, with explicit write access for the admin group.

    Writes the node to the database.

    :param project_id: ID of the home project
    :type project_id: ObjectId
    :param admin_group_id: ID of the admin group of the project. This group will
        receive write access to the node.
    :type admin_group_id: ObjectId
    :param user_id: ID of the owner of the node.
    :type user_id: ObjectId

    :returns: The created node.
    :rtype: dict
    """

    log.debug('Creating sync node for project %s, user %s', project_id, user_id)

    node = {
        'project': ObjectId(project_id),
        'node_type': 'group',
        'name': SYNC_GROUP_NODE_NAME,
        'user': ObjectId(user_id),
        'description': SYNC_GROUP_NODE_DESC,
        'properties': {'status': 'published'},
        'permissions': {
            'users': [],
            'groups': [
                {'group': ObjectId(admin_group_id),
                 'methods': ['GET', 'PUT', 'POST', 'DELETE']}
            ],
            'world': [],
        }
    }

    r, _, _, status = post_internal('nodes', node)
    if status != 201:
        log.warning('Unable to create Blender Sync node for home project %s: %s',
                    project_id, r)
        raise wz_exceptions.InternalServerError('Unable to create Blender Sync node')

    node.update(r)
    return node


def create_home_project(user_id, write_access):
    """Creates a home project for the given user.

    :param user_id: the user ID of the owner
    :param write_access: whether the user has full write access to the home project.
    :type write_access: bool
    :returns: the project
    :rtype: dict
    """

    log.info('Creating home project for user %s', user_id)
    overrides = {
        'category': 'home',
        'url': 'home',
        'summary': HOME_PROJECT_SUMMARY,
        'description': HOME_PROJECT_DESCRIPTION
    }

    # Maybe the user has a deleted home project.
    proj_coll = current_app.data.driver.db['projects']
    deleted_proj = proj_coll.find_one({'user': user_id, 'category': 'home', '_deleted': True})
    if deleted_proj:
        log.info('User %s has a deleted project %s, restoring', user_id, deleted_proj['_id'])
        project = deleted_proj
    else:
        log.debug('User %s does not have a deleted project', user_id)
        project = projects.create_new_project(project_name='Home',
                                              user_id=ObjectId(user_id),
                                              overrides=overrides)

    # Re-validate the authentication token, so that the put_internal call sees the
    # new group created for the project.
    authentication.validate_token()

    # There are a few things in the on_insert_projects hook we need to adjust.

    # Ensure that the project is private, even for admins.
    project['permissions']['world'] = []

    # Set up the correct node types. No need to set permissions for them,
    # as the inherited project permissions are fine.
    from manage_extra.node_types.group import node_type_group
    from manage_extra.node_types.asset import node_type_asset
    # from manage_extra.node_types.text import node_type_text
    from manage_extra.node_types.comment import node_type_comment

    # For non-subscribers: take away write access from the admin group,
    # and grant it to certain node types.
    project['permissions']['groups'][0]['methods'] = home_project_permissions(write_access)

    project['node_types'] = [
        node_type_group,
        node_type_asset,
        # node_type_text,
        node_type_comment,
    ]

    result, _, _, status = put_internal('projects', utils.remove_private_keys(project),
                                        _id=project['_id'])
    if status != 200:
        log.error('Unable to update home project %s for user %s: %s',
                  project['_id'], user_id, result)
        raise wz_exceptions.InternalServerError('Unable to update home project')
    project.update(result)

    # Create the Blender Sync node, with explicit write permissions on the node itself.
    create_blender_sync_node(project['_id'],
                             project['permissions']['groups'][0]['group'],
                             user_id)

    return project


@blueprint.route('/home-project')
@authorization.require_login()
def home_project():
    """Fetches the home project, creating it if necessary.

    Eve projections are supported, but at least the following fields must be present:
        'permissions', 'category', 'user'
    """
    user_id = g.current_user['user_id']
    roles = g.current_user.get('roles', ())

    log.debug('Possibly creating home project for user %s with roles %s', user_id, roles)
    if HOME_PROJECT_USERS and not HOME_PROJECT_USERS.intersection(roles):
        log.debug('User %s is not a subscriber, not creating home project.', user_id)
        return 'No home project', 404

    # Create the home project before we do the Eve query. This costs an extra round-trip
    # to the database, but makes it easier to do projections correctly.
    if not has_home_project(user_id):
        write_access = write_access_with_roles(roles)
        create_home_project(user_id, write_access)

    resp, _, _, status, _ = get('projects', category=u'home', user=user_id)
    if status != 200:
        return utils.jsonify(resp), status

    if resp['_items']:
        project = resp['_items'][0]
    else:
        log.warning('Home project for user %s not found, while we just created it! Could be '
                    'due to projections and other arguments on the query string: %s',
                    user_id, request.query_string)
        return 'No home project', 404

    return utils.jsonify(project), status


def write_access_with_roles(roles):
    """Returns whether or not one of these roles grants write access to the home project.

    :rtype: bool
    """

    write_access = bool(not HOME_PROJECT_WRITABLE_USERS or
                        HOME_PROJECT_WRITABLE_USERS.intersection(roles))
    return write_access


def home_project_permissions(write_access):
    """Returns the project permissions, given the write access of the user.

    :rtype: list
    """

    if write_access:
        return [u'GET', u'PUT', u'POST', u'DELETE']
    return [u'GET']


def has_home_project(user_id):
    """Returns True iff the user has a home project."""

    proj_coll = current_app.data.driver.db['projects']
    return proj_coll.count({'user': user_id, 'category': 'home', '_deleted': False}) > 0


def get_home_project(user_id, projection=None):
    """Returns the home project"""

    proj_coll = current_app.data.driver.db['projects']
    return proj_coll.find_one({'user': user_id, 'category': 'home', '_deleted': False},
                              projection=projection)


def is_home_project(project_id, user_id):
    """Returns True iff the given project exists and is the user's home project."""

    proj_coll = current_app.data.driver.db['projects']
    return proj_coll.count({'_id': project_id,
                            'user': user_id,
                            'category': 'home',
                            '_deleted': False}) > 0


def mark_node_updated(node_id):
    """Uses pymongo to set the node's _updated to "now"."""

    now = datetime.datetime.now(tz=tz_util.utc)
    nodes_coll = current_app.data.driver.db['nodes']

    return nodes_coll.update_one({'_id': node_id},
                                 {'$set': {'_updated': now}})


def get_home_project_parent_node(node, projection, name_for_log):
    """Returns a partial parent node document, but only if the node is a home project node."""

    user_id = authentication.current_user_id()
    if not user_id:
        log.debug('%s: user not logged in.', name_for_log)
        return None

    parent_id = node.get('parent')
    if not parent_id:
        log.debug('%s: ignoring top-level node.', name_for_log)
        return None

    project_id = node.get('project')
    if not project_id:
        log.debug('%s: ignoring node without project ID', name_for_log)
        return None

    project_id = ObjectId(project_id)
    if not is_home_project(project_id, user_id):
        log.debug('%s: node not part of home project.', name_for_log)
        return None

    # Get the parent node for permission checking.
    parent_id = ObjectId(parent_id)

    nodes_coll = current_app.data.driver.db['nodes']
    projection['project'] = 1
    parent_node = nodes_coll.find_one(parent_id, projection=projection)

    if parent_node['project'] != project_id:
        log.warning('%s: User %s is trying to reference '
                    'parent node %s from different project %s, expected project %s.',
                    name_for_log, user_id, parent_id, parent_node['project'], project_id)
        raise wz_exceptions.BadRequest('Trying to create cross-project links.')

    return parent_node


def check_home_project_nodes_permissions(nodes):
    for node in nodes:
        check_home_project_node_permissions(node)


def check_home_project_node_permissions(node):
    """Grants POST access to the node when the user has POST access on its parent."""

    parent_node = get_home_project_parent_node(node,
                                               {'permissions': 1,
                                                'project': 1,
                                                'node_type': 1},
                                               'check_home_project_node_permissions')
    if parent_node is None or 'permissions' not in parent_node:
        return

    parent_id = parent_node['_id']

    has_access = authorization.has_permissions('nodes', parent_node, 'POST')
    if not has_access:
        log.debug('check_home_project_node_permissions: No POST access to parent node %s, '
                  'ignoring.', parent_id)
        return

    # Grant access!
    log.debug('check_home_project_node_permissions: POST access at parent node %s, '
              'so granting POST access to new child node.', parent_id)

    # Make sure the permissions of the parent node are copied to this node.
    node['permissions'] = copy.deepcopy(parent_node['permissions'])


def mark_parents_as_updated(nodes):
    for node in nodes:
        mark_parent_as_updated(node)


def mark_parent_as_updated(node, original=None):
    parent_node = get_home_project_parent_node(node,
                                               {'permissions': 1,
                                                'node_type': 1},
                                               'mark_parent_as_updated')
    if parent_node is None:
        return

    # Mark the parent node as 'updated' if this is an asset and the parent is a group.
    if node.get('node_type') == 'asset' and parent_node['node_type'] == 'group':
        log.debug('Node %s updated, marking parent=%s as updated too',
                  node['_id'], parent_node['_id'])
        mark_node_updated(parent_node['_id'])


def user_changed_role(sender, user):
    """Responds to the 'user changed' signal from the Badger service.

    Changes the permissions on the home project based on the 'subscriber' role.

    :returns: whether this function actually made changes.
    :rtype: bool
    """

    user_id = user['_id']
    if not has_home_project(user_id):
        log.debug('User %s does not have a home project', user_id)
        return

    proj_coll = current_app.data.driver.db['projects']
    proj = get_home_project(user_id, projection={'permissions': 1, '_id': 1})

    write_access = write_access_with_roles(user['roles'])
    target_permissions = home_project_permissions(write_access)

    current_perms = proj['permissions']['groups'][0]['methods']
    if set(current_perms) == set(target_permissions):
        return False

    project_id = proj['_id']
    log.info('Updating permissions on user %s home project %s from %s to %s',
             user_id, project_id, current_perms, target_permissions)
    proj_coll.update_one({'_id': project_id},
                         {'$set': {'permissions.groups.0.methods': list(target_permissions)}})

    return True


def setup_app(app, url_prefix):
    app.register_blueprint(blueprint, url_prefix=url_prefix)

    app.on_insert_nodes += check_home_project_nodes_permissions
    app.on_inserted_nodes += mark_parents_as_updated
    app.on_updated_nodes += mark_parent_as_updated
    app.on_replaced_nodes += mark_parent_as_updated

    from application.modules import service
    service.signal_user_changed_role.connect(user_changed_role)

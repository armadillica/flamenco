import copy
import logging
import json

from bson import ObjectId
from eve.methods.post import post_internal
from eve.methods.patch import patch_internal
from flask import g, Blueprint, request, abort, current_app
from werkzeug import exceptions as wz_exceptions

from application.utils import remove_private_keys, authorization, jsonify, mongo
from application.utils.gcs import GoogleCloudStorageBucket
from application.utils.authorization import user_has_role, check_permissions, require_login
from manage_extra.node_types.asset import node_type_asset
from manage_extra.node_types.comment import node_type_comment
from manage_extra.node_types.group import node_type_group
from manage_extra.node_types.texture import node_type_texture
from manage_extra.node_types.group_texture import node_type_group_texture

log = logging.getLogger(__name__)
blueprint = Blueprint('projects', __name__)


def before_inserting_projects(items):
    """Strip unwanted properties, that will be assigned after creation. Also,
    verify permission to create a project (check quota, check role).

    :param items: List of project docs that have been inserted (normally one)
    """

    # Allow admin users to do whatever they want.
    if user_has_role(u'admin'):
        return

    for item in items:
        item.pop('url', None)


def override_is_private_field(project, original):
    """Override the 'is_private' property from the world permissions.

    :param project: the project, which will be updated
    """

    # No permissions, no access.
    if 'permissions' not in project:
        project['is_private'] = True
        return

    world_perms = project['permissions'].get('world', [])
    is_private = 'GET' not in world_perms
    project['is_private'] = is_private


def before_inserting_override_is_private_field(projects):
    for project in projects:
        override_is_private_field(project, None)


def before_edit_check_permissions(document, original):
    # Allow admin users to do whatever they want.
    # TODO: possibly move this into the check_permissions function.
    if user_has_role(u'admin'):
        return

    check_permissions('projects', original, request.method)


def before_delete_project(document):
    """Checks permissions before we allow deletion"""

    # Allow admin users to do whatever they want.
    # TODO: possibly move this into the check_permissions function.
    if user_has_role(u'admin'):
        return

    check_permissions('projects', document, request.method)


def protect_sensitive_fields(document, original):
    """When not logged in as admin, prevents update to certain fields."""

    # Allow admin users to do whatever they want.
    if user_has_role(u'admin'):
        return

    def revert(name):
        if name not in original:
            try:
                del document[name]
            except KeyError:
                pass
            return
        document[name] = original[name]

    revert('url')
    revert('status')
    revert('category')
    revert('user')


def after_inserting_projects(items):
    """After inserting a project in the collection we do some processing such as:
    - apply the right permissions
    - define basic node types
    - optionally generate a url
    - initialize storage space

    :param items: List of project docs that have been inserted (normally one)
    """
    current_user = g.current_user
    users_collection = current_app.data.driver.db['users']
    user = users_collection.find_one(current_user['user_id'])

    for item in items:
        after_inserting_project(item, user)


def after_inserting_project(project, db_user):
    project_id = project['_id']
    user_id = db_user['_id']

    # Create a project-specific admin group (with name matching the project id)
    result, _, _, status = post_internal('groups', {'name': str(project_id)})
    if status != 201:
        log.error('Unable to create admin group for new project %s: %s',
                  project_id, result)
        return abort_with_error(status)

    admin_group_id = result['_id']
    log.debug('Created admin group %s for project %s', admin_group_id, project_id)

    # Assign the current user to the group
    db_user.setdefault('groups', []).append(admin_group_id)

    result, _, _, status = patch_internal('users', {'groups': db_user['groups']}, _id=user_id)
    if status != 200:
        log.error('Unable to add user %s as member of admin group %s for new project %s: %s',
                  user_id, admin_group_id, project_id, result)
        return abort_with_error(status)
    log.debug('Made user %s member of group %s', user_id, admin_group_id)

    # Assign the group to the project with admin rights
    is_admin = authorization.is_admin(db_user)
    world_permissions = ['GET'] if is_admin else []
    permissions = {
        'world': world_permissions,
        'users': [],
        'groups': [
            {'group': admin_group_id,
             'methods': ['GET', 'PUT', 'POST', 'DELETE']},
        ]
    }

    def with_permissions(node_type):
        copied = copy.deepcopy(node_type)
        copied['permissions'] = permissions
        return copied

    # Assign permissions to the project itself, as well as to the node_types
    project['permissions'] = permissions
    project['node_types'] = [
        with_permissions(node_type_group),
        with_permissions(node_type_asset),
        with_permissions(node_type_comment),
        with_permissions(node_type_texture),
        with_permissions(node_type_group_texture),
    ]

    # Allow admin users to use whatever url they want.
    if not is_admin or not project.get('url'):
        project['url'] = "p-{!s}".format(project_id)

    # Initialize storage page (defaults to GCS)
    if current_app.config.get('TESTING'):
        log.warning('Not creating Google Cloud Storage bucket while running unit tests!')
    else:
        gcs_storage = GoogleCloudStorageBucket(str(project_id))
        if gcs_storage.bucket.exists():
            log.info('Created CGS instance for project %s', project_id)
        else:
            log.warning('Unable to create CGS instance for project %s', project_id)

    # Commit the changes directly to the MongoDB; a PUT is not allowed yet,
    # as the project doesn't have a valid permission structure.
    projects_collection = current_app.data.driver.db['projects']
    result = projects_collection.update_one({'_id': project_id},
                                            {'$set': remove_private_keys(project)})
    if result.matched_count != 1:
        log.warning('Unable to update project %s: %s', project_id, result.raw_result)
        abort_with_error(500)


def _create_new_project(project_name, user_id, overrides):
    """Creates a new project owned by the given user."""

    log.info('Creating new project "%s" for user %s', project_name, user_id)

    # Create the project itself, the rest will be done by the after-insert hook.
    project = {'description': '',
               'name': project_name,
               'node_types': [],
               'status': 'published',
               'user': user_id,
               'is_private': True,
               'permissions': {},
               'url': '',
               'summary': '',
               'category': 'assets',  # TODO: allow the user to choose this.
               }
    if overrides is not None:
        project.update(overrides)

    result, _, _, status = post_internal('projects', project)
    if status != 201:
        log.error('Unable to create project "%s": %s', project_name, result)
        return abort_with_error(status)
    project.update(result)

    # Now re-fetch the project, as both the initial document and the returned
    # result do not contain the same etag as the database. This also updates
    # other fields set by hooks.
    document = current_app.data.driver.db['projects'].find_one(project['_id'])
    project.update(document)

    log.info('Created project %s for user %s', project['_id'], user_id)

    return project


@blueprint.route('/create', methods=['POST'])
@authorization.require_login(require_roles={u'admin', u'subscriber', u'demo'})
def create_project(overrides=None):
    """Creates a new project."""

    if request.mimetype == 'application/json':
        project_name = request.json['name']
    else:
        project_name = request.form['project_name']
    user_id = g.current_user['user_id']

    project = _create_new_project(project_name, user_id, overrides)

    # Return the project in the response.
    return jsonify(project, status=201, headers={'Location': '/projects/%s' % project['_id']})


@blueprint.route('/users', methods=['GET', 'POST'])
@authorization.require_login()
def project_manage_users():
    """Manage users of a project. In this initial implementation, we handle
    addition and removal of a user to the admin group of a project.
    No changes are done on the project itself.
    """

    projects_collection = current_app.data.driver.db['projects']
    users_collection = current_app.data.driver.db['users']

    # TODO: check if user is admin of the project before anything
    if request.method == 'GET':
        project_id = request.args['project_id']
        project = projects_collection.find_one({'_id': ObjectId(project_id)})
        admin_group_id = project['permissions']['groups'][0]['group']

        users = users_collection.find(
            {'groups': {'$in': [admin_group_id]}},
            {'username': 1, 'email': 1, 'full_name': 1})
        return jsonify({'_status': 'OK', '_items': list(users)})

    # The request is not a form, since it comes from the API sdk
    data = json.loads(request.data)
    project_id = ObjectId(data['project_id'])
    target_user_id = ObjectId(data['user_id'])
    action = data['action']
    current_user_id = g.current_user['user_id']

    project = projects_collection.find_one({'_id': project_id})

    # Check if the current_user is owner of the project, or removing themselves.
    remove_self = target_user_id == current_user_id and action == 'remove'
    if project['user'] != current_user_id and not remove_self:
        return abort_with_error(403)

    admin_group = get_admin_group(project)

    # Get the user and add the admin group to it
    if action == 'add':
        operation = '$addToSet'
        log.info('project_manage_users: Adding user %s to admin group of project %s',
                 target_user_id, project_id)
    elif action == 'remove':
        log.info('project_manage_users: Removing user %s from admin group of project %s',
                 target_user_id, project_id)
        operation = '$pull'
    else:
        log.warning('project_manage_users: Unsupported action %r called by user %s',
                    action, current_user_id)
        raise wz_exceptions.UnprocessableEntity()

    users_collection.update({'_id': target_user_id},
                            {operation: {'groups': admin_group['_id']}})

    user = users_collection.find_one({'_id': target_user_id},
                                     {'username': 1, 'email': 1,
                                      'full_name': 1})
    user['_status'] = 'OK'
    return jsonify(user)


def get_admin_group(project):
    """Returns the admin group for the project."""

    groups_collection = current_app.data.driver.db['groups']

    # TODO: search through all groups to find the one with the project ID as its name.
    admin_group_id = ObjectId(project['permissions']['groups'][0]['group'])
    group = groups_collection.find_one({'_id': admin_group_id})

    if group is None:
        raise ValueError('Unable to handle project without admin group.')

    if group['name'] != str(project['_id']):
        return abort_with_error(403)

    return group


def abort_with_error(status):
    """Aborts with the given status, or 500 if the status doesn't indicate an error.

    If the status is < 400, status 500 is used instead.
    """

    abort(status if status // 100 >= 4 else 500)


@blueprint.route('/<string:project_id>/quotas')
@require_login()
def project_quotas(project_id):
    """Returns information about the project's limits."""

    # Check that the user has GET permissions on the project itself.
    project = mongo.find_one_or_404('projects', project_id)
    check_permissions('projects', project, 'GET')

    file_size_used = project_total_file_size(project_id)

    info = {
        'file_size_quota': None,  # TODO: implement this later.
        'file_size_used': file_size_used,
    }

    return jsonify(info)


def project_total_file_size(project_id):
    """Returns the total number of bytes used by files of this project."""

    files = current_app.data.driver.db['files']
    file_size_used = files.aggregate([
        {'$match': {'project': ObjectId(project_id)}},
        {'$project': {'length_aggregate_in_bytes': 1}},
        {'$group': {'_id': None,
                    'all_files': {'$sum': '$length_aggregate_in_bytes'}}}
    ])

    # The aggregate function returns a cursor, not a document.
    try:
        return next(file_size_used)['all_files']
    except StopIteration:
        # No files used at all.
        return 0


def before_returning_project_permissions(response):
    # Run validation process, since GET on nodes entry point is public
    check_permissions('projects', response, 'GET', append_allowed_methods=True)


def before_returning_project_resource_permissions(response):
    # Return only those projects the user has access to.
    allow = [project for project in response['_items']
             if authorization.has_permissions('projects', project,
                                              'GET', append_allowed_methods=True)]
    response['_items'] = allow


def project_node_type_has_method(response):
    """Check for a specific request arg, and check generate the allowed_methods
    list for the required node_type.
    """

    node_type_name = request.args.get('node_type', '')

    # Proceed only node_type has been requested
    if not node_type_name:
        return

    # Look up the node type in the project document
    if not any(node_type.get('name') == node_type_name
               for node_type in response['node_types']):
        return abort(404)

    # Check permissions and append the allowed_methods to the node_type
    check_permissions('projects', response, 'GET', append_allowed_methods=True,
                      check_node_type=node_type_name)


def projects_node_type_has_method(response):
    for project in response['_items']:
        project_node_type_has_method(project)


def setup_app(app, url_prefix):
    app.on_replace_projects += override_is_private_field
    app.on_replace_projects += before_edit_check_permissions
    app.on_replace_projects += protect_sensitive_fields
    app.on_update_projects += override_is_private_field
    app.on_update_projects += before_edit_check_permissions
    app.on_update_projects += protect_sensitive_fields
    app.on_delete_item_projects += before_delete_project
    app.on_insert_projects += before_inserting_override_is_private_field
    app.on_insert_projects += before_inserting_projects
    app.on_inserted_projects += after_inserting_projects

    app.on_fetched_item_projects += before_returning_project_permissions
    app.on_fetched_resource_projects += before_returning_project_resource_permissions
    app.on_fetched_item_projects += project_node_type_has_method
    app.on_fetched_resource_projects += projects_node_type_has_method

    app.register_blueprint(blueprint, url_prefix=url_prefix)

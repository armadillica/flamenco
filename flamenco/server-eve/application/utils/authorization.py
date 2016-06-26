import logging
import functools

from bson import ObjectId
from flask import g
from flask import abort
from flask import current_app
from werkzeug.exceptions import Forbidden

CHECK_PERMISSIONS_IMPLEMENTED_FOR = {'projects', 'nodes'}

log = logging.getLogger(__name__)


def check_permissions(collection_name, resource, method, append_allowed_methods=False,
                      check_node_type=None):
    """Check user permissions to access a node. We look up node permissions from
    world to groups to users and match them with the computed user permissions.
    If there is not match, we raise 403.

    :param collection_name: name of the collection the resource comes from.
    :param resource: resource from MongoDB
    :type resource: dict
    :param method: name of the requested HTTP method
    :param append_allowed_methods: whether to return the list of allowed methods
        in the resource. Only valid when method='GET'.
    :param check_node_type: node type to check. Only valid when collection_name='projects'.
    :type check_node_type: str
    """

    if not has_permissions(collection_name, resource, method, append_allowed_methods,
                           check_node_type):
        abort(403)


def has_permissions(collection_name, resource, method, append_allowed_methods=False,
                      check_node_type=None):
    """Check user permissions to access a node. We look up node permissions from
    world to groups to users and match them with the computed user permissions.

    :param collection_name: name of the collection the resource comes from.
    :param resource: resource from MongoDB
    :type resource: dict
    :param method: name of the requested HTTP method
    :param append_allowed_methods: whether to return the list of allowed methods
        in the resource. Only valid when method='GET'.
    :param check_node_type: node type to check. Only valid when collection_name='projects'.
    :type check_node_type: str
    :returns: True if the user has access, False otherwise.
    :rtype: bool
    """

    # Check some input values.
    if collection_name not in CHECK_PERMISSIONS_IMPLEMENTED_FOR:
        raise ValueError('check_permission only implemented for %s, not for %s',
                         CHECK_PERMISSIONS_IMPLEMENTED_FOR, collection_name)

    if append_allowed_methods and method != 'GET':
        raise ValueError("append_allowed_methods only allowed with 'GET' method")

    if check_node_type is not None and collection_name != 'projects':
        raise ValueError('check_node_type parameter is only valid for checking projects.')

    computed_permissions = compute_aggr_permissions(collection_name, resource, check_node_type)

    if not computed_permissions:
        log.info('No permissions available to compute for %s on resource %r',
                 method, resource.get('node_type', resource))
        return False

    # Accumulate allowed methods from the user, group and world level.
    allowed_methods = set()

    current_user = g.current_user
    if current_user:
        # If the user is authenticated, proceed to compare the group permissions
        for permission in computed_permissions.get('groups', ()):
            if permission['group'] in current_user['groups']:
                allowed_methods.update(permission['methods'])

        for permission in computed_permissions.get('users', ()):
            if current_user['user_id'] == permission['user']:
                allowed_methods.update(permission['methods'])

    # Check if the node is public or private. This must be set for non logged
    # in users to see the content. For most BI projects this is on by default,
    # while for private project this will not be set at all.
    if 'world' in computed_permissions:
        allowed_methods.update(computed_permissions['world'])

    permission_granted = method in allowed_methods
    if permission_granted:
        if append_allowed_methods:
            # TODO: rename this field _allowed_methods
            if check_node_type:
                node_type = next((node_type for node_type in resource['node_types']
                                  if node_type['name'] == check_node_type))
                assign_to = node_type
            else:
                assign_to = resource
            assign_to['allowed_methods'] = list(set(allowed_methods))
        return True

    return False


def compute_aggr_permissions(collection_name, resource, check_node_type):
    """Returns a permissions dict."""

    # We always need the know the project.
    if collection_name == 'projects':
        project = resource
        if check_node_type is None:
            return project['permissions']
        node_type_name = check_node_type
    else:
        # Not a project, so it's a node.
        assert 'project' in resource
        assert 'node_type' in resource

        node_type_name = resource['node_type']

        if isinstance(resource['project'], dict):
            # embedded project
            project = resource['project']
        else:
            project_id = resource['project']
            project = _find_project_node_type(project_id, node_type_name)

    # Every node should have a project.
    if project is None:
        log.warning('Resource %s from "%s" refers to a project that does not exist.',
                    resource['_id'], collection_name)
        raise Forbidden()

    project_permissions = project['permissions']

    # Find the node type from the project.
    node_type = next((node_type for node_type in project['node_types']
                      if node_type['name'] == node_type_name), None)
    if node_type is None:  # This node type is not known, so doesn't give permissions.
        node_type_permissions = {}
    else:
        node_type_permissions = node_type.get('permissions', {})

    # For projects or specific node types in projects, we're done now.
    if collection_name == 'projects':
        return merge_permissions(project_permissions, node_type_permissions)

    node_permissions = resource.get('permissions', {})
    return merge_permissions(project_permissions, node_type_permissions, node_permissions)


def _find_project_node_type(project_id, node_type_name):
    """Returns the project with just the one named node type."""

    # Cache result per request, as many nodes of the same project can be checked.
    cache = g.get('_find_project_node_type_cache')
    if cache is None:
        cache = g._find_project_node_type_cache = {}

    try:
        return cache[(project_id, node_type_name)]
    except KeyError:
        pass

    projects_collection = current_app.data.driver.db['projects']
    project = projects_collection.find_one(
        ObjectId(project_id),
        {'permissions': 1,
         'node_types': {'$elemMatch': {'name': node_type_name}},
         'node_types.name': 1,
         'node_types.permissions': 1})

    cache[(project_id, node_type_name)] = project

    return project


def merge_permissions(*args):
    """Merges all given permissions.

    :param args: list of {'user': ..., 'group': ..., 'world': ...} dicts.
    :returns: combined list of permissions.
    """

    if not args:
        return {}

    if len(args) == 1:
        return args[0]

    effective = {}

    # When testing we want stable results, and not be dependent on PYTHONHASH values etc.
    if current_app.config['TESTING']:
        maybe_sorted = sorted
    else:
        def maybe_sorted(arg):
            return arg

    def merge(field_name):
        plural_name = field_name + 's'

        from0 = args[0].get(plural_name, [])
        from1 = args[1].get(plural_name, [])

        asdict0 = {permission[field_name]: permission['methods'] for permission in from0}
        asdict1 = {permission[field_name]: permission['methods'] for permission in from1}

        keys = set(asdict0.keys() + asdict1.keys())
        for key in maybe_sorted(keys):
            methods0 = asdict0.get(key, [])
            methods1 = asdict1.get(key, [])
            methods = maybe_sorted(set(methods0).union(set(methods1)))
            effective.setdefault(plural_name, []).append({field_name: key, u'methods': methods})

    merge(u'user')
    merge(u'group')

    # Gather permissions for world
    world0 = args[0].get('world', [])
    world1 = args[1].get('world', [])
    world_methods = set(world0).union(set(world1))
    if world_methods:
        effective[u'world'] = maybe_sorted(world_methods)

    # Recurse for longer merges
    if len(args) > 2:
        return merge_permissions(effective, *args[2:])

    return effective


def require_login(require_roles=set(),
                  require_all=False):
    """Decorator that enforces users to authenticate.

    Optionally only allows access to users with a certain role.

    :param require_roles: set of roles.
    :param require_all:
        When False (the default): if the user's roles have a
        non-empty intersection with the given roles, access is granted.
        When True: require the user to have all given roles before access is
        granted.
    """

    if not isinstance(require_roles, set):
        raise TypeError('require_roles param should be a set, but is a %r' % type(require_roles))

    if require_all and not require_roles:
        raise ValueError('require_login(require_all=True) cannot be used with empty require_roles.')

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_user = g.get('current_user')

            if current_user is None:
                # We don't need to log at a higher level, as this is very common.
                # Many browsers first try to see whether authentication is needed
                # at all, before sending the password.
                log.debug('Unauthenticated acces to %s attempted.', func)
                abort(403)

            intersection = require_roles.intersection(set(current_user['roles']))
            if require_all:
                if intersection != require_roles:
                    log.warning('User %s does not have ALL required roles %s to access %s',
                                current_user['user_id'], require_roles, func)
                    abort(403)
            elif require_roles and not intersection:
                log.warning('User %s is authenticated, but does not have any required role %s to '
                            'access %s', current_user['user_id'], require_roles, func)
                abort(403)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def user_has_role(role, user=None):
    """Returns True iff the user is logged in and has the given role."""

    if user is None:
        user = g.get('current_user')

    if user is None:
        return False

    return role in user['roles']


def is_admin(user):
    """Returns True iff the given user has the admin role."""

    return user_has_role(u'admin', user)

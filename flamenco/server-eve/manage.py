#!/usr/bin/env python

from __future__ import print_function
from __future__ import division

import copy
import os
import logging

from bson.objectid import ObjectId
from eve.methods.put import put_internal
from eve.methods.post import post_internal
from flask.ext.script import Manager

# Use a sensible default when running manage.py commands.
if not os.environ.get('EVE_SETTINGS'):
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 'settings.py')
    os.environ['EVE_SETTINGS'] = settings_path

from application import app
from application.utils.gcs import GoogleCloudStorageBucket
from manage_extra.node_types.asset import node_type_asset
from manage_extra.node_types.blog import node_type_blog
from manage_extra.node_types.comment import node_type_comment
from manage_extra.node_types.group import node_type_group
from manage_extra.node_types.post import node_type_post
from manage_extra.node_types.project import node_type_project
from manage_extra.node_types.storage import node_type_storage
from manage_extra.node_types.texture import node_type_texture
from manage_extra.node_types.group_texture import node_type_group_texture

manager = Manager(app)

log = logging.getLogger('manage')
log.setLevel(logging.INFO)

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')


@manager.command
def runserver(**options):
    # Automatic creation of STORAGE_DIR path if it's missing
    if not os.path.exists(app.config['STORAGE_DIR']):
        os.makedirs(app.config['STORAGE_DIR'])

    app.run(host=app.config['HOST'],
            port=app.config['PORT'],
            debug=app.config['DEBUG'],
            **options)


@manager.command
def runserver_memlimit(limit_kb=1000000):
    import resource

    limit_b = int(limit_kb) * 1024
    for rsrc in (resource.RLIMIT_AS, resource.RLIMIT_DATA, resource.RLIMIT_RSS):
        resource.setrlimit(rsrc, (limit_b, limit_b))

    runserver()


@manager.command
def runserver_profile(pfile='profile.stats'):
    import cProfile

    cProfile.run('runserver(use_reloader=False)', pfile)


def each_project_node_type(node_type_name=None):
    """Generator, yields (project, node_type) tuples for all projects and node types.

    When a node type name is given, only yields those node types.
    """

    projects_coll = app.data.driver.db['projects']

    for project in projects_coll.find():
        for node_type in project['node_types']:
            if node_type_name is None or node_type['name'] == node_type_name:
                yield project, node_type


def post_item(entry, data):
    return post_internal(entry, data)


def put_item(collection, item):
    item_id = item['_id']
    internal_fields = ['_id', '_etag', '_updated', '_created']
    for field in internal_fields:
        item.pop(field, None)
    # print item
    # print type(item_id)
    p = put_internal(collection, item, **{'_id': item_id})
    if p[0]['_status'] == 'ERR':
        print(p)
        print(item)


@manager.command
def setup_db(admin_email):
    """Setup the database
    - Create admin, subscriber and demo Group collection
    - Create admin user (must use valid blender-id credentials)
    - Create one project
    """

    # Create default groups
    groups_list = []
    for group in ['admin', 'subscriber', 'demo']:
        g = {'name': group}
        g = post_internal('groups', g)
        groups_list.append(g[0]['_id'])
        print("Creating group {0}".format(group))

    # Create admin user
    user = {'username': admin_email,
            'groups': groups_list,
            'roles': ['admin', 'subscriber', 'demo'],
            'settings': {'email_communications': 1},
            'auth': [],
            'full_name': admin_email,
            'email': admin_email}
    result, _, _, status = post_internal('users', user)
    if status != 201:
        raise SystemExit('Error creating user {}: {}'.format(admin_email, result))
    user.update(result)
    print("Created user {0}".format(user['_id']))

    # Create a default project by faking a POST request.
    with app.test_request_context(data={'project_name': u'Default Project'}):
        from flask import g
        from application.modules import projects

        g.current_user = {'user_id': user['_id'],
                          'groups': user['groups'],
                          'roles': set(user['roles'])}

        projects.create_project(overrides={'url': 'default-project',
                                           'is_private': False})


def _default_permissions():
    """Returns a dict of default permissions.

    Usable for projects, node types, and others.

    :rtype: dict
    """

    groups_collection = app.data.driver.db['groups']
    admin_group = groups_collection.find_one({'name': 'admin'})

    default_permissions = {
        'world': ['GET'],
        'users': [],
        'groups': [
            {'group': admin_group['_id'],
             'methods': ['GET', 'PUT', 'POST']},
        ]
    }

    return default_permissions


@manager.command
def setup_for_attract(project_uuid, replace=False):
    """Adds Attract node types to the project.

    :param project_uuid: the UUID of the project to update
    :type project_uuid: str
    :param replace: whether to replace existing Attract node types (True),
        or to keep existing node types (False, the default).
    :type replace: bool
    """

    from manage_extra.node_types.act import node_type_act
    from manage_extra.node_types.scene import node_type_scene
    from manage_extra.node_types.shot import node_type_shot

    # Copy permissions from the project, then give everyone with PUT
    # access also DELETE access.
    project = _get_project(project_uuid)
    permissions = copy.deepcopy(project['permissions'])

    for perms in permissions.values():
        for perm in perms:
            methods = set(perm['methods'])
            if 'PUT' not in perm['methods']:
                continue
            methods.add('DELETE')
            perm['methods'] = list(methods)

    node_type_act['permissions'] = permissions
    node_type_scene['permissions'] = permissions
    node_type_shot['permissions'] = permissions

    # Add the missing node types.
    for node_type in (node_type_act, node_type_scene, node_type_shot):
        found = [nt for nt in project['node_types']
                 if nt['name'] == node_type['name']]
        if found:
            assert len(found) == 1, 'node type name should be unique (found %ix)' % len(found)

            # TODO: validate that the node type contains all the properties Attract needs.
            if replace:
                log.info('Replacing existing node type %s', node_type['name'])
                project['node_types'].remove(found[0])
            else:
                continue

        project['node_types'].append(node_type)

    _update_project(project_uuid, project)

    log.info('Project %s was updated for Attract.', project_uuid)


def _get_project(project_uuid):
    """Find a project in the database, or SystemExit()s.

    :param project_uuid: UUID of the project
    :type: str
    :return: the project
    :rtype: dict
    """

    projects_collection = app.data.driver.db['projects']
    project_id = ObjectId(project_uuid)

    # Find the project in the database.
    project = projects_collection.find_one(project_id)
    if not project:
        log.error('Project %s does not exist.', project_uuid)
        raise SystemExit()

    return project


def _update_project(project_uuid, project):
    """Updates a project in the database, or SystemExit()s.

    :param project_uuid: UUID of the project
    :type: str
    :param project: the project data, should be the entire project document
    :type: dict
    :return: the project
    :rtype: dict
    """

    from application.utils import remove_private_keys

    project_id = ObjectId(project_uuid)
    project = remove_private_keys(project)
    result, _, _, _ = put_internal('projects', project, _id=project_id)

    if result['_status'] != 'OK':
        log.error("Can't update project %s, issues: %s", project_uuid, result['_issues'])
        raise SystemExit()


@manager.command
def clear_db():
    """Wipes the database
    """
    from pymongo import MongoClient

    client = MongoClient(MONGO_HOST, 27017)
    db = client.eve
    db.drop_collection('nodes')
    db.drop_collection('node_types')
    db.drop_collection('tokens')
    db.drop_collection('users')


@manager.command
def add_parent_to_nodes():
    """Find the parent of any node in the nodes collection"""
    import codecs
    import sys

    UTF8Writer = codecs.getwriter('utf8')
    sys.stdout = UTF8Writer(sys.stdout)

    nodes_collection = app.data.driver.db['nodes']

    def find_parent_project(node):
        if node and 'parent' in node:
            parent = nodes_collection.find_one({'_id': node['parent']})
            return find_parent_project(parent)
        if node:
            return node
        else:
            return None

    nodes = nodes_collection.find()
    nodes_index = 0
    nodes_orphan = 0
    for node in nodes:
        nodes_index += 1
        if node['node_type'] == ObjectId("55a615cfea893bd7d0489f2d"):
            print(u"Skipping project node - {0}".format(node['name']))
        else:
            project = find_parent_project(node)
            if project:
                nodes_collection.update({'_id': node['_id']},
                                        {"$set": {'project': project['_id']}})
                print(u"{0} {1}".format(node['_id'], node['name']))
            else:
                nodes_orphan += 1
                nodes_collection.remove({'_id': node['_id']})
                print("Removed {0} {1}".format(node['_id'], node['name']))

    print("Edited {0} nodes".format(nodes_index))
    print("Orphan {0} nodes".format(nodes_orphan))


@manager.command
def make_project_public(project_id):
    """Convert every node of a project from pending to public"""

    DRY_RUN = False
    nodes_collection = app.data.driver.db['nodes']
    for n in nodes_collection.find({'project': ObjectId(project_id)}):
        n['properties']['status'] = 'published'
        print(u"Publishing {0} {1}".format(n['_id'], n['name'].encode('ascii', 'ignore')))
        if not DRY_RUN:
            put_item('nodes', n)


@manager.command
def set_attachment_names():
    """Loop through all existing nodes and assign proper ContentDisposition
    metadata to referenced files that are using GCS.
    """
    from application.utils.gcs import update_file_name
    nodes_collection = app.data.driver.db['nodes']
    for n in nodes_collection.find():
        print("Updating node {0}".format(n['_id']))
        update_file_name(n)


@manager.command
def files_verify_project():
    """Verify for missing or conflicting node/file ids"""
    nodes_collection = app.data.driver.db['nodes']
    files_collection = app.data.driver.db['files']
    issues = dict(missing=[], conflicting=[], processing=[])

    def _parse_file(item, file_id):
        f = files_collection.find_one({'_id': file_id})
        if f:
            if 'project' in item and 'project' in f:
                if item['project'] != f['project']:
                    issues['conflicting'].append(item['_id'])
                if 'status' in item['properties'] \
                        and item['properties']['status'] == 'processing':
                    issues['processing'].append(item['_id'])
        else:
            issues['missing'].append(
                "{0} missing {1}".format(item['_id'], file_id))

    for item in nodes_collection.find():
        print("Verifying node {0}".format(item['_id']))
        if 'file' in item['properties']:
            _parse_file(item, item['properties']['file'])
        elif 'files' in item['properties']:
            for f in item['properties']['files']:
                _parse_file(item, f['file'])

    print("===")
    print("Issues detected:")
    for k, v in issues.iteritems():
        print("{0}:".format(k))
        for i in v:
            print(i)
        print("===")


def replace_node_type(project, node_type_name, new_node_type):
    """Update or create the specified node type. We rely on the fact that
    node_types have a unique name in a project.
    """

    old_node_type = next(
        (item for item in project['node_types'] if item.get('name') \
         and item['name'] == node_type_name), None)
    if old_node_type:
        for i, v in enumerate(project['node_types']):
            if v['name'] == node_type_name:
                project['node_types'][i] = new_node_type
    else:
        project['node_types'].append(new_node_type)


@manager.command
def project_upgrade_node_types(project_id):
    projects_collection = app.data.driver.db['projects']
    project = projects_collection.find_one({'_id': ObjectId(project_id)})
    replace_node_type(project, 'group', node_type_group)
    replace_node_type(project, 'asset', node_type_asset)
    replace_node_type(project, 'storage', node_type_storage)
    replace_node_type(project, 'comment', node_type_comment)
    replace_node_type(project, 'blog', node_type_blog)
    replace_node_type(project, 'post', node_type_post)
    replace_node_type(project, 'texture', node_type_texture)
    put_item('projects', project)


@manager.command
def test_put_item(node_id):
    import pprint
    nodes_collection = app.data.driver.db['nodes']
    node = nodes_collection.find_one(ObjectId(node_id))
    pprint.pprint(node)
    put_item('nodes', node)


@manager.command
def test_post_internal(node_id):
    import pprint
    nodes_collection = app.data.driver.db['nodes']
    node = nodes_collection.find_one(ObjectId(node_id))
    internal_fields = ['_id', '_etag', '_updated', '_created']
    for field in internal_fields:
        node.pop(field, None)
    pprint.pprint(node)
    print(post_internal('nodes', node))


@manager.command
def algolia_push_users():
    """Loop through all users and push them to Algolia"""
    from application.utils.algolia import algolia_index_user_save
    users_collection = app.data.driver.db['users']
    for user in users_collection.find():
        print("Pushing {0}".format(user['username']))
        algolia_index_user_save(user)


@manager.command
def algolia_push_nodes():
    """Loop through all nodes and push them to Algolia"""
    from application.utils.algolia import algolia_index_node_save
    nodes_collection = app.data.driver.db['nodes']
    for node in nodes_collection.find():
        print(u"Pushing {0}: {1}".format(node['_id'], node['name'].encode(
            'ascii', 'ignore')))
        algolia_index_node_save(node)


@manager.command
def files_make_public_t():
    """Loop through all files and if they are images on GCS, make the size t
    public
    """
    from gcloud.exceptions import InternalServerError
    from application.utils.gcs import GoogleCloudStorageBucket
    files_collection = app.data.driver.db['files']

    for f in files_collection.find({'backend': 'gcs'}):
        if 'variations' not in f:
            continue

        variation_t = next((item for item in f['variations']
                            if item['size'] == 't'), None)
        if not variation_t:
            continue

        try:
            storage = GoogleCloudStorageBucket(str(f['project']))
            blob = storage.Get(variation_t['file_path'], to_dict=False)
            if not blob:
                print('Unable to find blob for project %s file %s' %(f['project'], f['_id']))
                continue

            print('Making blob public: {0}'.format(blob.path))
            blob.make_public()
        except InternalServerError as ex:
            print('Internal Server Error: ', ex)


@manager.command
def subscribe_node_owners():
    """Automatically subscribe node owners to notifications for items created
    in the past.
    """
    from application import after_inserting_nodes
    nodes_collection = app.data.driver.db['nodes']
    for n in nodes_collection.find():
        if 'parent' in n:
            after_inserting_nodes([n])


@manager.command
def refresh_project_links(project, chunk_size=50, quiet=False):
    """Regenerates almost-expired file links for a certain project."""

    if quiet:
        import logging
        from application import log

        logging.getLogger().setLevel(logging.WARNING)
        log.setLevel(logging.WARNING)

    chunk_size = int(chunk_size)  # CLI parameters are passed as strings
    from application.modules import file_storage
    file_storage.refresh_links_for_project(project, chunk_size, 2 * 3600)


@manager.command
def refresh_backend_links(backend_name, chunk_size=50, quiet=False):
    """Refreshes all file links that are using a certain storage backend."""

    if quiet:
        import logging
        from application import log

        logging.getLogger().setLevel(logging.WARNING)
        log.setLevel(logging.WARNING)

    chunk_size = int(chunk_size)  # CLI parameters are passed as strings
    from application.modules import file_storage
    file_storage.refresh_links_for_backend(backend_name, chunk_size, 2 * 3600)


@manager.command
def expire_all_project_links(project_uuid):
    """Expires all file links for a certain project without refreshing.

    This is just for testing.
    """

    import datetime
    import bson.tz_util

    files_collection = app.data.driver.db['files']

    now = datetime.datetime.now(tz=bson.tz_util.utc)
    expires = now - datetime.timedelta(days=1)

    result = files_collection.update_many(
        {'project': ObjectId(project_uuid)},
        {'$set': {'link_expires': expires}}
    )

    print('Expired %i links' % result.matched_count)


@manager.command
def register_local_user(email, password):
    from application.modules.local_auth import create_local_user
    create_local_user(email, password)


@manager.command
def add_group_to_projects(group_name):
    """Prototype to add a specific group, in read-only mode, to all node_types
    for all projects.
    """
    methods = ['GET']
    groups_collection = app.data.driver.db['groups']
    projects_collections = app.data.driver.db['projects']
    group = groups_collection.find_one({'name': group_name})
    for project in projects_collections.find():
        print("Processing: {}".format(project['name']))
        for node_type in project['node_types']:
            node_type_name = node_type['name']
            base_node_types = ['group', 'asset', 'blog', 'post', 'page',
                               'comment', 'group_texture', 'storage', 'texture']
            if node_type_name in base_node_types:
                print("Processing: {0}".format(node_type_name))
                # Check if group already exists in the permissions
                g = next((g for g in node_type['permissions']['groups']
                          if g['group'] == group['_id']), None)
                # If not, we add it
                if g is None:
                    print("Adding permissions")
                    permissions = {
                        'group': group['_id'],
                        'methods': methods}
                    node_type['permissions']['groups'].append(permissions)
                    projects_collections.update(
                        {'_id': project['_id']}, project)


@manager.command
def add_license_props():
    """Add license fields to all node types asset for every project."""
    projects_collections = app.data.driver.db['projects']
    for project in projects_collections.find():
        print("Processing {}".format(project['_id']))
        for node_type in project['node_types']:
            if node_type['name'] == 'asset':
                node_type['dyn_schema']['license_notes'] = {'type': 'string'}
                node_type['dyn_schema']['license_type'] = {
                    'type': 'string',
                    'allowed': [
                        'cc-by',
                        'cc-0',
                        'cc-by-sa',
                        'cc-by-nd',
                        'cc-by-nc',
                        'copyright'
                    ],
                    'default': 'cc-by'
                }
                node_type['form_schema']['license_notes'] = {}
                node_type['form_schema']['license_type'] = {}
        projects_collections.update(
            {'_id': project['_id']}, project)


@manager.command
def refresh_file_sizes():
    """Computes & stores the 'length_aggregate_in_bytes' fields of all files."""

    from application.modules import file_storage

    matched = 0
    unmatched = 0
    total_size = 0

    files_collection = app.data.driver.db['files']
    for file_doc in files_collection.find():
        file_storage.compute_aggregate_length(file_doc)
        length = file_doc['length_aggregate_in_bytes']
        total_size += length

        result = files_collection.update_one({'_id': file_doc['_id']},
                                             {'$set': {'length_aggregate_in_bytes': length}})
        if result.matched_count != 1:
            log.warning('Unable to update document %s', file_doc['_id'])
            unmatched += 1
        else:
            matched += 1

    log.info('Updated %i file documents.', matched)
    if unmatched:
        log.warning('Unable to update %i documents.', unmatched)
    log.info('%i bytes (%.3f GiB) storage used in total.',
             total_size, total_size / 1024 ** 3)


@manager.command
def project_stats():
    import csv
    import sys
    from collections import defaultdict
    from functools import partial

    from application.modules import projects

    proj_coll = app.data.driver.db['projects']
    nodes = app.data.driver.db['nodes']

    aggr = defaultdict(partial(defaultdict, int))

    csvout = csv.writer(sys.stdout)
    csvout.writerow(['project ID', 'owner', 'private', 'file size',
                     'nr of nodes', 'nr of top-level nodes', ])

    for proj in proj_coll.find(projection={'user': 1,
                                           'name': 1,
                                           'is_private': 1,
                                           '_id': 1}):
        project_id = proj['_id']
        is_private = proj.get('is_private', False)
        row = [str(project_id),
               unicode(proj['user']).encode('utf-8'),
               is_private]

        file_size = projects.project_total_file_size(project_id)
        row.append(file_size)

        node_count_result = nodes.aggregate([
            {'$match': {'project': project_id}},
            {'$project': {'parent': 1,
                          'is_top': {'$cond': [{'$gt': ['$parent', None]}, 0, 1]},
                          }},
            {'$group': {
                '_id': None,
                'all': {'$sum': 1},
                'top': {'$sum': '$is_top'},
            }}
        ])

        try:
            node_counts = next(node_count_result)
            nodes_all = node_counts['all']
            nodes_top = node_counts['top']
        except StopIteration:
            # No result from the nodes means nodeless project.
            nodes_all = 0
            nodes_top = 0
        row.append(nodes_all)
        row.append(nodes_top)

        for collection in aggr[None], aggr[is_private]:
            collection['project_count'] += 1
            collection['project_count'] += 1
            collection['file_size'] += file_size
            collection['node_count'] += nodes_all
            collection['top_nodes'] += nodes_top

        csvout.writerow(row)

    csvout.writerow([
        'public', '', '%i projects' % aggr[False]['project_count'],
        aggr[False]['file_size'], aggr[False]['node_count'], aggr[False]['top_nodes'],
    ])
    csvout.writerow([
        'private', '', '%i projects' % aggr[True]['project_count'],
        aggr[True]['file_size'], aggr[True]['node_count'], aggr[True]['top_nodes'],
    ])
    csvout.writerow([
        'total', '', '%i projects' % aggr[None]['project_count'],
        aggr[None]['file_size'], aggr[None]['node_count'], aggr[None]['top_nodes'],
    ])


@manager.command
def add_node_types():
    """Add texture and group_texture node types to all projects"""
    from manage_extra.node_types.texture import node_type_texture
    from manage_extra.node_types.group_texture import node_type_group_texture
    from application.utils import project_get_node_type
    projects_collections = app.data.driver.db['projects']
    for project in projects_collections.find():
        print("Processing {}".format(project['_id']))
        if not project_get_node_type(project, 'group_texture'):
            project['node_types'].append(node_type_group_texture)
            print("Added node type: {}".format(node_type_group_texture['name']))
        if not project_get_node_type(project, 'texture'):
            project['node_types'].append(node_type_texture)
            print("Added node type: {}".format(node_type_texture['name']))
        projects_collections.update(
            {'_id': project['_id']}, project)


@manager.command
def update_texture_node_type():
    """Update allowed values for textures node_types"""
    projects_collections = app.data.driver.db['projects']
    for project in projects_collections.find():
        print("Processing {}".format(project['_id']))
        for node_type in project['node_types']:
            if node_type['name'] == 'texture':
                allowed = [
                    'color',
                    'specular',
                    'bump',
                    'normal',
                    'translucency',
                    'emission',
                    'alpha'
                    ]
                node_type['dyn_schema']['files']['schema']['schema']['map_type']['allowed'] = allowed
        projects_collections.update(
            {'_id': project['_id']}, project)


@manager.command
def update_texture_nodes_maps():
    """Update abbreviated texture map types to the extended version"""
    nodes_collection = app.data.driver.db['nodes']
    remap = {
        'col': 'color',
        'spec': 'specular',
        'nor': 'normal'}
    for node in nodes_collection.find({'node_type': 'texture'}):
        for v in node['properties']['files']:
            try:
                updated_map_types = remap[v['map_type']]
                print("Updating {} to {}".format(v['map_type'], updated_map_types))
                v['map_type'] = updated_map_types
            except KeyError:
                print("Skipping {}".format(v['map_type']))
            nodes_collection.update({'_id': node['_id']}, node)


if __name__ == '__main__':
    manager.run()

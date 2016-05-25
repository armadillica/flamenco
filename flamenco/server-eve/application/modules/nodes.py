import logging

from bson import ObjectId
from flask import current_app
from werkzeug.exceptions import UnprocessableEntity

from application.modules import file_storage
from application.utils.authorization import check_permissions
from application.utils.gcs import update_file_name
from application.utils.activities import activity_subscribe, activity_object_add

log = logging.getLogger(__name__)


def item_parse_attachments(response):
    """Before returning a response, check if the 'attachments' property is
    defined. If yes, load the file (for the moment only images) in the required
    variation, get the link and build a Markdown representation. Search in the
    'field' specified in the attachment and replace the 'slug' tag with the
    generated link.
    """

    if 'properties' not in response or 'attachments' not in response['properties']:
        return

    files_collection = current_app.data.driver.db['files']
    for attachment in response['properties']['attachments']:
        # Make a list from the property path
        field_name_path = attachment['field'].split('.')
        # This currently allow to access only properties inside of
        # the properties property
        if len(field_name_path) > 1:
            field_content = response[field_name_path[0]][field_name_path[1]]
        # This is for the "normal" first level property
        else:
            field_content = response[field_name_path[0]]
        for af in attachment['files']:
            slug = af['slug']
            slug_tag = "[{0}]".format(slug)
            f = files_collection.find_one({'_id': ObjectId(af['file'])})
            if f is None:
                af['file'] = None
                continue
            size = f['size'] if 'size' in f else 'l'
            # Get the correct variation from the file
            thumbnail = next((item for item in f['variations'] if
                              item['size'] == size), None)
            l = file_storage.generate_link(f['backend'], thumbnail['file_path'],
                                           str(f['project']))
            # Build Markdown img string
            l = '![{0}]({1} "{2}")'.format(slug, l, f['name'])
            # Parse the content of the file and replace the attachment
            # tag with the actual image link
            field_content = field_content.replace(slug_tag, l)

        # Apply the parsed value back to the property. See above for
        # clarifications on how this is done.
        if len(field_name_path) > 1:
            response[field_name_path[0]][field_name_path[1]] = field_content
        else:
            response[field_name_path[0]] = field_content


def resource_parse_attachments(response):
    for item in response['_items']:
        item_parse_attachments(item)


def before_replacing_node(item, original):
    check_permissions('nodes', original, 'PUT')
    update_file_name(item)


def after_replacing_node(item, original):
    """Push an update to the Algolia index when a node item is updated. If the
    project is private, prevent public indexing.
    """

    projects_collection = current_app.data.driver.db['projects']
    project = projects_collection.find_one({'_id': item['project']})
    if project.get('is_private', False):
        # Skip index updating and return
        return

    from algoliasearch.client import AlgoliaException
    from application.utils.algolia import algolia_index_node_save

    try:
        algolia_index_node_save(item)
    except AlgoliaException as ex:
        log.warning('Unable to push node info to Algolia for node %s; %s',
                    item.get('_id'), ex)


def before_inserting_nodes(items):
    """Before inserting a node in the collection we check if the user is allowed
    and we append the project id to it.
    """
    nodes_collection = current_app.data.driver.db['nodes']

    def find_parent_project(node):
        """Recursive function that finds the ultimate parent of a node."""
        if node and 'parent' in node:
            parent = nodes_collection.find_one({'_id': node['parent']})
            return find_parent_project(parent)
        if node:
            return node
        else:
            return None

    for item in items:
        check_permissions('nodes', item, 'POST')
        if 'parent' in item and 'project' not in item:
            parent = nodes_collection.find_one({'_id': item['parent']})
            project = find_parent_project(parent)
            if project:
                item['project'] = project['_id']


def after_inserting_nodes(items):
    for item in items:
        # Skip subscriptions for first level items (since the context is not a
        # node, but a project).
        # TODO: support should be added for mixed context
        if 'parent' not in item:
            return
        context_object_id = item['parent']
        if item['node_type'] == 'comment':
            nodes_collection = current_app.data.driver.db['nodes']
            parent = nodes_collection.find_one({'_id': item['parent']})
            # Always subscribe to the parent node
            activity_subscribe(item['user'], 'node', item['parent'])
            if parent['node_type'] == 'comment':
                # If the parent is a comment, we provide its own parent as
                # context. We do this in order to point the user to an asset
                # or group when viewing the notification.
                verb = 'replied'
                context_object_id = parent['parent']
                # Subscribe to the parent of the parent comment (post or group)
                activity_subscribe(item['user'], 'node', parent['parent'])
            else:
                activity_subscribe(item['user'], 'node', item['_id'])
                verb = 'commented'
        else:
            verb = 'posted'
            activity_subscribe(item['user'], 'node', item['_id'])

        activity_object_add(
            item['user'],
            verb,
            'node',
            item['_id'],
            'node',
            context_object_id
        )


def deduct_content_type(node_doc, original):
    """Deduct the content type from the attached file, if any."""

    if node_doc['node_type'] != 'asset':
        log.debug('deduct_content_type: called on node type %r, ignoring', node_doc['node_type'])
        return

    node_id = node_doc['_id']
    try:
        file_id = ObjectId(node_doc['properties']['file'])
    except KeyError:
        log.warning('deduct_content_type: Asset without properties.file, rejecting.')
        raise UnprocessableEntity('Missing file property for asset node')

    files = current_app.data.driver.db['files']
    file_doc = files.find_one({'_id': file_id},
                              {'content_type': 1})
    if not file_doc:
        log.warning('deduct_content_type: Node %s refers to non-existing file %s, rejecting.',
                    node_id, file_id)
        raise UnprocessableEntity('File property refers to non-existing file')

    # Guess the node content type from the file content type
    file_type = file_doc['content_type']
    if file_type.startswith('video/'):
        content_type = 'video'
    elif file_type.startswith('image/'):
        content_type = 'image'
    else:
        content_type = 'file'

    node_doc['properties']['content_type'] = content_type


def before_returning_node_permissions(response):
    # Run validation process, since GET on nodes entry point is public
    check_permissions('nodes', response, 'GET', append_allowed_methods=True)


def before_returning_node_resource_permissions(response):
    for item in response['_items']:
        check_permissions('nodes', item, 'GET', append_allowed_methods=True)


def setup_app(app):
    # Permission hooks
    app.on_fetched_item_nodes += before_returning_node_permissions
    app.on_fetched_resource_nodes += before_returning_node_resource_permissions

    app.on_fetched_item_nodes += item_parse_attachments
    app.on_fetched_resource_nodes += resource_parse_attachments
    app.on_replace_nodes += before_replacing_node
    app.on_replaced_nodes += after_replacing_node
    app.on_insert_nodes += before_inserting_nodes
    app.on_inserted_nodes += after_inserting_nodes

    app.on_replace_nodes += deduct_content_type

import base64
import logging
import urlparse

import pymongo.errors
import rsa.randnum
from bson import ObjectId
from flask import current_app, g, Blueprint, request
from werkzeug.exceptions import UnprocessableEntity, InternalServerError

from application.modules import file_storage
from application.utils import str2id, jsonify
from application.utils.authorization import check_permissions, require_login
from application.utils.gcs import update_file_name
from application.utils.activities import activity_subscribe, activity_object_add

log = logging.getLogger(__name__)
blueprint = Blueprint('nodes', __name__)
ROLES_FOR_SHARING = {u'subscriber', u'demo'}


@blueprint.route('/<node_id>/share', methods=['GET', 'POST'])
@require_login(require_roles=ROLES_FOR_SHARING)
def share_node(node_id):
    """Shares a node, or returns sharing information."""

    node_id = str2id(node_id)
    nodes_coll = current_app.data.driver.db['nodes']

    node = nodes_coll.find_one({'_id': node_id},
                               projection={
                                   'project': 1,
                                   'node_type': 1,
                                   'short_code': 1
                               })

    check_permissions('nodes', node, request.method)

    log.info('Sharing node %s', node_id)

    short_code = node.get('short_code')
    status = 200

    if not short_code:
        if request.method == 'POST':
            short_code = generate_and_store_short_code(node)
            status = 201
        else:
            return '', 204

    return jsonify(short_link_info(short_code), status=status)


def generate_and_store_short_code(node):
    nodes_coll = current_app.data.driver.db['nodes']
    node_id = node['_id']

    log.debug('Creating new short link for node %s', node_id)

    max_attempts = 10
    for attempt in range(1, max_attempts):

        # Generate a new short code
        short_code = create_short_code(node)
        log.debug('Created short code for node %s: %s', node_id, short_code)

        node['short_code'] = short_code

        # Store it in MongoDB
        try:
            result = nodes_coll.update_one({'_id': node_id},
                                           {'$set': {'short_code': short_code}})
            break
        except pymongo.errors.DuplicateKeyError:
            log.info('Duplicate key while creating short code, retrying (attempt %i/%i)',
                     attempt, max_attempts)
            pass
    else:
        log.error('Unable to find unique short code for node %s after %i attempts, failing!',
                  node_id, max_attempts)
        raise InternalServerError('Unable to create unique short code for node %s' % node_id)

    # We were able to store a short code, now let's verify the result.
    if result.matched_count != 1:
        log.warning('Unable to update node %s with new short_links=%r', node_id, node['short_code'])
        raise InternalServerError('Unable to update node %s with new short links' % node_id)

    return short_code


def create_short_code(node):
    """Generates a new 'short code' for the node."""

    length = current_app.config['SHORT_CODE_LENGTH']
    bits = rsa.randnum.read_random_bits(32)
    short_code = base64.b64encode(bits, altchars='xy').rstrip('=')
    short_code = short_code[:length]

    return short_code


def short_link_info(short_code):
    """Returns the short link info in a dict."""

    short_link = urlparse.urljoin(current_app.config['SHORT_LINK_BASE_URL'], short_code)

    return {
        'short_code': short_code,
        'short_link': short_link,
    }


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

        # Default the 'user' property to the current user.
        item.setdefault('user', g.current_user['user_id'])


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


def deduct_content_type(node_doc, original=None):
    """Deduct the content type from the attached file, if any."""

    if node_doc['node_type'] != 'asset':
        log.debug('deduct_content_type: called on node type %r, ignoring', node_doc['node_type'])
        return

    node_id = node_doc.get('_id')
    try:
        file_id = ObjectId(node_doc['properties']['file'])
    except KeyError:
        if node_id is None:
            # Creation of a file-less node is allowed, but updates aren't.
            return
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


def nodes_deduct_content_type(nodes):
    for node in nodes:
        deduct_content_type(node)


def before_returning_node_permissions(response):
    # Run validation process, since GET on nodes entry point is public
    check_permissions('nodes', response, 'GET', append_allowed_methods=True)


def before_returning_node_resource_permissions(response):
    for item in response['_items']:
        check_permissions('nodes', item, 'GET', append_allowed_methods=True)


def node_set_default_picture(node, original=None):
    """Uses the image of an image asset or colour map of texture node as picture."""

    if node.get('picture'):
        log.debug('Node %s already has a picture, not overriding', node.get('_id'))
        return

    node_type = node.get('node_type')
    props = node.get('properties', {})
    content = props.get('content_type')

    if node_type == 'asset' and content == 'image':
        image_file_id = props.get('file')
    elif node_type == 'texture':
        # Find the colour map, defaulting to the first image map available.
        image_file_id = None
        for image in props.get('files', []):
            if image_file_id is None or image.get('map_type') == u'color':
                image_file_id = image.get('file')
    else:
        log.debug('Not setting default picture on node type %s content type %s',
                  node_type, content)
        return

    if image_file_id is None:
        log.debug('Nothing to set the picture to.')
        return

    log.debug('Setting default picture for node %s to %s', node.get('_id'), image_file_id)
    node['picture'] = image_file_id


def nodes_set_default_picture(nodes):
    for node in nodes:
        node_set_default_picture(node)


def setup_app(app, url_prefix):
    # Permission hooks
    app.on_fetched_item_nodes += before_returning_node_permissions
    app.on_fetched_resource_nodes += before_returning_node_resource_permissions

    app.on_fetched_item_nodes += item_parse_attachments
    app.on_fetched_resource_nodes += resource_parse_attachments

    app.on_replace_nodes += before_replacing_node
    app.on_replace_nodes += deduct_content_type
    app.on_replace_nodes += node_set_default_picture
    app.on_replaced_nodes += after_replacing_node

    app.on_insert_nodes += before_inserting_nodes
    app.on_insert_nodes += nodes_deduct_content_type
    app.on_insert_nodes += nodes_set_default_picture
    app.on_inserted_nodes += after_inserting_nodes

    app.register_blueprint(blueprint, url_prefix=url_prefix)

import logging
import os
import json
from bson import ObjectId
from datetime import datetime
import bugsnag
import bugsnag.flask
import bugsnag.handlers
from zencoder import Zencoder
from flask import g
from flask import request
from flask import abort
from eve import Eve

from eve.auth import TokenAuth
from eve.io.mongo import Validator

RFC1123_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'


class NewAuth(TokenAuth):
    def check_auth(self, token, allowed_roles, resource, method):
        return validate_token()


class ValidateCustomFields(Validator):
    def convert_properties(self, properties, node_schema):
        for prop in node_schema:
            if not prop in properties:
                continue
            schema_prop = node_schema[prop]
            prop_type = schema_prop['type']
            if prop_type == 'dict':
                properties[prop] = self.convert_properties(
                    properties[prop], schema_prop['schema'])
            if prop_type == 'list':
                if properties[prop] in ['', '[]']:
                    properties[prop] = []
                for k, val in enumerate(properties[prop]):
                    if not 'schema' in schema_prop:
                        continue
                    item_schema = {'item': schema_prop['schema']}
                    item_prop = {'item': properties[prop][k]}
                    properties[prop][k] = self.convert_properties(
                        item_prop, item_schema)['item']
            # Convert datetime string to RFC1123 datetime
            elif prop_type == 'datetime':
                prop_val = properties[prop]
                properties[prop] = datetime.strptime(prop_val, RFC1123_DATE_FORMAT)
            elif prop_type == 'objectid':
                prop_val = properties[prop]
                if prop_val:
                    properties[prop] = ObjectId(prop_val)
                else:
                    properties[prop] = None

        return properties

    def _validate_valid_properties(self, valid_properties, field, value):
        projects_collection = app.data.driver.db['projects']
        lookup = {'_id': ObjectId(self.document['project'])}
        project = projects_collection.find_one(lookup)
        node_type = next(
            (item for item in project['node_types'] if item.get('name') \
             and item['name'] == self.document['node_type']), None)
        try:
            value = self.convert_properties(value, node_type['dyn_schema'])
        except Exception, e:
            print ("Error converting: {0}".format(e))

        v = Validator(node_type['dyn_schema'])
        val = v.validate(value)

        if val:
            return True
        else:
            try:
                print (val.errors)
            except:
                pass
            self._error(
                field, "Error validating properties")


# We specify a settings.py file because when running on wsgi we can't detect it
# automatically. The default path (which works in Docker) can be overridden with
# an env variable.
settings_path = os.environ.get(
    'EVE_SETTINGS', '/data/git/pillar/pillar/settings.py')
app = Eve(settings=settings_path, validator=ValidateCustomFields, auth=NewAuth)

# Load configuration from three different sources, to make it easy to override
# settings with secrets, as well as for development & testing.
app_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app.config.from_pyfile(os.path.join(app_root, 'config.py'), silent=False)
app.config.from_pyfile(os.path.join(app_root, 'config_local.py'), silent=True)
from_envvar = os.environ.get('PILLAR_CONFIG')
if from_envvar:
    # Don't use from_envvar, as we want different behaviour. If the envvar
    # is not set, it's fine (i.e. silent=True), but if it is set and the
    # configfile doesn't exist, it should error out (i.e. silent=False).
    app.config.from_pyfile(from_envvar, silent=False)

# Configure logging
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)-15s %(levelname)8s %(name)s %(message)s')

logging.getLogger('werkzeug').setLevel(logging.INFO)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG if app.config['DEBUG'] else logging.INFO)
if app.config['DEBUG']:
    log.info('Pillar starting, debug=%s', app.config['DEBUG'])

# Configure Bugsnag
if not app.config.get('TESTING'):
    bugsnag.configure(
        api_key=app.config['BUGSNAG_API_KEY'],
        project_root="/data/git/pillar/pillar",
    )
    bugsnag.flask.handle_exceptions(app)

    bs_handler = bugsnag.handlers.BugsnagHandler()
    bs_handler.setLevel(logging.ERROR)
    log.addHandler(bs_handler)

# Google Cloud project
try:
    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = \
        app.config['GCLOUD_APP_CREDENTIALS']
except KeyError:
    raise SystemExit('GCLOUD_APP_CREDENTIALS configuration is missing')

# Storage backend (GCS)
try:
    os.environ['GCLOUD_PROJECT'] = app.config['GCLOUD_PROJECT']
except KeyError:
    raise SystemExit('GCLOUD_PROJECT configuration value is missing')

# Algolia search
if 'ALGOLIA_USER' in app.config:
    from algoliasearch import algoliasearch

    client = algoliasearch.Client(
        app.config['ALGOLIA_USER'],
        app.config['ALGOLIA_API_KEY'])
    algolia_index_users = client.init_index(app.config['ALGOLIA_INDEX_USERS'])
    algolia_index_nodes = client.init_index(app.config['ALGOLIA_INDEX_NODES'])
else:
    algolia_index_users = None
    algolia_index_nodes = None

# Encoding backend
if app.config['ENCODING_BACKEND'] == 'zencoder':
    encoding_service_client = Zencoder(app.config['ZENCODER_API_KEY'])
else:
    encoding_service_client = None

from utils.authentication import validate_token
from utils.authorization import check_permissions
from utils.gcs import update_file_name
from utils.activities import activity_subscribe
from utils.activities import activity_object_add
from utils.activities import notification_parse
from modules import file_storage
from modules.projects import before_inserting_projects
from modules.projects import after_inserting_projects


@app.before_request
def validate_token_at_every_request():
    validate_token()


def before_returning_item_permissions(response):
    # Run validation process, since GET on nodes entry point is public
    check_permissions(response, 'GET', append_allowed_methods=True)


def before_returning_resource_permissions(response):
    for item in response['_items']:
        check_permissions(item, 'GET', append_allowed_methods=True)


def before_replacing_node(item, original):
    check_permissions(original, 'PUT')
    update_file_name(item)


def after_replacing_node(item, original):
    """Push an update to the Algolia index when a node item is updated. If the
    project is private, prevent public indexing.
    """
    projects_collection = app.data.driver.db['projects']
    project = projects_collection.find_one({'_id': item['project']},
                                           {'is_private': 1})
    if 'is_private' in project and project['is_private']:
        # Skip index updating and return
        return

    from algoliasearch.client import AlgoliaException
    from utils.algolia import algolia_index_node_save

    try:
        algolia_index_node_save(item)
    except AlgoliaException as ex:
        log.warning('Unable to push node info to Algolia for node %s; %s',
                    item.get('_id'), ex)


def before_inserting_nodes(items):
    """Before inserting a node in the collection we check if the user is allowed
    and we append the project id to it.
    """
    nodes_collection = app.data.driver.db['nodes']

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
        check_permissions(item, 'POST')
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
            nodes_collection = app.data.driver.db['nodes']
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


def item_parse_attachments(response):
    """Before returning a response, check if the 'attachments' property is
    defined. If yes, load the file (for the moment only images) in the required
    variation, get the link and build a Markdown representation. Search in the
    'field' specified in the attachment and replace the 'slug' tag with the
    generated link.
    """
    if 'properties' in response and 'attachments' in response['properties']:
        files_collection = app.data.driver.db['files']
        for field in response['properties']['attachments']:
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


def project_node_type_has_method(response):
    """Check for a specific request arg, and check generate the allowed_methods
    list for the required node_type.
    """
    try:
        node_type_name = request.args['node_type']
    except KeyError:
        return
    # Proceed only node_type has been requested
    if node_type_name:
        # Look up the node type in the project document
        node_type = next(
            (item for item in response['node_types'] if item.get('name') \
             and item['name'] == node_type_name), None)
        if not node_type:
            return abort(404)
        # Check permissions and append the allowed_methods to the node_type
        check_permissions(node_type, 'GET', append_allowed_methods=True)


def before_returning_item_notifications(response):
    if request.args.get('parse'):
        notification_parse(response)


def before_returning_resource_notifications(response):
    for item in response['_items']:
        if request.args.get('parse'):
            notification_parse(item)


app.on_fetched_item_nodes += before_returning_item_permissions
app.on_fetched_item_nodes += item_parse_attachments
app.on_fetched_resource_nodes += before_returning_resource_permissions
app.on_fetched_resource_nodes += resource_parse_attachments
app.on_fetched_item_node_types += before_returning_item_permissions
app.on_fetched_item_notifications += before_returning_item_notifications
app.on_fetched_resource_notifications += before_returning_resource_notifications
app.on_fetched_resource_node_types += before_returning_resource_permissions
app.on_replace_nodes += before_replacing_node
app.on_replaced_nodes += after_replacing_node
app.on_insert_nodes += before_inserting_nodes
app.on_inserted_nodes += after_inserting_nodes
app.on_fetched_item_projects += before_returning_item_permissions
app.on_fetched_item_projects += project_node_type_has_method
app.on_fetched_resource_projects += before_returning_resource_permissions

file_storage.setup_app(app, url_prefix='/storage')

# The encoding module (receive notification and report progress)
from modules.encoding import encoding
from modules.blender_id import blender_id
from modules import projects
from modules import local_auth
from modules import users

app.register_blueprint(encoding, url_prefix='/encoding')
app.register_blueprint(blender_id, url_prefix='/blender_id')
projects.setup_app(app, url_prefix='/p')
local_auth.setup_app(app, url_prefix='/auth')
users.setup_app(app)

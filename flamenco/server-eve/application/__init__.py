import logging
import logging.config
import os
import tempfile
from bson import ObjectId
from datetime import datetime
from flask import g
from flask import request
from flask import abort
from eve import Eve

from eve.auth import TokenAuth
from eve.io.mongo import Validator

from application.utils import project_get_node_type

RFC1123_DATE_FORMAT = '%a, %d %b %Y %H:%M:%S GMT'


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
        node_type = project_get_node_type(project, self.document['node_type'])
        try:
            value = self.convert_properties(value, node_type['dyn_schema'])
        except Exception as e:
            log.warning("Error converting form properties", exc_info=True)

        v = Validator(node_type['dyn_schema'])
        val = v.validate(value)

        if val:
            return True

        log.debug('Error validating properties for node %s: %s', self.document, v.errors)
        self._error(field, "Error validating properties")


# We specify a settings.py file because when running on wsgi we can't detect it
# automatically. The default path (which works in Docker) can be overridden with
# an env variable.
settings_path = os.environ.get(
    'EVE_SETTINGS', '/data/git/pillar/pillar/settings.py')
app = Eve(settings=settings_path, validator=ValidateCustomFields)

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

# Set the TMP environment variable to manage where uploads are stored.
# These are all used by tempfile.mkstemp(), but we don't knwow in whic
# order. As such, we remove all used variables but the one we set.
tempfile.tempdir = app.config['STORAGE_DIR']
os.environ['TMP'] = app.config['STORAGE_DIR']
os.environ.pop('TEMP', None)
os.environ.pop('TMPDIR', None)


# Configure logging
logging.config.dictConfig(app.config['LOGGING'])
log = logging.getLogger(__name__)
if app.config['DEBUG']:
    log.info('Pillar starting, debug=%s', app.config['DEBUG'])

# Configure Bugsnag
if not app.config.get('TESTING') and app.config.get('BUGSNAG_API_KEY'):
    import bugsnag
    import bugsnag.flask
    import bugsnag.handlers

    bugsnag.configure(
        api_key=app.config['BUGSNAG_API_KEY'],
        project_root="/data/git/pillar/pillar",
    )
    bugsnag.flask.handle_exceptions(app)

    bs_handler = bugsnag.handlers.BugsnagHandler()
    bs_handler.setLevel(logging.ERROR)
    log.addHandler(bs_handler)
else:
    log.info('Bugsnag NOT configured.')

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
if app.config['SEARCH_BACKEND'] == 'algolia':
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
    from zencoder import Zencoder
    encoding_service_client = Zencoder(app.config['ZENCODER_API_KEY'])
else:
    encoding_service_client = None

from utils.authentication import validate_token
from utils.authorization import check_permissions
from utils.activities import notification_parse
from modules.projects import before_inserting_projects
from modules.projects import after_inserting_projects


@app.before_request
def validate_token_at_every_request():
    validate_token()


def before_returning_item_notifications(response):
    if request.args.get('parse'):
        notification_parse(response)


def before_returning_resource_notifications(response):
    for item in response['_items']:
        if request.args.get('parse'):
            notification_parse(item)


app.on_fetched_item_notifications += before_returning_item_notifications
app.on_fetched_resource_notifications += before_returning_resource_notifications


# The encoding module (receive notification and report progress)
from modules.encoding import encoding
from modules.blender_id import blender_id
from modules import projects
from modules import local_auth
from modules import file_storage
from modules import users
from modules import nodes
from modules import latest
from modules import blender_cloud
from modules import service

app.register_blueprint(encoding, url_prefix='/encoding')
app.register_blueprint(blender_id, url_prefix='/blender_id')
projects.setup_app(app, url_prefix='/p')
local_auth.setup_app(app, url_prefix='/auth')
file_storage.setup_app(app, url_prefix='/storage')
latest.setup_app(app, url_prefix='/latest')
blender_cloud.setup_app(app, url_prefix='/bcloud')
users.setup_app(app, url_prefix='/users')
service.setup_app(app, url_prefix='/service')
nodes.setup_app(app)

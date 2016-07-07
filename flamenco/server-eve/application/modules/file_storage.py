import datetime
import logging
import mimetypes
import os
import tempfile
import uuid
import io
from hashlib import md5

import bson.tz_util
import eve.utils
import pymongo
from bson import ObjectId
from bson.errors import InvalidId
from eve.methods.patch import patch_internal
from eve.methods.post import post_internal
from eve.methods.put import put_internal
from flask import Blueprint
from flask import jsonify
from flask import request
from flask import send_from_directory
from flask import url_for, helpers
from flask import current_app
from flask import g
from flask import make_response
from werkzeug.exceptions import NotFound, InternalServerError, BadRequest

from application import utils
from application.utils import remove_private_keys, authentication
from application.utils.authorization import require_login, user_has_role
from application.utils.cdn import hash_file_path
from application.utils.encoding import Encoder
from application.utils.gcs import GoogleCloudStorageBucket
from application.utils.imaging import generate_local_thumbnails

log = logging.getLogger(__name__)

file_storage = Blueprint('file_storage', __name__,
                         template_folder='templates',
                         static_folder='../../static/storage', )

# Add our own extensions to the mimetypes package
mimetypes.add_type('application/x-blender', '.blend')


@file_storage.route('/gcs/<bucket_name>/<subdir>/')
@file_storage.route('/gcs/<bucket_name>/<subdir>/<path:file_path>')
def browse_gcs(bucket_name, subdir, file_path=None):
    """Browse the content of a Google Cloud Storage bucket"""

    # Initialize storage client
    storage = GoogleCloudStorageBucket(bucket_name, subdir=subdir)
    if file_path:
        # If we provided a file_path, we try to fetch it
        file_object = storage.Get(file_path)
        if file_object:
            # If it exists, return file properties in a dictionary
            return jsonify(file_object)
        else:
            listing = storage.List(file_path)
            return jsonify(listing)
            # We always return an empty listing even if the directory does not
            # exist. This can be changed later.
            # return abort(404)

    else:
        listing = storage.List('')
        return jsonify(listing)


@file_storage.route('/file', methods=['POST'])
@file_storage.route('/file/<path:file_name>', methods=['GET', 'POST'])
def index(file_name=None):
    # GET file -> read it
    if request.method == 'GET':
        return send_from_directory(current_app.config['STORAGE_DIR'], file_name)

    # POST file -> save it

    # Sanitize the filename; source: http://stackoverflow.com/questions/7406102/
    file_name = request.form['name']
    keepcharacters = {' ', '.', '_'}
    file_name = ''.join(
        c for c in file_name if c.isalnum() or c in keepcharacters).strip()
    file_name = file_name.lstrip('.')

    # Determine & create storage directory
    folder_name = file_name[:2]
    file_folder_path = helpers.safe_join(current_app.config['STORAGE_DIR'], folder_name)
    if not os.path.exists(file_folder_path):
        log.info('Creating folder path %r', file_folder_path)
        os.mkdir(file_folder_path)

    # Save uploaded file
    file_path = helpers.safe_join(file_folder_path, file_name)
    log.info('Saving file %r', file_path)
    request.files['data'].save(file_path)

    # TODO: possibly nicer to just return a redirect to the file's URL.
    return jsonify({'url': url_for('file_storage.index', file_name=file_name)})


def _process_image(gcs, file_id, local_file, src_file):
    from PIL import Image

    im = Image.open(local_file)
    res = im.size
    src_file['width'] = res[0]
    src_file['height'] = res[1]

    # Generate previews
    log.info('Generating thumbnails for file %s', file_id)
    src_file['variations'] = generate_local_thumbnails(src_file['name'],
                                                       local_file.name)

    # Send those previews to Google Cloud Storage.
    log.info('Uploading %i thumbnails for file %s to Google Cloud Storage (GCS)',
             len(src_file['variations']), file_id)

    # TODO: parallelize this at some point.
    for variation in src_file['variations']:
        fname = variation['file_path']
        log.debug('  - Sending thumbnail %s to GCS', fname)
        blob = gcs.bucket.blob('_/' + fname, chunk_size=256 * 1024 * 2)
        blob.upload_from_filename(variation['local_path'],
                                  content_type=variation['content_type'])

        if variation.get('size') == 't':
            blob.make_public()

        try:
            os.unlink(variation['local_path'])
        except OSError:
            log.warning('Unable to unlink %s, ignoring this but it will need cleanup later.',
                        variation['local_path'])

        del variation['local_path']

    log.info('Done processing file %s', file_id)
    src_file['status'] = 'complete'


def _process_video(gcs, file_id, local_file, src_file):
    """Video is processed by Zencoder; the file isn't even stored locally."""

    log.info('Processing video for file %s', file_id)

    # Create variations
    root, _ = os.path.splitext(src_file['file_path'])
    src_file['variations'] = []

    # Most of these properties will be available after encode.
    v = 'mp4'
    file_variation = dict(
        format=v,
        content_type='video/{}'.format(v),
        file_path='{}-{}.{}'.format(root, v, v),
        size='',
        duration=0,
        width=0,
        height=0,
        length=0,
        md5='',
    )
    # Append file variation. Originally mp4 and webm were the available options,
    # that's why we build a list.
    src_file['variations'].append(file_variation)

    j = Encoder.job_create(src_file)
    if j is None:
        log.warning('_process_video: unable to create encoder job for file %s.', file_id)
        return

    log.info('Created asynchronous Zencoder job %s for file %s', j['process_id'], file_id)

    # Add the processing status to the file object
    src_file['processing'] = {
        'status': 'pending',
        'job_id': str(j['process_id']),
        'backend': j['backend']}


def process_file(gcs, file_id, local_file):
    """Process the file by creating thumbnails, sending to Zencoder, etc.

    :param file_id: '_id' key of the file
    :type file_id: ObjectId or str
    :param local_file: locally stored file, or None if no local processing is needed.
    :type local_file: file
    """

    file_id = ObjectId(file_id)

    # Fetch the src_file document from MongoDB.
    files = current_app.data.driver.db['files']
    src_file = files.find_one(file_id)
    if not src_file:
        log.warning('process_file(%s): no such file document found, ignoring.')
        return
    src_file = utils.remove_private_keys(src_file)

    # Update the 'format' field from the content type.
    # TODO: overrule the content type based on file extention & magic numbers.
    mime_category, src_file['format'] = src_file['content_type'].split('/', 1)

    # Prevent video handling for non-admins.
    if not user_has_role(u'admin') and mime_category == 'video':
        if src_file['format'].startswith('x-'):
            xified = src_file['format']
        else:
            xified = 'x-' + src_file['format']

        src_file['content_type'] = 'application/%s' % xified
        mime_category = 'application'
        log.info('Not processing video file %s for non-admin user', file_id)

    # Run the required processor, based on the MIME category.
    processors = {
        'image': _process_image,
        'video': _process_video,
    }

    try:
        processor = processors[mime_category]
    except KeyError:
        log.info("POSTed file %s was of type %r, which isn't thumbnailed/encoded.", file_id,
                 mime_category)
        src_file['status'] = 'complete'
    else:
        log.debug('process_file(%s): marking file status as "processing"', file_id)
        src_file['status'] = 'processing'
        update_file_doc(file_id, status='processing')

        try:
            processor(gcs, file_id, local_file, src_file)
        except Exception:
            log.warning('process_file(%s): error when processing file, resetting status to '
                        '"queued_for_processing"', file_id, exc_info=True)
            update_file_doc(file_id, status='queued_for_processing')
            return

    # Update the original file with additional info, e.g. image resolution
    r, _, _, status = put_internal('files', src_file, _id=file_id)
    if status not in (200, 201):
        log.warning('process_file(%s): status %i when saving processed file info to MongoDB: %s',
                    file_id, status, r)


def delete_file(file_item):
    def process_file_delete(file_item):
        """Given a file item, delete the actual file from the storage backend.
        This function can be probably made self-calling."""
        if file_item['backend'] == 'gcs':
            storage = GoogleCloudStorageBucket(str(file_item['project']))
            storage.Delete(file_item['file_path'])
            # Delete any file variation found in the file_item document
            if 'variations' in file_item:
                for v in file_item['variations']:
                    storage.Delete(v['file_path'])
            return True
        elif file_item['backend'] == 'pillar':
            pass
        elif file_item['backend'] == 'cdnsun':
            pass
        else:
            pass

    files_collection = current_app.data.driver.db['files']
    # Collect children (variations) of the original file
    children = files_collection.find({'parent': file_item['_id']})
    for child in children:
        process_file_delete(child)
    # Finally remove the original file
    process_file_delete(file_item)


def generate_link(backend, file_path, project_id=None, is_public=False):
    """Hook to check the backend of a file resource, to build an appropriate link
    that can be used by the client to retrieve the actual file.
    """

    if backend == 'gcs':
        storage = GoogleCloudStorageBucket(project_id)
        blob = storage.Get(file_path)
        if blob is None:
            return ''

        if is_public:
            return blob['public_url']
        return blob['signed_url']

    if backend == 'pillar':
        return url_for('file_storage.index', file_name=file_path, _external=True,
                       _scheme=current_app.config['SCHEME'])
    if backend == 'cdnsun':
        return hash_file_path(file_path, None)
    if backend == 'unittest':
        return md5(file_path).hexdigest()

    return ''


def before_returning_file(response):
    ensure_valid_link(response)

    # Enable this call later, when we have implemented the is_public field on files.
    # strip_link_and_variations(response)


def strip_link_and_variations(response):
    # Check the access level of the user.
    if g.current_user is None:
        has_full_access = False
    else:
        user_roles = g.current_user['roles']
        access_roles = current_app.config['FULL_FILE_ACCESS_ROLES']
        has_full_access = bool(user_roles.intersection(access_roles))

    # Strip all file variations (unless image) and link to the actual file.
    if not has_full_access:
        response.pop('link', None)
        response.pop('link_expires', None)

        # Image files have public variations, other files don't.
        if not response.get('content_type', '').startswith('image/'):
            if response.get('variations') is not None:
                response['variations'] = []


def before_returning_files(response):
    for item in response['_items']:
        ensure_valid_link(item)


def ensure_valid_link(response):
    """Ensures the file item has valid file links using generate_link(...)."""

    # log.debug('Inspecting link for file %s', response['_id'])

    # Check link expiry.
    now = datetime.datetime.now(tz=bson.tz_util.utc)
    if 'link_expires' in response:
        link_expires = response['link_expires']
        if now < link_expires:
            # Not expired yet, so don't bother regenerating anything.
            log.debug('Link expires at %s, which is in the future, so not generating new link',
                      link_expires)
            return

        log.debug('Link expired at %s, which is in the past; generating new link', link_expires)
    else:
        log.debug('No expiry date for link; generating new link')

    _generate_all_links(response, now)


def _generate_all_links(response, now):
    """Generate a new link for the file and all its variations.

    :param response: the file document that should be updated.
    :param now: datetime that reflects 'now', for consistent expiry generation.
    """

    project_id = str(
        response['project']) if 'project' in response else None  # TODO: add project id to all files
    backend = response['backend']
    response['link'] = generate_link(backend, response['file_path'], project_id)

    variations = response.get('variations')
    if variations:
        for variation in variations:
            variation['link'] = generate_link(backend, variation['file_path'], project_id)

    # Construct the new expiry datetime.
    validity_secs = current_app.config['FILE_LINK_VALIDITY'][backend]
    response['link_expires'] = now + datetime.timedelta(seconds=validity_secs)

    patch_info = remove_private_keys(response)
    file_id = ObjectId(response['_id'])
    (patch_resp, _, _, _) = patch_internal('files', patch_info, _id=file_id)
    if patch_resp.get('_status') == 'ERR':
        log.warning('Unable to save new links for file %s: %r', response['_id'], patch_resp)
        # TODO: raise a snag.
        response['_updated'] = now
    else:
        response['_updated'] = patch_resp['_updated']

    # Be silly and re-fetch the etag ourselves. TODO: handle this better.
    etag_doc = current_app.data.driver.db['files'].find_one({'_id': file_id}, {'_etag': 1})
    response['_etag'] = etag_doc['_etag']


def before_deleting_file(item):
    delete_file(item)


def on_pre_get_files(_, lookup):
    # Override the HTTP header, we always want to fetch the document from MongoDB.
    parsed_req = eve.utils.parse_request('files')
    parsed_req.if_modified_since = None

    # Only fetch it if the date got expired.
    now = datetime.datetime.now(tz=bson.tz_util.utc)
    lookup_expired = lookup.copy()
    lookup_expired['link_expires'] = {'$lte': now}

    cursor = current_app.data.find('files', parsed_req, lookup_expired)
    for file_doc in cursor:
        log.debug('Updating expired links for file %r.', file_doc['_id'])
        _generate_all_links(file_doc, now)


def refresh_links_for_project(project_uuid, chunk_size, expiry_seconds):
    if chunk_size:
        log.info('Refreshing the first %i links for project %s', chunk_size, project_uuid)
    else:
        log.info('Refreshing all links for project %s', project_uuid)

    # Retrieve expired links.
    files_collection = current_app.data.driver.db['files']

    now = datetime.datetime.now(tz=bson.tz_util.utc)
    expire_before = now + datetime.timedelta(seconds=expiry_seconds)
    log.info('Limiting to links that expire before %s', expire_before)

    to_refresh = files_collection.find(
        {'project': ObjectId(project_uuid),
         'link_expires': {'$lt': expire_before},
         }).sort([('link_expires', pymongo.ASCENDING)]).limit(chunk_size)

    if to_refresh.count() == 0:
        log.info('No links to refresh.')
        return

    for file_doc in to_refresh:
        log.debug('Refreshing links for file %s', file_doc['_id'])
        _generate_all_links(file_doc, now)

    log.info('Refreshed %i links', min(chunk_size, to_refresh.count()))


def refresh_links_for_backend(backend_name, chunk_size, expiry_seconds):
    from flask import current_app

    # Retrieve expired links.
    files_collection = current_app.data.driver.db['files']

    now = datetime.datetime.now(tz=bson.tz_util.utc)
    expire_before = now + datetime.timedelta(seconds=expiry_seconds)
    log.info('Limiting to links that expire before %s', expire_before)

    to_refresh = files_collection.find(
        {'$or': [{'backend': backend_name, 'link_expires': None},
                 {'backend': backend_name, 'link_expires': {'$lt': expire_before}},
                 {'backend': backend_name, 'link': None}]
         }).sort([('link_expires', pymongo.ASCENDING)]).limit(chunk_size)

    if to_refresh.count() == 0:
        log.info('No links to refresh.')
        return

    for file_doc in to_refresh:
        log.debug('Refreshing links for file %s', file_doc['_id'])
        _generate_all_links(file_doc, now)

    log.info('Refreshed %i links', min(chunk_size, to_refresh.count()))


@require_login()
def create_file_doc(name, filename, content_type, length, project, backend='gcs',
                    **extra_fields):
    """Creates a minimal File document for storage in MongoDB.

    Doesn't save it to MongoDB yet.
    """

    current_user = g.get('current_user')

    file_doc = {'name': name,
                'filename': filename,
                'file_path': '',
                'user': current_user['user_id'],
                'backend': backend,
                'md5': '',
                'content_type': content_type,
                'length': length,
                'project': project}
    file_doc.update(extra_fields)

    return file_doc


def override_content_type(uploaded_file):
    """Overrides the content type based on file extensions.

    :param uploaded_file: file from request.files['form-key']
    :type uploaded_file: werkzeug.datastructures.FileStorage
    """

    # Possibly use the browser-provided mime type
    mimetype = uploaded_file.mimetype
    if '/' in mimetype:
        mimecat = mimetype.split('/')[0]
        if mimecat in {'video', 'audio', 'image'}:
            # The browser's mime type is probably ok, just use it.
            return

    # And then use it to set the mime type.
    (mimetype, encoding) = mimetypes.guess_type(uploaded_file.filename)

    # Only override the mime type if we can detect it, otherwise just
    # keep whatever the browser gave us.
    if mimetype:
        # content_type property can't be set directly
        uploaded_file.headers['content-type'] = mimetype

        # It has this, because we used uploaded_file.mimetype earlier this function.
        del uploaded_file._parsed_content_type


@file_storage.route('/stream/<string:project_id>', methods=['POST', 'OPTIONS'])
@require_login()
def stream_to_gcs(project_id):
    try:
        project_oid = ObjectId(project_id)
    except InvalidId:
        raise BadRequest('Invalid ObjectID')

    projects = current_app.data.driver.db['projects']
    project = projects.find_one(project_oid, projection={'_id': 1})

    if not project:
        raise NotFound('Project %s does not exist' % project_id)

    log.info('Streaming file to bucket for project=%s user_id=%s', project_id,
             authentication.current_user_id())
    uploaded_file = request.files['file']

    override_content_type(uploaded_file)
    if not uploaded_file.content_type:
        log.warning('File uploaded to project %s without content type.', project_oid)
        raise BadRequest('Missing content type.')

    file_id, internal_fname, status = create_file_doc_for_upload(project_oid, uploaded_file)

    if uploaded_file.content_type.startswith('image/'):
        # We need to do local thumbnailing, so we have to write the stream
        # both to Google Cloud Storage and to local storage.
        local_file = tempfile.NamedTemporaryFile(dir=current_app.config['STORAGE_DIR'])
        uploaded_file.save(local_file)
        local_file.seek(0)  # Make sure that a re-read starts from the beginning.
        stream_for_gcs = local_file
    else:
        local_file = None
        stream_for_gcs = uploaded_file.stream

    # Figure out the file size, as we need to pass this in explicitly to GCloud.
    # Otherwise it always uses os.fstat(file_obj.fileno()).st_size, which isn't
    # supported by a BytesIO object (even though it does have a fileno attribute).
    if isinstance(stream_for_gcs, io.BytesIO):
        file_size = len(stream_for_gcs.getvalue())
    else:
        file_size = os.fstat(stream_for_gcs.fileno()).st_size

    # Upload the file to GCS.
    from gcloud.streaming import transfer
    # Files larger than this many bytes will be streamed directly from disk, smaller
    # ones will be read into memory and then uploaded.
    transfer.RESUMABLE_UPLOAD_THRESHOLD = 102400
    try:
        gcs = GoogleCloudStorageBucket(project_id)
        blob = gcs.bucket.blob('_/' + internal_fname, chunk_size=256 * 1024 * 2)
        blob.upload_from_file(stream_for_gcs, size=file_size,
                              content_type=uploaded_file.mimetype)
    except Exception:
        log.exception('Error uploading file to Google Cloud Storage (GCS),'
                      ' aborting handling of uploaded file (id=%s).', file_id)
        update_file_doc(file_id, status='failed')
        raise InternalServerError('Unable to stream file to Google Cloud Storage')

    # Reload the blob to get the file size according to Google.
    blob.reload()
    update_file_doc(file_id,
                    status='queued_for_processing',
                    file_path=internal_fname,
                    length=blob.size,
                    content_type=uploaded_file.mimetype)

    process_file(gcs, file_id, local_file)

    # Local processing is done, we can close the local file so it is removed.
    if local_file is not None:
        local_file.close()

    log.debug('Handled uploaded file id=%s, fname=%s, size=%i', file_id, internal_fname, blob.size)

    # Status is 200 if the file already existed, and 201 if it was newly created.
    # TODO: add a link to a thumbnail in the response.
    resp = jsonify(status='ok', file_id=str(file_id))
    resp.status_code = status
    add_access_control_headers(resp)
    return resp


def add_access_control_headers(resp):
    """Allows cross-site requests from the configured domain."""

    if 'Origin' not in request.headers:
        return resp

    resp.headers['Access-Control-Allow-Origin'] = request.headers['Origin']
    resp.headers['Access-Control-Allow-Credentials'] = 'true'
    return resp


def update_file_doc(file_id, **updates):
    files = current_app.data.driver.db['files']
    res = files.update_one({'_id': ObjectId(file_id)},
                           {'$set': updates})
    log.debug('update_file_doc(%s, %s): %i matched, %i updated.',
              file_id, updates, res.matched_count, res.modified_count)
    return res


def create_file_doc_for_upload(project_id, uploaded_file):
    """Creates a secure filename and a document in MongoDB for the file.

    The (project_id, filename) tuple should be unique. If such a document already
    exists, it is updated with the new file.

    :param uploaded_file: file from request.files['form-key']
    :type uploaded_file: werkzeug.datastructures.FileStorage
    :returns: a tuple (file_id, filename, status), where 'filename' is the internal
            filename used on GCS.
    """

    project_id = ObjectId(project_id)

    # Hash the filename with path info to get the internal name. This should
    # be unique for the project.
    # internal_filename = uploaded_file.filename
    _, ext = os.path.splitext(uploaded_file.filename)
    internal_filename = uuid.uuid4().hex + ext

    # For now, we don't support overwriting files, and create a new one every time.
    # # See if we can find a pre-existing file doc.
    # files = current_app.data.driver.db['files']
    # file_doc = files.find_one({'project': project_id,
    #                            'name': internal_filename})
    file_doc = None

    # TODO: at some point do name-based and content-based content-type sniffing.
    new_props = {'filename': uploaded_file.filename,
                 'content_type': uploaded_file.mimetype,
                 'length': uploaded_file.content_length,
                 'project': project_id,
                 'status': 'uploading'}

    if file_doc is None:
        # Create a file document on MongoDB for this file.
        file_doc = create_file_doc(name=internal_filename, **new_props)
        file_fields, _, _, status = post_internal('files', file_doc)
    else:
        file_doc.update(new_props)
        file_fields, _, _, status = put_internal('files', remove_private_keys(file_doc))

    if status not in (200, 201):
        log.error('Unable to create new file document in MongoDB, status=%i: %s',
                  status, file_fields)
        raise InternalServerError()

    return file_fields['_id'], internal_filename, status


def compute_aggregate_length(file_doc, original=None):
    """Computes the total length (in bytes) of the file and all variations.

    Stores the result in file_doc['length_aggregate_in_bytes']
    """

    # Compute total size of all variations.
    variations = file_doc.get('variations', ())
    var_length = sum(var.get('length', 0) for var in variations)

    file_doc['length_aggregate_in_bytes'] = file_doc.get('length', 0) + var_length


def compute_aggregate_length_items(file_docs):
    for file_doc in file_docs:
        compute_aggregate_length(file_doc)


def setup_app(app, url_prefix):
    app.on_pre_GET_files += on_pre_get_files

    app.on_fetched_item_files += before_returning_file
    app.on_fetched_resource_files += before_returning_files

    app.on_delete_item_files += before_deleting_file

    app.on_update_files += compute_aggregate_length
    app.on_replace_files += compute_aggregate_length
    app.on_insert_files += compute_aggregate_length_items

    app.register_blueprint(file_storage, url_prefix=url_prefix)

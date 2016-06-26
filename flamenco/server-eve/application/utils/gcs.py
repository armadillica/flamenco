import os
import time
import datetime
import logging

from bson import ObjectId
from gcloud.storage.client import Client
from gcloud.exceptions import NotFound
from flask import current_app

log = logging.getLogger(__name__)


class GoogleCloudStorageBucket(object):
    """Cloud Storage bucket interface. We create a bucket for every project. In
    the bucket we create first level subdirs as follows:
    - '_' (will contain hashed assets, and stays on top of default listing)
    - 'svn' (svn checkout mirror)
    - 'shared' (any additional folder of static folder that is accessed via a
      node of 'storage' node_type)

    :type bucket_name: string
    :param bucket_name: Name of the bucket.

    :type subdir: string
    :param subdir: The local entry point to browse the bucket.

    """

    def __init__(self, bucket_name, subdir='_/'):
        gcs = Client()
        try:
            self.bucket = gcs.get_bucket(bucket_name)
        except NotFound:
            self.bucket = gcs.bucket(bucket_name)
            # Hardcode the bucket location to EU
            self.bucket.location = 'EU'
            self.bucket.create()

        self.subdir = subdir


    def List(self, path=None):
        """Display the content of a subdir in the project bucket. If the path
        points to a file the listing is simply empty.

        :type path: string
        :param path: The relative path to the directory or asset.
        """
        if path and not path.endswith('/'):
            path += '/'
        prefix = os.path.join(self.subdir, path)

        fields_to_return = 'nextPageToken,items(name,size,contentType),prefixes'
        req = self.bucket.list_blobs(fields=fields_to_return, prefix=prefix,
                                     delimiter='/')

        files = []
        for f in req:
            filename = os.path.basename(f.name)
            if filename != '':  # Skip own folder name
                files.append(dict(
                    path=os.path.relpath(f.name, self.subdir),
                    text=filename,
                    type=f.content_type))

        directories = []
        for dir_path in req.prefixes:
            directory_name = os.path.basename(os.path.normpath(dir_path))
            directories.append(dict(
                text=directory_name,
                path=os.path.relpath(dir_path, self.subdir),
                type='group_storage',
                children=True))
            # print os.path.basename(os.path.normpath(path))

        list_dict = dict(
            name=os.path.basename(os.path.normpath(path)),
            type='group_storage',
            children=files + directories
        )

        return list_dict

    def blob_to_dict(self, blob):
        blob.reload()
        expiration = datetime.datetime.now() + datetime.timedelta(days=1)
        expiration = int(time.mktime(expiration.timetuple()))
        return dict(
            updated=blob.updated,
            name=os.path.basename(blob.name),
            size=blob.size,
            content_type=blob.content_type,
            signed_url=blob.generate_signed_url(expiration),
            public_url=blob.public_url)

    def Get(self, path, to_dict=True):
        """Get selected file info if the path matches.

        :type path: string
        :param path: The relative path to the file.
        :type to_dict: bool
        :param to_dict: Return the object as a dictionary.
        """
        path = os.path.join(self.subdir, path)
        blob = self.bucket.blob(path)
        if blob.exists():
            if to_dict:
                return self.blob_to_dict(blob)
            else:
                return blob
        else:
            return None

    def Post(self, full_path, path=None):
        """Create new blob and upload data to it.
        """
        path = path if path else os.path.join('_', os.path.basename(full_path))
        blob = self.bucket.blob(path)
        if blob.exists():
            return None
        blob.upload_from_filename(full_path)
        return blob
        # return self.blob_to_dict(blob) # Has issues with threading

    def Delete(self, path):
        """Delete blob (when removing an asset or replacing a preview)"""

        # We want to get the actual blob to delete
        blob = self.Get(path, to_dict=False)
        try:
            blob.delete()
            return True
        except NotFound:
            return None

    def update_name(self, blob, name):
        """Set the ContentDisposition metadata so that when a file is downloaded
        it has a human-readable name.
        """
        blob.content_disposition = u'attachment; filename="{0}"'.format(name)
        blob.patch()


def update_file_name(node):
    """Assign to the CGS blob the same name of the asset node. This way when
    downloading an asset we get a human-readable name.
    """

    # Process only files that are not processing
    if node['properties'].get('status', '') == 'processing':
        return

    def _format_name(name, override_ext, size=None, map_type=u''):
        root, _ = os.path.splitext(name)
        size = u'-{}'.format(size) if size else u''
        map_type = u'-{}'.format(map_type) if map_type else u''
        return u'{}{}{}{}'.format(root, size, map_type, override_ext)

    def _update_name(file_id, file_props):
        files_collection = current_app.data.driver.db['files']
        file_doc = files_collection.find_one({'_id': ObjectId(file_id)})

        if file_doc is None or file_doc['backend'] != 'gcs':
            return

        # For textures -- the map type should be part of the name.
        map_type = file_props.get('map_type', u'')

        storage = GoogleCloudStorageBucket(str(node['project']))
        blob = storage.Get(file_doc['file_path'], to_dict=False)
        # Pick file extension from original filename
        _, ext = os.path.splitext(file_doc['filename'])
        name = _format_name(node['name'], ext, map_type=map_type)
        storage.update_name(blob, name)

        # Assign the same name to variations
        for v in file_doc.get('variations', []):
            _, override_ext = os.path.splitext(v['file_path'])
            name = _format_name(node['name'], override_ext, v['size'], map_type=map_type)
            blob = storage.Get(v['file_path'], to_dict=False)
            if blob is None:
                log.info('Unable to find blob for file %s in project %s. This can happen if the '
                         'video encoding is still processing.', v['file_path'], node['project'])
                continue
            storage.update_name(blob, name)

    # Currently we search for 'file' and 'files' keys in the object properties.
    # This could become a bit more flexible and realy on a true reference of the
    # file object type from the schema.
    if 'file' in node['properties']:
        _update_name(node['properties']['file'], {})

    if 'files' in node['properties']:
        for file_props in node['properties']['files']:
            _update_name(file_props['file'], file_props)

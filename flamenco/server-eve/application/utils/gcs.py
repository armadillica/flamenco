import os
import time
import datetime
import bugsnag
from bson import ObjectId
from gcloud.storage.client import Client
from gcloud.exceptions import NotFound
from flask import current_app


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
        blob.content_disposition = 'attachment; filename="{0}"'.format(name)
        blob.patch()


def update_file_name(item):
    """Assign to the CGS blob the same name of the asset node. This way when
    downloading an asset we get a human-readable name.
    """

    def _format_name(name, format, size=None):
        # If the name already has an extention, and such extension matches the
        # format, only inject the size.
        root, ext = os.path.splitext(name)
        size = "-{0}".format(size) if size else ''
        ext = ext if len(ext) > 1 and ext[1:] == format else ".{0}".format(format)
        return "{0}{1}{2}".format(root, size, ext)

    def _update_name(item, file_id):
        files_collection = current_app.data.driver.db['files']
        f = files_collection.find_one({'_id': ObjectId(file_id)})
        status = item['properties']['status']
        if f and f['backend'] == 'gcs' and status != 'processing':
            # Process only files that are on GCS and that are not processing
            try:
                storage = GoogleCloudStorageBucket(str(item['project']))
                blob = storage.Get(f['file_path'], to_dict=False)
                # Pick file extension from original filename
                _, ext = os.path.splitext(f['filename'])
                name = _format_name(item['name'], ext[1:])
                storage.update_name(blob, name)
                try:
                    # Assign the same name to variations
                    for v in f['variations']:
                        blob = storage.Get(v['file_path'], to_dict=False)
                        name = _format_name(item['name'], v['format'], v['size'])
                        storage.update_name(blob, name)
                except KeyError:
                    pass
            except AttributeError:
                bugsnag.notify(Exception('Missing or conflicting ids detected'),
                               meta_data={'nodes_info':
                                              {'node_id': item['_id'], 'file_id': file_id}})

    # Currently we search for 'file' and 'files' keys in the object properties.
    # This could become a bit more flexible and realy on a true reference of the
    # file object type from the schema.
    if 'file' in item['properties']:
        _update_name(item, item['properties']['file'])

    elif 'files' in item['properties']:
        for f in item['properties']['files']:
            _update_name(item, f['file'])

import os
import subprocess

from flask import current_app
from application.utils.gcs import GoogleCloudStorageBucket


def get_sizedata(filepath):
    outdata = dict(
        size=int(os.stat(filepath).st_size)
    )
    return outdata


def rsync(path, remote_dir=''):
    BIN_SSH = current_app.config['BIN_SSH']
    BIN_RSYNC = current_app.config['BIN_RSYNC']

    DRY_RUN = False
    arguments = ['--verbose', '--ignore-existing', '--recursive', '--human-readable']
    logs_path = current_app.config['CDN_SYNC_LOGS']
    storage_address = current_app.config['CDN_STORAGE_ADDRESS']
    user = current_app.config['CDN_STORAGE_USER']
    rsa_key_path = current_app.config['CDN_RSA_KEY']
    known_hosts_path = current_app.config['CDN_KNOWN_HOSTS']

    if DRY_RUN:
        arguments.append('--dry-run')
    folder_arguments = list(arguments)
    if rsa_key_path:
        folder_arguments.append(
            '-e ' + BIN_SSH + ' -i ' + rsa_key_path + ' -o "StrictHostKeyChecking=no"')
    # if known_hosts_path:
    #     folder_arguments.append("-o UserKnownHostsFile " + known_hosts_path)
    folder_arguments.append("--log-file=" + logs_path + "/rsync.log")
    folder_arguments.append(path)
    folder_arguments.append(user + "@" + storage_address + ":/public/" + remote_dir)
    # print (folder_arguments)
    devnull = open(os.devnull, 'wb')
    # DEBUG CONFIG
    # print folder_arguments
    # proc = subprocess.Popen(['rsync'] + folder_arguments)
    # stdout, stderr = proc.communicate()
    subprocess.Popen(['nohup', BIN_RSYNC] + folder_arguments, stdout=devnull, stderr=devnull)


def remote_storage_sync(path):  # can be both folder and file
    if os.path.isfile(path):
        filename = os.path.split(path)[1]
        rsync(path, filename[:2] + '/')
    else:
        if os.path.exists(path):
            rsync(path)
        else:
            raise IOError('ERROR: path not found')


def push_to_storage(project_id, full_path, backend='cgs'):
    """Move a file from temporary/processing local storage to a storage endpoint.
    By default we store items in a Google Cloud Storage bucket named after the
    project id.
    """

    def push_single_file(project_id, full_path, backend):
        if backend == 'cgs':
            storage = GoogleCloudStorageBucket(project_id, subdir='_')
            blob = storage.Post(full_path)
            # XXX Make public on the fly if it's an image and small preview.
            # This should happen by reading the database (push to storage
            # should change to accomodate it).
            if blob is not None and full_path.endswith('-t.jpg'):
                blob.make_public()
            os.remove(full_path)

    if os.path.isfile(full_path):
        push_single_file(project_id, full_path, backend)
    else:
        if os.path.exists(full_path):
            for root, dirs, files in os.walk(full_path):
                for name in files:
                    push_single_file(project_id, os.path.join(root, name), backend)
        else:
            raise IOError('ERROR: path not found')

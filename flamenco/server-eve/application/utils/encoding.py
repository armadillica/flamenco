import logging
import os

from flask import current_app

from application import encoding_service_client

log = logging.getLogger(__name__)


class Encoder:
    """Generic Encoder wrapper. Provides a consistent API, independent from
    the encoding backend enabled.
    """

    @staticmethod
    def job_create(src_file):
        """Create an encoding job. Return the backend used as well as an id.
        """
        if current_app.config['ENCODING_BACKEND'] != 'zencoder' or \
                encoding_service_client is None:
            log.error('I can only work with Zencoder, check the config file.')
            return None

        if src_file['backend'] != 'gcs':
            log.error('Unable to work with storage backend %r', src_file['backend'])
            return None

        # Build the specific GCS input url, assuming the file is stored
        # in the _ subdirectory
        storage_base = "gcs://{0}/_/".format(src_file['project'])
        file_input = os.path.join(storage_base, src_file['file_path'])
        options = dict(notifications=current_app.config['ZENCODER_NOTIFICATIONS_URL'])

        outputs = [{'format': v['format'],
                    'url': os.path.join(storage_base, v['file_path'])}
                   for v in src_file['variations']]
        r = encoding_service_client.job.create(file_input,
                                               outputs=outputs,
                                               options=options)
        if r.code != 201:
            log.error('Error %i creating Zencoder job: %s', r.code, r.body)
            return None

        return {'process_id': r.body['id'],
                'backend': 'zencoder'}

    @staticmethod
    def job_progress(job_id):
        if isinstance(encoding_service_client, Zencoder):
            r = encoding_service_client.job.progress(int(job_id))
            return r.body
        else:
            return None

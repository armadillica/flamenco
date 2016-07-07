import copy
import json
import datetime
import functools
import logging

import bson.objectid
from eve import RFC1123_DATE_FORMAT
from flask import current_app
from werkzeug import exceptions as wz_exceptions


__all__ = ('remove_private_keys', 'PillarJSONEncoder')
log = logging.getLogger(__name__)


def remove_private_keys(document):
    """Removes any key that starts with an underscore, returns result as new
    dictionary.
    """
    doc_copy = copy.deepcopy(document)
    for key in list(doc_copy.keys()):
        if key.startswith('_'):
            del doc_copy[key]

    try:
        del doc_copy['allowed_methods']
    except KeyError:
        pass

    return doc_copy


class PillarJSONEncoder(json.JSONEncoder):
    """JSON encoder with support for Pillar resources."""

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.strftime(RFC1123_DATE_FORMAT)

        if isinstance(obj, bson.ObjectId):
            return str(obj)

        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


def dumps(mongo_doc, **kwargs):
    """json.dumps() for MongoDB documents."""
    return json.dumps(mongo_doc, cls=PillarJSONEncoder, **kwargs)


def jsonify(mongo_doc, status=200, headers=None):
    """JSonifies a Mongo document into a Flask response object."""
    
    return current_app.response_class(dumps(mongo_doc),
                                      mimetype='application/json',
                                      status=status,
                                      headers=headers)


def skip_when_testing(func):
    """Decorator, skips the decorated function when app.config['TESTING']"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if current_app.config['TESTING']:
            log.debug('Skipping call to %s(...) due to TESTING', func.func_name)
            return None

        return func(*args, **kwargs)
    return wrapper


def project_get_node_type(project_document, node_type_node_name):
    """Return a node_type subdocument for a project. If none is found, return
    None.
    """

    if project_document is None:
        return None

    return next((node_type for node_type in project_document['node_types']
                 if node_type['name'] == node_type_node_name), None)


def str2id(document_id):
    """Returns the document ID as ObjectID, or raises a BadRequest exception.

    :type document_id: str
    :rtype: bson.ObjectId
    :raises: wz_exceptions.BadRequest
    """

    if not document_id:
        raise wz_exceptions.BadRequest('Invalid object ID %r', document_id)

    try:
        return bson.ObjectId(document_id)
    except bson.objectid.InvalidId:
        raise wz_exceptions.BadRequest('Invalid object ID %r', document_id)

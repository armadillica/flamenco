import copy
import json
import datetime

import bson
from eve import RFC1123_DATE_FORMAT
from flask import current_app

__all__ = ('remove_private_keys', 'PillarJSONEncoder')


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

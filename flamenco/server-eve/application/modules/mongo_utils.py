"""Utility functions for MongoDB stuff."""

from bson import ObjectId
from flask import current_app
from werkzeug.exceptions import NotFound


def find_one_or_404(collection_name, object_id):
    """Returns the found object from the collection, or raises a NotFound exception.

    :param collection_name: name of the collection, such as 'users' or 'files'
    :type collection_name: str
    :param object_id: ID of the object to find.
    :type object_id: str or bson.ObjectId
    :returns: the found object
    :rtype: dict

    :raises: werkzeug.exceptions.NotFound
    """

    collection = current_app.data.driver.db[collection_name]
    found = collection.find_one(ObjectId(object_id))

    if found is None:
        raise NotFound()

    return found

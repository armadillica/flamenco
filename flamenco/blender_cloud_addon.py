import typing

import flask
import werkzeug.exceptions as wz_exceptions


def requested_by_version() -> typing.Optional[typing.Tuple[int, int, int]]:
    """Determine the version of the Blender Cloud add-on.

    The version of the Blender Cloud add-on performing the current request is
    returned as (major, minor, micro) tuple. If the current request did not
    come from the Blender Cloud add-on (as recognised by the
    'Blender-Cloud-Addon' HTTP header), return None.
    """
    addon_version = flask.request.headers.get('Blender-Cloud-Addon')
    if not addon_version:
        return None

    try:
        parts = tuple(int(part) for part in addon_version.split('.'))
    except ValueError:
        raise wz_exceptions.BadRequest('Invalid Blender-Cloud-Addon header')

    if 2 <= len(parts) < 4:
        return (parts + (0, 0))[:3]

    raise wz_exceptions.BadRequest('Invalid Blender-Cloud-Addon header')

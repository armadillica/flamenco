import logging

from flask import Blueprint, request, current_app, g
from eve.methods.get import get
from eve.utils import config as eve_config
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import InternalServerError

from application import utils
from application.utils.authorization import require_login

TL_PROJECTION = utils.dumps({'name': 1, 'url': 1, 'permissions': 1,})
TL_SORT = utils.dumps([('name', 1)])

TEXTURE_LIBRARY_QUERY_ARGS = {
    eve_config.QUERY_PROJECTION: TL_PROJECTION,
    eve_config.QUERY_SORT: TL_SORT,
    'max_results': 'null',  # this needs to be there, or we get a KeyError.
}

blueprint = Blueprint('blender_cloud.texture_libs', __name__)
log = logging.getLogger(__name__)


def keep_fetching_texture_libraries(proj_filter):

    groups = g.current_user['groups']
    user_id = g.current_user['user_id']

    page = 1
    max_page = float('inf')

    while page <= max_page:
        request.args.setlist(eve_config.QUERY_PAGE, [page])

        result, _, _, status, _ = get(
            'projects',
            {'$or': [
                {'user': user_id},
                {'permissions.groups.group': {'$in': groups}},
                {'permissions.world': 'GET'}
            ]})

        if status != 200:
            log.warning('Error fetching texture libraries: %s', result)
            raise InternalServerError('Error fetching texture libraries')

        for proj in result['_items']:
            if proj_filter(proj):
                yield proj

        # Compute the last page number we should query.
        meta = result['_meta']
        max_page = meta['total'] // meta['max_results']
        if meta['total'] % meta['max_results'] > 0:
            max_page += 1

        page += 1


@blueprint.route('/texture-libraries')
@require_login()
def texture_libraries():
    # Use Eve method so that we get filtering on permissions for free.
    # This gives all the projects that contain the required node types.

    request.args = MultiDict(request.args)   # allow changes; it's an ImmutableMultiDict by default.
    request.args.setlist(eve_config.QUERY_PROJECTION, [TL_PROJECTION])
    request.args.setlist(eve_config.QUERY_SORT, [TL_SORT])

    # Construct eve-like response.
    projects = list(keep_fetching_texture_libraries(has_texture_node))
    result = {'_items': projects,
              '_meta': {
                  'max_results': len(projects),
                  'page': 1,
                  'total': len(projects),
              }}

    return utils.jsonify(result)


def has_texture_node(proj):
    """Returns True iff the project has a top-level (group)texture node."""

    nodes_collection = current_app.data.driver.db['nodes']

    count = nodes_collection.count(
        {'node_type': 'group_texture',
         'project': proj['_id'],
         'parent': None})
    return count > 0


def setup_app(app, url_prefix):
    app.register_blueprint(blueprint, url_prefix=url_prefix)

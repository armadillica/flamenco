# -*- encoding: utf-8 -*-

import itertools
import logging

from flamenco.node_types.shot import node_type_shot, human_readable_properties
from pillar.api.nodes import only_for_node_type_decorator
import pillar.api.activities
import pillar.api.utils.authentication
import pillar.api.utils
import pillar.web.jinja

log = logging.getLogger(__name__)
only_for_shot = only_for_node_type_decorator(node_type_shot['name'])


def register_shot_activity(shot, descr):
    user_id = pillar.api.utils.authentication.current_user_id()
    pillar.api.activities.register_activity(
        user_id,
        descr,
        'node', shot['_id'],
        'project', shot['project'],
        shot['project'],
        node_type=shot['node_type'],
    )


@only_for_shot
def activity_after_replacing_shot(shot, original):
    """
    Note: this is also used on PATCH, since our custom shot PATCH handler
    performs a PUT-internal to run the patched node through Eve for
    validation.
    """

    # Compare to original, and either mention the things that changed,
    # or (if they are equal) don't log an activity at all.
    changes = list(itertools.islice(pillar.api.utils.doc_diff(shot, original), 2))
    if not changes:
        log.info('Not registering replacement of shot %s, as it is identical '
                 'in non-private fields.', shot['_id'])
        return

    if len(changes) == 1:
        (key, val_shot, _) = changes[0]
        try:
            human_key = human_readable_properties[key]
        except KeyError:
            human_key = pillar.web.jinja.format_undertitle(key.rsplit('.', 1)[-1])
        descr = None

        # Some key- and value-specific overrides
        if val_shot is pillar.api.utils.DoesNotExist:
            descr = 'removed "%s" from shot "%s"' % (human_key, shot['name'])
        if key == 'picture':
            descr = 'changed the thumbnail of shot "%s"' % shot['name']
        elif key == 'properties.status':
            val_shot = pillar.web.jinja.format_undertitle(val_shot)
        elif isinstance(val_shot, basestring) and len(val_shot) > 80:
            val_shot = val_shot[:80] + u'…'

        if descr is None:
            descr = 'changed "%s" to "%s" in shot "%s"' %\
                    (human_key, val_shot, shot['name'])
    else:
        descr = 'edited shot "%s"' % shot['name']

    register_shot_activity(shot, descr)


@only_for_shot
def activity_after_creating_shot(shot):
    register_shot_activity(shot, 'created a new shot "%s"' % shot['name'])


def activity_after_creating_shots(nodes):
    for node in nodes:
        activity_after_creating_shot(node)


@only_for_shot
def set_default_used_in_edit(shot):
    """Ensures that used_in_edit is always set."""
    shot.setdefault('properties', {}).setdefault('used_in_edit', True)


def nodes_set_default_used_in_edit(nodes):
    for node in nodes:
        set_default_used_in_edit(node)


@only_for_shot
def activity_after_deleting_shot(shot):
    register_shot_activity(shot, 'deleted shot "%s"' % shot['name'])


def setup_app(app):
    app.on_replaced_nodes += activity_after_replacing_shot
    app.on_insert_nodes += nodes_set_default_used_in_edit
    app.on_inserted_nodes += activity_after_creating_shots
    app.on_deleted_item_nodes += activity_after_deleting_shot
    app.on_deleted_resource_nodes += activity_after_deleting_shot

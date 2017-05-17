import logging

import werkzeug.exceptions as wz_exceptions

from pillar.api.utils.authentication import current_user_id

from flamenco import current_flamenco

log = logging.getLogger(__name__)


def check_permission_fetch(doc: dict, *, doc_name: str):
    """Checks permissions on the given task/job/anything with 'project' and 'manager' fields."""

    if current_flamenco.manager_manager.user_manages(mngr_doc_id=doc.get('manager')):
        # Managers can re-fetch their own tasks/jobs to validate their local cache.
        return

    project_id = doc.get('project')
    if not project_id:
        log.warning('Denying user %s GET access to %s %s because it has no "project" field',
                    current_user_id(), doc_name, doc.get('_id'))
        raise wz_exceptions.Forbidden()

    auth = current_flamenco.auth
    if auth.current_user_may(auth.Actions.VIEW, project_id):
        return

    raise wz_exceptions.Forbidden()

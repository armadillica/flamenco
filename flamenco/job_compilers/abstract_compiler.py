import abc
import typing

import attr
import bson
from pillar import attrs_extra


@attr.s
class AbstractJobCompiler(object, metaclass=abc.ABCMeta):
    task_manager = attr.ib(cmp=False, hash=False)
    job_manager = attr.ib(cmp=False, hash=False)
    _log = attrs_extra.log('%s.AbstractJobCompiler' % __name__)

    REQUIRED_SETTINGS = []  # type: typing.List[str]

    def compile(self, job: dict):
        """Compiles the job into a list of tasks.

        Calls self.task_manager.create_task(...) to create the task in the database.
        """

        if not isinstance(job.get('_id'), bson.ObjectId):
            raise TypeError("job['_id'] should be an ObjectId, not %s" % job.get('_id'))

        if not isinstance(job, dict):
            raise TypeError('job should be a dict, not %s' % type(job))

        self._compile(job)
        self._flip_status(job)

    @abc.abstractmethod
    def _compile(self, job: dict):
        """Compiles the job into a list of tasks.

        Implement this in a subclass. Ensure that self._create_task(...) is used to create the
        tasks. This is important to prevent race conditions between job compilation and the Manager
        fetching tasks.
        """

    def _flip_status(self, job: dict):
        """Flips the job & tasks status from 'under-construction' to 'queued'."""

        import datetime
        from bson import tz_util

        # Flip all tasks for this job from 'under-construction' to 'queued', and do the same
        # with the job. This must all happen using a single '_updated' timestamp to prevent
        # race conditions.
        now = datetime.datetime.now(tz=tz_util.utc)

        # handle 'start paused' flag
        if job.get('start_paused', False):
            new_status = 'paused'
        else:
            new_status = 'queued'

        self.task_manager.api_set_task_status_for_job(
            job['_id'], 'under-construction', new_status, now=now)
        self.job_manager.api_set_job_status(job['_id'], new_status, now=now)

    def _create_task(self, job: dict, commands, name, task_type, status='under-construction',
                     **kwargs) -> bson.ObjectId:
        """Creates an under-construction task.

        Use this to construct tasks, rather than calling self.task_manager.api_create_task directly.
        This is important to prevent race conditions between job compilation and the Manager
        fetching tasks.
        """

        return self.task_manager.api_create_task(job, commands, name,
                                                 task_type=task_type,
                                                 status=status,
                                                 **kwargs)

    def validate_job_settings(self, job: dict):
        """Raises an exception if required settings are missing.

        :raises: flamenco.exceptions.JobSettingError
        """

        if not isinstance(job, dict):
            raise TypeError('job should be a dict, not %s' % type(job))

        job_settings = job['settings']

        missing = [key for key in self.REQUIRED_SETTINGS
                   if key not in job_settings]

        if not missing:
            return

        from flamenco import exceptions
        job_id = job.get('_id') or ''
        if job_id:
            job_id = ' %s' % job_id
        if len(missing) == 1:
            setting = 'setting'
        else:
            setting = 'settings'

        raise exceptions.JobSettingError(
            'Job%s is missing required %s: %s' % (job_id, setting, ', '.join(missing)))

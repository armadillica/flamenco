import attr
from pillar import attrs_extra


@attr.s
class AbstractJobCompiler(object):
    task_manager = attr.ib(cmp=False, hash=False)
    _log = attrs_extra.log('%s.AbstractJobType' % __name__)

    REQUIRED_SETTINGS = []

    def compile(self, job):
        """Compiles the job into a list of tasks.

        Calls self.task_manager.create_task(...) to create the task in the database.
        """
        raise NotImplementedError()

    def validate_job_settings(self, job):
        """Raises an exception if required settings are missing.

        :raises: flamenco.exceptions.JobSettingError
        """
        from pillarsdk import Resource

        job_settings = job['settings']
        if isinstance(job_settings, Resource):
            job_settings = job_settings.to_dict()

        missing = [key for key in self.REQUIRED_SETTINGS
                   if key not in job_settings]

        if not missing:
            return

        from flamenco import exceptions
        job_id = job.get('_id', '')
        if job_id:
            job_id = ' ' + job_id
        if len(missing) == 1:
            setting = 'setting'
        else:
            setting = 'settings'

        raise exceptions.JobSettingError(
            'Job%s is missing required %s: %s' % (job_id, setting, ', '.join(missing)))

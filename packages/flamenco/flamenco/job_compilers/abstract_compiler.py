import attr
from pillar import attrs_extra


@attr.s
class AbstractJobCompiler(object):
    task_manager = attr.ib(cmp=False, hash=False)
    _log = attrs_extra.log('%s.AbstractJobType' % __name__)

    def compile(self, job):
        """Compiles the job into a list of tasks.

        Calls self.task_manager.create_task(...) to create the task in the database.
        """
        raise NotImplementedError()

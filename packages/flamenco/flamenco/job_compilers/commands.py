import attr


@attr.s
class AbstractCommand(object):
    """Abstract Flamenco command.

    Command settings are defined in subclasses using attr.ib().
    """

    @classmethod
    def cmdname(cls):
        """Returns the command name."""
        return cls.__name__.lower()

    def to_dict(self):
        """Returns a dictionary representation of this command, for JSON serialisation."""

        return {
            u'name': self.cmdname(),
            u'settings': attr.asdict(self),
        }


@attr.s
class Sleep(AbstractCommand):
    time_in_seconds = attr.ib(validator=attr.validators.instance_of(int))


@attr.s
class Echo(AbstractCommand):
    message = attr.ib(validator=attr.validators.instance_of(unicode))

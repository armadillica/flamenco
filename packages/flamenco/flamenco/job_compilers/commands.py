import attr


@attr.s
class AbstractCommand(object):
    """Abstract Flamenco command.

    Command settings are defined in subclasses using attr.ib().
    """

    @classmethod
    def cmdname(cls):
        """Returns the command name."""
        from flamenco.utils import camel_case_to_lower_case_underscore

        return camel_case_to_lower_case_underscore(cls.__name__)

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


@attr.s
class BlenderRender(AbstractCommand):
    # Blender executable to run.
    blender_cmd = attr.ib(validator=attr.validators.instance_of(unicode))
    # blend file path.
    filepath = attr.ib(validator=attr.validators.instance_of(unicode))
    # output format.
    format = attr.ib(validator=attr.validators.optional(attr.validators.instance_of(unicode)))
    # output file path, defaults to the path in the blend file itself.
    render_output = attr.ib(
        validator=attr.validators.optional(attr.validators.instance_of(unicode)))

    # list of frames to render, as frame range string.
    frames = attr.ib(validator=attr.validators.instance_of(unicode))

import datetime


class tzutc(datetime.tzinfo):
    """tzinfo subclass for UTC time."""

    def utcoffset(self, dt):
        return datetime.timedelta(0)

    def dst(self, dt):
        return datetime.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def is_ambiguous(self, dt):
        return False

    def __eq__(self, other):
        if not isinstance(other, tzutc):
            return NotImplemented

        return True

    __hash__ = None

    def __ne__(self, other):
        return not (self == other)

    def __repr__(self):
        return "%s()" % self.__class__.__name__

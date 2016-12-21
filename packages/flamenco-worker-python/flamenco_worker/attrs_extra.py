"""Extra functionality for attrs."""

import logging

import attr


def log(name):
    """Returns a logger attr.ib

    :param name: name to pass to logging.getLogger()
    :rtype: attr.ib
    """
    return attr.ib(default=logging.getLogger(name),
                   repr=False,
                   hash=False,
                   cmp=False)

#!/usr/bin/env python

"""Setup file for the Flamenco extension."""

import setuptools

setuptools.setup(
    name='flamenco',
    version='2.1',
    packages=setuptools.find_packages('.', exclude=['test']),
    install_requires=[],
    tests_require=[
        'pytest>=2.9.1',
        'responses>=0.5.1',
        'pytest-cov>=2.2.1',
        'mock>=2.0.0',
    ],
    zip_safe=False,
)

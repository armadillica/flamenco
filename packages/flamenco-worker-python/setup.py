#!/usr/bin/env python

import setuptools

if __name__ == '__main__':
    setuptools.setup(
        name='flamenco-worker',
        version='2.0-beta10',
        description='Flamenco Worker implementation',
        author='Sybren A. Stüvel',
        author_email='sybren@blender.studio',
        packages=setuptools.find_packages(),
        license='GPL',
        classifiers=[
            'Operating System :: OS Independent',
            'Programming Language :: Python',
            'Programming Language :: Python :: 3.5',
        ],
        package_data={'flamenco_worker': ['merge-exr.blend']},
        install_requires=[
            'attrs >=16.3.0',
            'requests>=2.12.4',
        ],
        entry_points={'console_scripts': [
            'flamenco-worker = flamenco_worker.cli:main',
        ]},
        zip_safe=False,  # due to the bundled merge-exr.blend file.
    )

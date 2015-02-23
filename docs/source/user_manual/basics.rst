.. _basics:

******
Basics
******

.. _installing:

Installing brender
==================

There are two ways to install brender: the first one, recommended for
final users, is using the installer (which does not exist yet). It's
basically a package containing all the dependencies needed by brender
to make it run out of the box.
The second way is the development one, that involves making a python 
virtual environament and istalling the dependencies manually.

Brender is currently not ready for deployment, we are still working on it!

.. _configuring:

Configuring brender
===================

To install brender, create a virtual environment and install the content of
requirements.txt. In order to run the server, navigate to the server directory
and type::

    python manage.py runserver

To run the dashboard, we need to run (one level above the server directory)::

    python brender.py dashboard

And finally, to run the woker::

    python brender.py worker


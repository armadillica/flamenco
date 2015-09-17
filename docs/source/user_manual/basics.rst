
******
Basics
******

.. _installing:

Getting Started with Flamenco
===================

Flamenco is a Network Renderer for Blender that can leverage Cycles and GPU rendering.

There are five components to know about when working with Flamenco.  Four of the components are server-side services that run outside of Blender.
The fifth component is a Blender Add-on that you run in the instance of Blender that you have designed your animation on.

Flamenco has also been designed to work on multiple networks.  This allows you to have multiple datacenter render farms (potentially a combination of real or cloud providers).

So there is a use case for running a render farm in one location, and a different use case for running a render farm in multiple locations.  I'll explain the components below
and which ones you need for the specific situation.  

Here is a brief description of the list of the components:

- Worker
	The 'Worker' is the one service that you run on all of the computers that you wish to have in your render farm.
	This can include your main server computer as well.  The remaining components below are only needed on your main server.

- Manager
	The 'Manager' is the component that listens on port 7777.  The 'Manager' is what the 'Workers' connect to get the jobs that they has been assigned.
	You need to run the 'Manager' in each Network that you have.

- Server
	The 'Server' is the component that listens on port 9999.  You only need one of these.  Run this component on your main render farm server.  All of the 'Managers'
	talk to this component.

- Dashboard
	The 'Dashboard' is the component that listens on port 8888.  You only need one of these.  This is the web interface that you use to manage all of the Jobs.

- Add-on:  render_flamenco.py
	This Blender addon runs on the instance of Blender that you created your animation on.  This Add-on connects to your one 'Server' instance.  This Add-on is how
	we submit a job to the render farm.


Use case 1:  Running Flamenco in one network
	This is what I use, where I am running a Flamenco render farm just inside my home.

	Main computer:
		The main computer runs all 5 components.  It acts as the main server and it renders jobs as well.

	Slave computers:
		These components only run the 'Worker' component.


Use case 2:  Running Flamenco on multiple networks
		On your main Network you need to run the 'Server', and 'Dashboard' components at a minimum on a single computer.  (Actually you could separate these as well if you want).

		But in your overall design, you only need one 'Dashboard' and one 'Server' to control the render farm.

		Now when you have a network that you want to have any rendering happening, now you need one 'Manager' on that network.  Then any 'Workers' connect to that 'Manger'.


.. _installing:

Getting Started with Flamenco
-----------------------------

Flamenco is a Network Renderer for Blender that can leverage Cycles and GPU rendering.

There are five main components to know about when working with Flamenco. Four of the components are server-side services that run outside of Blender.
The fifth component is a Blender Add-on and this is used to send an animation to the render farm.

All Flamenco components can run on Windows, OS X, and Linux.

Flamenco has also been designed to work on a single network or multiple networks. There are two major use cases; running a render farm in one physical location, and running a render farm in multiple physical locations. 
Which components are needed differ based on the use case, and that information is explained below. 

Flamenco components
-------------------

- **Worker**
	The 'Worker' is the one service that is ran on all of the computers that will do any rendering. This can include the main server computer as well. 

- **Manager**
	The 'Manager' is the component that listens on port 7777. The 'Manager' is what the 'Workers' connect to in order to get the jobs that they have been assigned.
	One 'Manager' is needed for each network in the render farm.

- **Server**
	The 'Server' is the component that listens on port 9999. Only one 'Server' total is needed. Run this component on the main render farm server. All of the 'Managers'
	talk to this component.

- **Dashboard**
	The 'Dashboard' is the component that listens on port 8888. Only one 'Dashboard' is needed. This is the web interface that is used to manage all of the Jobs.

- **Add-on: render_flamenco.py**
	This Blender Add-on runs on the instance of Blender that the animation was created on and it connects to the single 'Server'. This is used to send a job to the render farm.


Network Architecture Use cases
------------------------------

**Use case 1: Running Flamenco on one network**
	This use case is for a either a single home render farm or a render farm in a single datacenter.

	**Main computer:**
		The main computer runs all 5 components. It acts as the main server and it renders jobs as well.

	**Worker computers:**
		These components only run the 'Worker' component.


**Use case 2: Running Flamenco on multiple networks**
		On the main network the 'Server', and 'Dashboard' components are needed at a minimum.

		On any other networks that will be running 'Workers', one 'Manager' is needed and any 'Workers' connect to that 'Manger'.

# Installation

Flamenco is still under development, therefore this installation guide is rather technical.
In the future it will be a straightforward process, in two variants.

## Using the cloud.blender.org Server
**Note: This feature is not yet available**

In this case, only two components of the stack are controlled by the user: Manager and 
Workers. The setup:

- On Blender Cloud: create and initialize a Project to be used with Flamenco
- On Blender Cloud: Create a Manager (and collect the identification token)
- Download the Manager binary, add the identification token to the configuration, start 
the Manager (it will automatically connect with Blender Cloud)
- Download the Worker bundle and start it (it will automatically connect with the Manager)

## Using a self-provisioned Server
**Note: This feature is not yet available**

- Download and start the server (using Docker)
- Follow the steps for setting up with Blender Cloud, updating the configuration to point
to the self-provisioned Server, rather than cloud.blender.org

# Roadmap
The day-to-day planning for development is available on 
[developer.blender.org](https://developer.blender.org/project/board/58/). In this section we summarize
the high level goals for the projects.

## Self-provisionable Server
Make it possible for developers to run the full stack (Server, Manager and Worker) in a local 
environment. While this is easy to do for Manager and Worker, the challenge is to get the
Server (and its Pillar core) disconnected from Blender Cloud.

## Pre-built packages
Provide pre-built and easily installable components for regular user. Packaging will vary depending
on the component:

- Server: Python package (pip installable)
- Manager: Standalone platform-dependent binary
- Worker: Python package (possibly standalone)

## Complete Server API docs
To make it easy to implement own manager.

## More features
Resumable jobs, job callbacks, resource allocation, filtering.
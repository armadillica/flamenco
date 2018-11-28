# Installation & Configuration

This guide focuses on installing Flamenco while relying on the
[Blender Cloud](https://cloud.blender.org/) service. If you are interested in setting up the entire
Flamenco stack on your own infrastructure, you should check out the developer docs, as well as the
source code.

We are going to assume that you have a Blender Cloud subscription, and that you already created a
project. If you haven't, log in and create a [new project](https://cloud.blender.org/p/).

Here is an overview of the steps required to get Flamenco up an running.

- Download and install [Blender](https://www.blender.org/), either on each Worker separately or on a
  shared storage. Make sure the path is the same on each Worker.
- Download and configure your Manager
- Download and configure your Worker
- Enable your project for Flamenco
- Configure the Blender Cloud Add-on and start rendering

!!! note
    On Windows, make sure you use mapped drives, so do **not** use `\\SERVER` directly. Instead, map
    it to a drive letter and use that. Furthermore, **use forward slashes**, so `S:/some/path`.

This is meant as a step-by-step quick install guide. For more in-depth installation and
configuration documents, check out the `README.md` files and sources of each component.


## Flamenco Manager

Flamenco Manager is one of the components that you are responsible fur running on your
infrastructure (or on your local machine). The Manager handles the communication between your
Workers, which you also run locally, and the Server, which runs on the
[cloud.blender.org](https://cloud.blender.org) website.


### Manager installation

To run Flamenco Manager for the first time, follow these steps:

0. Optionally install [ImageMagick](https://www.imagemagick.org/script/download.php), if you want to
   show the latest rendered image in the Manager's dashboard, and make sure that the `convert`
   command can be found on `$PATH`. Since there are multiple builds of ImageMagick available, make
   sure you install the version that is compatible with your render output; for example, get a
   HDR-enabled build if you render to HDR EXR files.
1. Download [Flamenco Manager](https://www.flamenco.io/download/) for your platform.
2. Extract the downloaded file.
3. Run `./flamenco-manager -setup` (Linux/macOS) or `flamenco-manager.exe -setup` (Windows).
4. Flamenco Manager will give you a list of URLs at which it can be reached. Open the URL that is
   reachable both for you and the workers.
5. Link Flamenco Manager to Blender Cloud by following the steps in the web interface.
6. Configure Flamenco Manager via the web interface; details are described below.
7. Once you have completed configuration, save the configuration, then restart Flamenco Manager
   through the web interface. It will now run in normal (i.e. non-setup) mode.

!!! note
    Flamenco Manager uses coloured output for its logging. On Windows by default these colours
    will not be shown, and instead it will show the control codes literally. This can be solved
    by adding one key to the Registry, as [described in this answer on Stack Overflow](https://stackoverflow.com/a/16799175/875379).


### Manager configuration

Flamenco Manager can be configured via the web interface. Update the variables and path replacement
variables for your render farm. The `blender` and `ffmpeg` variables should point to respectively
the Blender and FFmpeg executables where they can be found *on the workers*. If the path contains a
space, it should be enclosed in double quotes. Example:

    variables:
        blender:
            darwin: /Applications/blender-2.80/blender.app/Contents/MacOS/blender
            linux: /home/sybren/bin/blender
            windows: "C:/Program Files/Blender Foundation/Blender-2.80/blender.exe" --factory-startup
        ffmpeg:
            windows: "C:/Program Files/FFmpeg/ffmpeg.exe"
            linux: /usr/bin/ffmpeg
            darwin: /usr/bin/ffmpeg

!!! note
    We recommend using forward slashes everywhere, also on Windows.


The **path replacement variables** allow you to run different platforms, e.g. use a Windows desktop
to create render jobs, and render them on Linux workers, or vice versa. For example, you can declare
that "`/shared/flamencofiles` on Linux is `E:/flamencofiles` on Windows and
`/Volumes/Shared/flamencofiles` on MacOS" like this:

    path_replacement:
        flamencofiles:
            linux: /shared/flamencofiles
            windows: E:/flamencofiles
            darwin: /Volumes/Shared/flamencofiles

When creating a render job for `/shared/flamencofiles/projectX/thefile.blend`, Flamenco will
internally change that to `{flamencofiles}/projectX/thefile.blend`. When sending that job to a
worker running on Windows, it'll change it to `E:/flamencofiles/projectX/thefile.blend`.

!!! note
    We recommend using forward slashes everywhere, also on Windows.

Note that `variables` and `path_replacement` share a namespace -- variable names have to be unique,
and cannot be used in both `variables` and `path_replacement` sections. If this happens, Flamenco
Manager will log the offending name, and refuse to start.


### Linking the Manager to a Server

To tell the Manager which Server to use, and to let the Server know that this Manager is available,
you have to **link your Manager**. This can be done by starting Flamenco Manager in setup mode
(i.e. run `flamenco-manager -setup`) and visiting the web interface. There you can provide the
Server URL (typically https://cloud.blender.org/) and click on the Link button. Follow the
on-screen instructions to complete the link.


## Enable project for Flamenco

You can enable for Flamenco any Blender Cloud project you are part of, by going to the main project
view (the homepage of a project), clicking on "Edit Project" and then "Flamenco". Alternatively,
you can visit the url `https://cloud.blender.org/p/<your_project_url>/edit/flamenco`.
Once in the Flamenco page, click on "Enable for Flamenco". After clicking, some things will happen:

- You will be able to see your project in [Flamenco](https://cloud.blender.org/flamenco/), where you
  will manage jobs and tasks.
- A Flamenco Manager will be attached to the project.


## Flamenco Worker

Flamenco Workers are in charge of executing tasks they fetch from the Manager. Workers are written
in Python 3.5, so they will run on any system that supports Python 3.5 or newer.


### Worker installation and configuration

1. Download and unzip the [latest version of the Worker](https://www.flamenco.io/download/) and
   extract it.
2. If you're upgrading from a previous installation: copy `flamenco-worker.cfg` and
  `flamenco-worker.db` to the newly extracted directoy.
3. Run `./flamenco-worker` (macOS and Linux) or `flamenco-worker.exe` (Windows)

All configuration keys should be placed in the `[flamenco-worker]` section of the config file.
Take a look at:

- `manager_url`: Flamenco Manager URL. Leave empty to use UPnP/SSDP to find the Manager on your
  network automatically.
- `task_types`: Space-separated list of task types this worker may execute.
- `task_update_queue_db`: filename of the SQLite3 database, holding the queue of task updates to be
  sent to the Master. If this file does not exist yet, Flamenco Manager will create it.
- `args` in the `[handler_file]` section, to configure where the logs are stored.

Run the Worker with the `flamenco-worker` command. The Worker will automatically connect to the
Manager, negotiate a worker ID and password, and start querying for tasks. The worker ID and
password will be stored in `$HOME/.flamenco-worker.cfg`.


## Video Encoding of Image Sequences

**Requires Flamenco Manager and Worker version 2.2 or newer.**

A Blender Render job can optionally create a video from an image sequence. This allows you to render
as an image sequence (allowing each worker to render one or more frames), and as a final step
combine those images into a video for easier viewing. However, since this requires FFmpeg, this step
is optional and by default Flamenco Server will **not** generate this video creation task. To enable
this, follow these steps:

- Decide which of your Workers will run the video encoding tasks. This could be all Workers, or one
  or more dedicated machines.
- On those workers, update the `flamenco_worker.cfg` file to have `video-encoding` in the
  `task_types` setting. For example:

        task_types = sleep blender-render file-management exr-merge video-encoding

- Download and install [FFmpeg](https://ffmpeg.org/), either on each Worker separately or on a
  shared storage. Make sure the path is the same on each Worker.
- Add an `ffmpeg` variable to your Manager's `flamenco_manager.yaml` configuration file, which
  should point to the path where the Workers can find the `ffmpeg` binary. For example:

        variables:
            blender:
                darwin: /Applications/blender-2.80/blender.app/Contents/MacOS/blender
                linux: /home/sybren/bin/blender
                windows: "C:/Program Files/Blender Foundation/Blender-2.80/blender.exe" --factory-startup
            ffmpeg:
                windows: "C:/Program Files/FFmpeg/ffmpeg.exe"
                linux: /usr/bin/ffmpeg
                darwin: /usr/bin/ffmpeg
- Restart Flamenco Manager and your Workers to activate the change in configuration.
- Upgrade your [Blender Cloud add-on](https://cloud.blender.org/services) to version 1.9.5 or newer
  (not yet released at the moment of writing.)

Once these steps have been performed, you can check
[your Manager configuration on Blender Cloud](https://cloud.blender.org/flamenco/managers/). Look at
the Task Types, and double-check that it shows `video-encoding` in the list. Once that is there,
new Simple Blender Render jobs will automatically use FFmpeg to create videos from file sequences.


!!!note
    We highly recommend ensuring you have exactly the same version of FFmpeg on each worker.

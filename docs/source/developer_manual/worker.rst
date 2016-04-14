.. _worker:


************
Worker Setup
************

There is a number of ways to set up a Flamenco worker. We are going to consider
the specific instance of getting a Blender render node.

Simple worker (Linux)
=====================

Setting up a simple worker would require the following configuration:

* python 2.7 with requests library
* blender package
* `libglu` and and `libxi6` libraries

The libraries can be installed with::

    sudo apt-get install libglu1-mesa libxi6

Once the node is setup, we run the manager run.py script and wait for a response
from the manager, which will provide a link to download.

Shared resources
================

In case the job files are large (2+GiB), we can avoid long transfer times by
mounting a shared drive with the workers, which will be able to read the file
directly.


Run a Blender instance inside of a byobu session.

Compute Engine setup
====================

Ubuntu 14.04
------------

We need to mount the resources disk (with software and file to render).::

    sudo mkdir /mnt/render
    sudo mkdir /mnt/render-output

We if our disk is labeled `render-base`, then it will be available with a
`google-` prefix.::

    sudo mount -o discard,defaults /dev/disk/by-id/google-render-base /mnt/render
    sudo chmod a+w /mnt/render
    sudo chmod a+w /mnt/render-output
    echo '/dev/disk/by-id/google-render-base /mnt/render ext4 discard,defaults 1 1' | sudo tee -a /etc/fstab

GCS Fuse setup
--------------

In order to mount a large storage (a GCS bucket) we need to get `gcsfuse` running.
Taken from gcsfuse docs.


1.  Add the gcsfuse distribution URL as a package source and import its public
    key::

        export GCSFUSE_REPO=gcsfuse-`lsb_release -c -s`
        echo "deb http://packages.cloud.google.com/apt $GCSFUSE_REPO main" | sudo tee /etc/apt/sources.list.d/gcsfuse.list
        curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo apt-key add -

2.  Update the list of packages available and install gcsfuse.::

        sudo apt-get update
        sudo apt-get install gcsfuse

3.  (**Ubuntu before wily only**) Add yourself to the `fuse` group, then log
    out and back in::

        sudo usermod -a -G fuse $USER
        exit


Connect GCS bucket
------------------

    gcsfuse render-storage /mnt/render-output


Blender command example
-----------------------

    /mnt/render/data/bin/blender-pano-experiments/blender \
    --enable-autoexec -noaudio --background \
    /mnt/render/data/file/01_01_A.lighting.vr/01_01_A.lighting.vr.blend  \
    --render-output /mnt/render-output \
    --render-format EXR \
    -f 760 \
    -- \
    --cycles-resumable-num-chunks 1 \
    --cycles-resumable-current-chunk 2
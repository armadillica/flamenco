# Shaman File Server

The Shaman File Server is a component of Flamenco Manager that manages the files for render jobs. It accepts uploaded files via HTTP, and stores them based on their SHA256-sum and their file length. It can recreate directory structures by symlinking those files. Shaman is intended to complement [Blender Asset Tracer (BAT)](https://developer.blender.org/source/blender-asset-tracer/).

From the user's perspective, it works as follows:

- Blender Cloud add-on creates a render job at Flamenco Server.
- Blender Cloud add-on computes SHA256-sums of the files in a BAT-pack, and sends the list of files to `shaman://flamenco.manager/`.
- Flamenco Manager responds with a list of unknown files.
- Blender Cloud add-on uploads the unknown files.
- Flamenco Manager creates a *checkout* of those files, by symlinking all the files from its storage to the checkout directory.
- Blender Cloud add-on lets Flamenco Server know the files are in place and queues the job.

After this process, the checkout directory contains symlinks to all the files in the Checkout
Definition File. **The user only had to upload new and changed files.**

## More detail

In more detail, the following steps are performed:

1. User creates a set of files.
- User creates a Checkout Definition File (CDF), consisting of the SHA256-sums, file sizes, and file paths.
- User sends the CDF to Shaman for inspection.
- Shaman replies which files still need uploading.
- User sends those files.
- User sends the CDF to Shaman and requests a checkout with a certain ID.
- Shaman creates the checkout by symlinking the files listed in the CDF.
- Shaman responds with the directory the checkout was created in.

All the above steps are performed by [BAT](https://developer.blender.org/source/blender-asset-tracer/) when packing to a `shaman://` or `shaman+http://` URL.

## File Store Structure

The Shaman file store is structured as follows:

    shaman-store/
        .. uploading/
            .. /{checksum[0:2]}/{checksum[2:]}/{filesize}-{unique-suffix}.tmp
        .. stored/
            .. /{checksum[0:2]}/{checksum[2:]}/{filesize}.blob

When a file is uploaded, it goes through several stages:

- Uploading: the file is being streamed over HTTP and in the process of
  being stored to disk. The `{checksum}` and `{filesize}` fields are
  as given by the user. While the file is being streamed to disk the
  SHA256 hash is calculated. After upload is complete the user-provided
  checksum and file size are compared to the SHA256 hash and actual size.
  If these differ, the file is rejected.
- Stored: after uploading is complete, the file is stored in the `stored`
  directory. Here the `{checksum}` and `{filesize}` fields can be assumed
  to be correct.

## Garbage Collection

To prevent infinite growth of the File Store, the Shaman will periodically
perform a garbage collection sweep. Garbage Collection can be configured by
setting the following settings in `shaman.yaml`:

- `garbageCollect.period`: this is the sleep time between garbage collector
  sweeps. Default is `8h`. Set to `0` to disable garbage collection.
- `garbageCollect.maxAge`: files that are newer than this age are not
  considered for garbage collection. Default is `744h` or 31 days.
- `garbageCollect.extraCheckoutPaths`: list of directories to include when
  searching for symlinks. Shaman will never create a checkout here.
  Default is empty.

Every time a file is symlinked into a checkout directory, it is 'touched'
(that is, its modification time is set to 'now').

Files that are not referenced in any checkout, and that have a modification
time that is older than `garbageCollectMaxAge` will be deleted.

To perform a dry run of the garbage collector, use `shaman -gc`.


## Key file generation

SHAman uses JWT with `ES256` signatures to authenticate users. The public keys of the JWT-signing authority need to be known, and are automatically downloaded from Flamenco Server by Flamenco Manager.

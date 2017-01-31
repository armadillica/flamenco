#!/usr/bin/env python

from __future__ import print_function

"""CLI command for scheduling Blender renders on Flamenco Server.

Assumes that the workers already have access to the required files.

The user_config_dir and user_data_dir functions come from
 https://github.com/ActiveState/appdirs/blob/master/appdirs.py and
 are licensed under the MIT license.
"""

import argparse
import json
import os.path
import pprint
import sys

import requests

PY2 = sys.version_info[0] == 2

if PY2:
    str = unicode
    input = raw_input
    from urlparse import urljoin
else:
    from urllib.parse import urljoin

if sys.platform.startswith('java'):
    import platform

    os_name = platform.java_ver()[3][0]
    if os_name.startswith('Windows'):  # "Windows XP", "Windows 7", etc.
        system = 'win32'
    elif os_name.startswith('Mac'):  # "Mac OS X", etc.
        system = 'darwin'
    else:  # "Linux", "SunOS", "FreeBSD", etc.
        # Setting this to "linux2" is not ideal, but only Windows or Mac
        # are actually checked for and the rest of the module expects
        # *sys.platform* style strings.
        system = 'linux2'
else:
    system = sys.platform

if system == 'win32':
    # Win32 is not supported because it requires too much fluff, and we don't use it in the studio.
    raise RuntimeError("Sorry, Windows is not supported for now.")


def find_user_id(server_url, auth_token):
    """Returns the current user ID."""

    print(15 * '=', 'User info', 15 * '=')

    url = urljoin(server_url, '/api/users/me')

    resp = requests.get(url, auth=(auth_token, ''))
    resp.raise_for_status()

    user_info = resp.json()
    print('You are logged in as %(full_name)s (%(_id)s)' % user_info)
    print()

    return user_info['_id']


def find_manager_id(server_url, auth_token):
    """Returns the manager ID.

    If the user has more than one Manager available, offers a choice.
    """

    print(15 * '=', 'Manager selection', 15 * '=')
    url = urljoin(server_url, '/api/flamenco/managers')
    resp = requests.get(url, auth=(auth_token, ''))
    resp.raise_for_status()

    managers = resp.json()['_items']
    if not managers:
        raise SystemExit('No Flamenco Managers available to your account.')

    if len(managers) == 1:
        print('One Flamenco Manager is available to you:')
        manager = managers[0]
    else:
        print('Please choose which Flamenco Manager should handle this job:')
        for idx, manager in enumerate(managers):
            print('    [%i] %s (%s)' % (idx + 1, manager['name'], manager['_id']))
        choice = input('Give index, or ENTER for the first one: ')
        if choice:
            manager = managers[int(choice) - 1]
        else:
            manager = managers[0]

    print('Using manager "%s" (%s)' % (manager['name'], manager['_id']))
    print()
    return manager['_id']


def find_project_id(server_url, auth_token):
    """Returns the project ID.

    If the user has more than one Flamenco-enabled project, offers a choice.
    """
    import json

    print(15 * '=', 'Project selection', 15 * '=')
    url = urljoin(server_url, '/api/projects')
    resp = requests.get(url,
                        params={
                            'where': json.dumps({'extension_props.flamenco': {'$exists': 1}}),
                            'projection': json.dumps({'_id': 1, 'name': 1, 'permissions': 1})
                        },
                        auth=(auth_token, ''))
    resp.raise_for_status()

    projects = resp.json()['_items']
    if not projects:
        raise SystemExit('No Flamenco Projects available to your account.')

    if len(projects) == 1:
        print('One Flamenco Project is available to you:')
        project = projects[0]
    else:
        print('Please choose which Flamenco Project this job belongs to:')
        for idx, project in enumerate(projects):
            print('    [%i] %s (%s)' % (idx + 1, project['name'], project['_id']))
        choice = input('Give index, or ENTER for the first one: ')
        if choice:
            project = projects[int(choice) - 1]
        else:
            project = projects[0]

    print('Using project "%s" (%s)' % (project['name'], project['_id']))
    print()
    return project['_id']


def create_render_job(server_url, auth_token, settings, args):
    user_id = find_user_id(server_url, auth_token)
    project_id = find_project_id(server_url, auth_token)
    manager_id = find_manager_id(server_url, auth_token)

    filename = os.path.basename(settings['filepath'])

    job = {
        u'status': u'queued',
        u'priority': 50,
        u'name': args.name or u'render %s' % filename,
        u'settings': settings,
        u'job_type': args.jobtype,
        u'user': user_id,
        u'manager': manager_id,
        u'project': project_id,
    }
    if args.description:
        job[u'description'] = args.description

    print()
    print('The job:')
    json.dump(job, sys.stdout, indent=4, sort_keys=True)

    url = urljoin(server_url, '/api/flamenco/jobs')
    print()
    print('Press [ENTER] to POST to %s' % url)
    input()

    resp = requests.post(url, json=job, auth=(auth_token, ''))
    if resp.status_code == 204:
        print('Job created.')
        print(resp.headers)
    else:
        print('Response:')
        if resp.headers['content-type'] == 'application/json':
            pprint.pprint(resp.json())
        else:
            print(resp.text)


def find_credentials():
    """Finds BlenderID credentials.

    :rtype: str
    :returns: the authentication token to use.
    """
    import glob

    # Find BlenderID profile file.
    configpath = user_config_dir('blender', 'Blender Foundation', roaming=True)
    found = glob.glob(os.path.join(configpath, '*'))
    for confpath in reversed(sorted(found)):
        profiles_path = os.path.join(confpath, 'config', 'blender_id', 'profiles.json')
        if not os.path.exists(profiles_path):
            continue

        print('Reading credentials from %s' % profiles_path)
        with open(profiles_path) as infile:
            profiles = json.load(infile, encoding='utf8')
        if profiles:
            break
    else:
        print('Unable to find Blender ID credentials. Log in with the Blender ID add-on in '
              'Blender first.')
        raise SystemExit()

    active_profile = profiles[u'active_profile']
    profile = profiles[u'profiles'][active_profile]
    print('Logging in as %s' % profile[u'username'])

    return profile[u'token']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('blendfile', help='The blendfile to render. It is assumed that a worker '
                                          'can find this file, since we do not yet have upload/'
                                          'download/copy commands.')
    parser.add_argument('frames',
                        help='Frame range to render, in "printer range" notation (1-4,15-30). '
                             'Should not contain any spaces.')
    parser.add_argument('-r', '--render-output',
                        help='Where to render to, defaults to whatever is defined in the blendfile.')
    parser.add_argument('-o', '--format',
                        help='The file format to output to, defaults to whatever is defined '
                             'in the blendfile.')
    parser.add_argument('-c', '--chunk-size',
                        help='The maximum number of frames to render on a single worker.')
    parser.add_argument('-u', '--server-url', default='https://cloud.blender.org/',
                        help='URL of the Flamenco server.')
    parser.add_argument('-t', '--token',
                        help='Authentication token to use. If not given, your token from the '
                             'Blender ID add-on is used.')
    parser.add_argument('-b', '--blender-cmd', default='{blender}',
                        help='Blender command, defaults to "{blender}".')
    parser.add_argument('-n', '--name', help='Optional job name, defaults to "render {filename}".')
    parser.add_argument('-d', '--description', help='Optional job description.')
    parser.add_argument('-p', '--progressive',
                        help='Progressive render information, '
                             'in the format "sample_count:num_chunks"')
    parser.add_argument('--jobtype', default='blender-render',
                        help='Sets the job type; set automatically when using --progressive')

    args = parser.parse_args()

    settings = {
        'filepath': args.blendfile,
        'frames': args.frames,
        'blender_cmd': args.blender_cmd,
    }

    if args.render_output:
        settings['render_output'] = args.render_output
    if args.format:
        settings['format'] = args.format
    if args.chunk_size:
        settings['chunk_size'] = int(args.chunk_size)
    if args.progressive:
        scount, nchunks = args.progressive.split(':')
        settings['cycles_sample_count'] = int(scount)
        settings['cycles_num_chunks'] = int(nchunks)
        args.jobtype = 'blender-render-progressive'
    if not args.token:
        args.token = find_credentials()

    create_render_job(args.server_url, args.token, settings, args)


def user_config_dir(appname=None, appauthor=None, version=None, roaming=False):
    r"""Return full path to the user-specific config dir for this application.
        "appname" is the name of application.
            If None, just the system directory is returned.
        "appauthor" (only used on Windows) is the name of the
            appauthor or distributing body for this application. Typically
            it is the owning company name. This falls back to appname. You may
            pass False to disable it.
        "version" is an optional version path element to append to the
            path. You might want to use this if you want multiple versions
            of your app to be able to run independently. If used, this
            would typically be "<major>.<minor>".
            Only applied when appname is present.
        "roaming" (boolean, default False) can be set True to use the Windows
            roaming appdata directory. That means that for users on a Windows
            network setup for roaming profiles, this user data will be
            sync'd on login. See
            <http://technet.microsoft.com/en-us/library/cc766489(WS.10).aspx>
            for a discussion of issues.
    Typical user config directories are:
        Mac OS X:               same as user_data_dir
        Unix:                   ~/.config/<AppName>     # or in $XDG_CONFIG_HOME, if defined
        Win *:                  same as user_data_dir
    For Unix, we follow the XDG spec and support $XDG_CONFIG_HOME.
    That means, by default "~/.config/<AppName>".
    """
    if system in {"win32", "darwin"}:
        path = user_data_dir(appname, appauthor, None, roaming)
    else:
        path = os.getenv('XDG_CONFIG_HOME', os.path.expanduser("~/.config"))
        if appname:
            path = os.path.join(path, appname)
    if appname and version:
        path = os.path.join(path, version)
    return path


def user_data_dir(appname=None, appauthor=None, version=None, roaming=False):
    r"""Return full path to the user-specific data dir for this application.
        "appname" is the name of application.
            If None, just the system directory is returned.
        "appauthor" (only used on Windows) is the name of the
            appauthor or distributing body for this application. Typically
            it is the owning company name. This falls back to appname. You may
            pass False to disable it.
        "version" is an optional version path element to append to the
            path. You might want to use this if you want multiple versions
            of your app to be able to run independently. If used, this
            would typically be "<major>.<minor>".
            Only applied when appname is present.
        "roaming" (boolean, default False) can be set True to use the Windows
            roaming appdata directory. That means that for users on a Windows
            network setup for roaming profiles, this user data will be
            sync'd on login. See
            <http://technet.microsoft.com/en-us/library/cc766489(WS.10).aspx>
            for a discussion of issues.
    Typical user data directories are:
        Mac OS X:               ~/Library/Application Support/<AppName>
        Unix:                   ~/.local/share/<AppName>    # or in $XDG_DATA_HOME, if defined
        Win XP (not roaming):   C:\Documents and Settings\<username>\Application Data\<AppAuthor>\<AppName>
        Win XP (roaming):       C:\Documents and Settings\<username>\Local Settings\Application Data\<AppAuthor>\<AppName>
        Win 7  (not roaming):   C:\Users\<username>\AppData\Local\<AppAuthor>\<AppName>
        Win 7  (roaming):       C:\Users\<username>\AppData\Roaming\<AppAuthor>\<AppName>
    For Unix, we follow the XDG spec and support $XDG_DATA_HOME.
    That means, by default "~/.local/share/<AppName>".
    """
    if system == "win32":
        raise RuntimeError("Sorry, Windows is not supported for now.")
    elif system == 'darwin':
        path = os.path.expanduser('~/Library/Application Support/')
        if appname:
            path = os.path.join(path, appname)
    else:
        path = os.getenv('XDG_DATA_HOME', os.path.expanduser("~/.local/share"))
        if appname:
            path = os.path.join(path, appname)
    if appname and version:
        path = os.path.join(path, version)
    return path


if __name__ == '__main__':
    main()

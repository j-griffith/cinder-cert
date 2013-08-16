#!/usr/bin/python

import contextlib
import os
import subprocess
import sys

from optparse import OptionParser

from cinder.openstack.common import processutils as putils
from cinder.openstack.common import timeutils


@contextlib.contextmanager
def _cd(path):
    original_dir = os.getcwd()
    try:
        os.chdir(path)
    except Exception:
        print('Failed to change working directory: %s' % sys.exc_info()[0])
    try:
        yield
    except Exception:
        print('Exception caught in _cd yield: %s' % sys.exc_info()[0])
    finally:
        os.chdir(original_dir)


def _process_options():
    usage = "usage: %prog [options]"\
            "\n\nRuns the Cinder driver certification tests."
    parser = OptionParser(usage, version='%prog 0.1')
    parser.add_option('-b', '--bug-id', action='store',
                      type='string',
                      default=None,
                      dest='bug_id',
                      help='LP bug-id to associate cert submission to.')
    parser.add_option('-d', '--devstack-location', action='store',
                      type='string',
                      default=None,
                      dest='devstack_path',
                      help='Full path to your devstack repository.')
    parser.add_option('-r', '--results', action='store',
                      type='string',
                      default='/tmp/cinder_driver_cert/',
                      dest='results_dir',
                      help='Directory to store cert results in '
                           '(\'/tmp/cinder_driver_cert/\')')

    options, args = parser.parse_args()
    return (options, args)


def _process_git_status(results_dict):
    out, err = putils.execute('git', 'status')
    results_dict['git_status'] = out

    out, err = putils.execute('git', 'show')
    results_dict['git_show'] = out

    out, err = putils.execute('git', 'diff')
    results_dict['git_diff'] = out


def _scrub_passwords(entry):
    if 'password=' not in entry.lower():
        return entry

    entry_items = entry.split('=')
    entry = entry_items[0] + '=xxxxxxxx'
    return entry


def _get_cinder_info(cinder_path):
    cinder_info = {}
    with _cd(cinder_path):
        out, err = putils.execute('cat', '/etc/cinder/cinder.conf')
        cinderconf_list = out.split()
        cinder_info['cinder_conf'] =\
            [_scrub_passwords(item) for item in cinderconf_list]

        _process_git_status(cinder_info)

    return cinder_info


def _get_devstack_info(devstack_location):
    stack_info = {}
    with _cd(devstack_location):
        stack_info['devstack_path'] = devstack_location

        out, err = putils.execute('cat', './localrc')
        localrc_list = out.split()

        stack_info['local_rc'] =\
            [_scrub_passwords(item) for item in localrc_list]

        _process_git_status(stack_info)

    return stack_info


def _get_stack_path(localrc_list):
    dest = '/opt/stack/'
    for idx, val in enumerate(localrc_list):
        if 'dest=' in val.lower().strip():
            dest = val.split('=')[1]

    return dest


def _run_tempest_api_tests(stack_path):
    with _cd(stack_path + '/tempest'):
        #NOTE(jdg): We're not using putils here intentionally because we want
        #to wait and do some things that we typicall don't do in OpenStack
        proc = subprocess.Popen(['./run_tests.sh', './tempest/api/volume/*'],
                                stdout=subprocess.PIPE, shell=True)
        (out, err) = proc.communicate()

    return out, err


if __name__ == '__main__':

    if len(sys.argv) == 1:
        sys.argv.append('-h')

    time_stamp = timeutils.strtime()
    (options, args) = _process_options()
    print('Gathering devstack env info...')
    devstack_info = _get_devstack_info(options.devstack_path)
    stack_path = _get_stack_path(devstack_info['local_rc'])
    print('Set stack_path to %s' % stack_path)
    print('Gathering cinder env info...')
    cinder_info = _get_cinder_info(stack_path + '/cinder')
    results_file = '/tmp/test.out'
    print('Running tempest api volume tests...')
    out, err = _run_tempest_api_tests(stack_path)

    print ('Stdout results:')
    for line in out.split('\n'):
        print line

    print ('Stderr results:')
    for line in err.split('\n'):
        print line

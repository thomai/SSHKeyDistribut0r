# -*- coding: utf-8 -*-

import argparse
import json
import logging
import os
import re
import shutil
import socket
import sys
import yaml

import paramiko
import scp

logging.raiseExceptions=False

CLEANUP_AFTER = True
TMP_DIR_PATH = 'tmp'
TIMEOUT_ON_CONNECT = 2  # in seconds

# Colors for console outputs
COLOR_RED = '\033[91m'
COLOR_GREEN = '\033[92m'
COLOR_END = '\033[0m'

# File extension regex
yaml_ext = re.compile("^\.ya?ml$")
json_ext = re.compile("^\.json$")

def cleanup():
    if os.path.exists(TMP_DIR_PATH):
        shutil.rmtree(TMP_DIR_PATH)


def remove_special_chars(original_string):
    return ''.join(e for e in original_string if e.isalnum())


def error_log(message):
    print u'%s✗ Error: %s%s' % (COLOR_RED, message, COLOR_END)


def server_error_log(ip, comment, message):
    error_log('%s/%s - %s' % (ip, comment, message))


def info_log(message):
    print u'%s✓ %s%s' % (COLOR_GREEN, message, COLOR_END)


def server_info_log(ip, comment, users):
    info_log('%s/%s - %s' % (ip, comment, users))

def read_config(config_file):
    ext = os.path.splitext(config_file)[-1]
    try:
        if yaml_ext.match(ext):
            return yaml.load(open(config_file))
        elif json_ext.match(ext):
            return json.load(open(config_file))
        else:
            error_log("Configuration file extension '%s' not supported. Please use .json or .yml." % ext)
            sys.exit(1)
    except (ValueError, yaml.scanner.ScannerError):
        error_log('Cannot parse malformed configuration file.')
        sys.exit(1)


def main(args):
    # Load config files
    servers = read_config(args.server)
    keys = read_config(args.keys)

    for server in servers:
        if len(server['authorized_users']) > 0:
            # Generate key file for this server
            key_file_name = 'authorized_keys_%s' % remove_special_chars(server['comment'] + server['ip'])
            key_file = open('%s/%s' % (TMP_DIR_PATH, key_file_name), 'w+')
            server_users = []

            # Write all keys of users with permissions for this server
            for authorized_user in server['authorized_users']:
                # user_name = '%s (%s)' % (keys[authorized_user]['fullname'], authorized_user)
                user_name = authorized_user
                server_users.append(user_name)
                if authorized_user in keys.keys():
                    for key in keys[authorized_user]['keys']:
                        key_file.write('%s\n' % key)
            key_file.close()

            if args.dry_run:
                server_info_log(server['ip'], server['comment'], ', '.join(server_users))
            else:
                # Configure SSH client
                ssh_client = paramiko.SSHClient()
                ssh_client.load_system_host_keys()  # Load host keys to check whether they are matching
                ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())  # Add missing host keys automatically
                try:
                    # Establish connection
                    ssh_client.connect(server['ip'], port=server['port'], username=server['user'],
                                       timeout=TIMEOUT_ON_CONNECT)
                    scp_client = scp.SCPClient(ssh_client.get_transport())

                    # Upload key file
                    remote_path = '.ssh/authorized_keys'
                    scp_client.put('%s/%s' % (TMP_DIR_PATH, key_file_name), remote_path=remote_path)
                    scp_client.close()

                    server_info_log(server['ip'], server['comment'], ', '.join(server_users))

                except (paramiko.ssh_exception.NoValidConnectionsError, paramiko.ssh_exception.SSHException):
                    server_error_log(server['ip'], server['comment'], 'Cannot connect to server.')
                except paramiko.ssh_exception.PasswordRequiredException:
                    server_error_log(server['ip'], server['comment'],
                                     'Cannot connect to server because of an authentication problem.')
                except scp.SCPException:
                    server_error_log(server['ip'], server['comment'], 'Cannot send file to server.')
                except socket.timeout:
                    server_error_log(server['ip'], server['comment'], 'Cannot connect to server because of a timeout.')
        else:
            server_error_log(server['ip'], server['comment'], 'No user mentioned in configuration file!')


if __name__ == '__main__':
    print
    print 'SSHKeyDistribut0r'
    print '================='
    print 'Welcome to the world of key distribution!'
    print

    parser = argparse.ArgumentParser(
            description='A tool to automate key distribution with user authorization.')
    parser.add_argument('--dry-run', '-n', action='store_true',
            help='show pending changes without applying them')
    parser.add_argument('--keys', '-k', default='config/keys.yml',
            help="path to keys file (default: '%(default)s')")
    parser.add_argument('--server', '-s', default='config/servers.yml',
            help="path to server file (default: '%(default)s')")
    args = parser.parse_args()

    try:
        cleanup()
        os.makedirs(TMP_DIR_PATH)
        main(args)
        print
        if CLEANUP_AFTER:
            cleanup()
    except KeyboardInterrupt:
        sys.exit(1)

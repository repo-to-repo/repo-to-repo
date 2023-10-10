#!/usr/bin/env python3
import argparse
import json
import logging
import tempfile
from consolidateconfig import ConsolidateConfig
from downloadfile import DownloadFile
from getgithubrelease import GetGithubRelease
from handlefile import HandleFile

logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')

# Define the command line arguments
parser = argparse.ArgumentParser(description="A script to turn github releases into a repo for Debian and RedHat based operating systems")
parser.add_argument('--config-file', '--config', '-f', default='./config.json', help='Path to the configuration file')
parser.add_argument('--owner', '-o', default='UNDEF', help='Specify the owner string for the repo to build packages for')
parser.add_argument('--repo', '-r', default='UNDEF', help='Specify the repo string for the repo to build packages for')
parser.add_argument('--version-match', '-m', default='UNDEF', help='Specify the string to use to find the version to get')
parser.add_argument('--object-regex', '-e', default='UNDEF', help='Specify the string to use to find the file match to get')
parser.add_argument('--target', '-t', default='deb', choices=['deb', 'rpm'], help='The target OS family to get or build a repo for')
parser.add_argument('--path', '-p', default='UNDEF', help='The path to place the downloaded files')
parser.add_argument('--private-key', '-k', default=None, help='**DANGER** Do not use this outside testing environments. Instead pass the environment variable PRIVATE_KEY with the content of this file. The private key for GPG signing the resulting repository files.')
parser.add_argument('--debug', '-d', action='store_true', help='Enable debug logging')
args = parser.parse_args()

# Load the config file (if it exists)
try:
    with open(args.config_file, 'r') as config_file:
        config = json.load(config_file)
except:
    logging.error(f"No config file loaded")
    exit(1)

# Enable/Disable debugging
disable_debug = True
if 'debug' in config and str(config['debug']).lower() == 'true':
    disable_debug = False

if args.debug:
    disable_debug = False

if disable_debug:
    logging.disable(logging.DEBUG)

tempdir = tempfile.TemporaryDirectory()

try:
    allConfig = ConsolidateConfig(config, args, tempdir=tempdir.name)
except BaseException as e:
    logging.error(e.message)
    exit(1)

if not allConfig.exists('path'):
    logging.error(f"No target path defined")
    exit(1)

try:
    release = GetGithubRelease(allConfig)
    assets = release.GetAssets()
    for asset in assets:
        logging.info(f"Getting asset {asset}")
        HandleFile(
            allConfig,
            DownloadFile(assets[asset], config=allConfig, target=f"{tempdir.name}/source").getTarget(),
            assets[asset]
        )
except BaseException as e:
    logging.error(repr(e))
    exit(1)


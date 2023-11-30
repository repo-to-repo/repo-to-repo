#!/usr/bin/env python3

import os
import pwd
import logging
import argparse

from _configuration import Configuration
from _makeRepositories import MakeRepository,MakeDebRepository, MakeRPMRepository
from _exceptions import NotRoot

class RunService:
    def __init__(self):
        self.config: Configuration = None

    def main(self):
        logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
        parser = argparse.ArgumentParser(description="Turn a Github Release into a Linux Repository")

        parser.add_argument("--config", required=True, help="Path to the config file")
        parser.add_argument("--pgp-key", default=None, help="Path to the PGP private key file. Override with `export pgp_key_base64='string'` for a base64 encoded string of the pgp key, or `export pgp_key='path'` for the path to the file.")
        parser.add_argument('--debug', '-d', action='store_true', help='Enable debug logging')
        parser.add_argument('--quiet', '-q', action='store_true', help='Disable warnings')
        parser.add_argument('--output-path', '--output', help="Override the config-defined path to the output.")

        target_path = parser.add_mutually_exclusive_group()
        target_path.add_argument('--timestamp', '--timestamped-output', '-t', default="%Y%m%d%H%M%S", help="Include YYYYMMDDHHIISS in the final output paths, and symlink 'latest' to that path. (Default: ON)")
        target_path.add_argument('--clean', '--clean-output', '-c', action='store_true', help="Do not include YYYYMMDDHHIISS in the final output path. (Default: OFF)")

        args = parser.parse_args()
        if not args.debug:
            logging.disable(logging.DEBUG)

        self.config = Configuration(args.config, args.pgp_key, args)
        self.config.load_pgp_privatekey()
        self.config.get_targets()
        
        uid = os.getuid()
        if uid != 0:
            for target in self.config.targets:
                if 'rpm' in target.result['formats']:
                    raise NotRoot("This script cannot proceed, as you are not root, and you've requested an RPM package, which requires root.")

        debs = []
        rpms = []
        for target in self.config.targets:
            target.getRelease()
            if 'deb_package' in target.result:
                debs.append(target)
                logging.info(f"{target.result['repo']}/{target.result['owner']} release of {target.result['name']} for {target.result['architecture']} obtained and packaged: {target.result['deb_package']}")

            if 'rpm_package' in target.result:
                rpms.append(target)
                logging.info(f"{target.result['repo']}/{target.result['owner']} release of {target.result['name']} for {target.result['architecture']} obtained and packaged: {target.result['rpm_package']}")
        
        support = MakeRepository(self.config.runtime_config)

        if len(debs) > 0:
            MakeDebRepository(debs, self.config.runtime_config)

        if len(rpms) > 0:
            MakeRPMRepository(rpms, self.config.runtime_config)

        support.finalize()


if __name__ == "__main__":
    service = RunService()
    try:
        service.main()
    except Exception as e:
        logging.error(e)
        service.config.cleanUp()
        raise e

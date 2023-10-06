import os
import re
import shutil
import logging
import subprocess
import tarfile
import tempfile
from consolidateconfig import ConsolidateConfig
from getgithubrelease import GithubAsset

class HandleFile:
    def __init__(self, config: ConsolidateConfig, target: str, asset: GithubAsset):
        logging.debug('HandleFile:__init__')
        self.config = config
        self.asset  = asset
        asset_item  = self.config.get('object_regex')

        self.target_file=target

        if asset_item.endswith('.deb'):
            self._handleDeb()
        elif (
            asset_item.endswith('.tar.gz') or 
            asset_item.endswith('.tgz') or
            asset_item.endswith('.tar') or
            asset_item.endswith('.tar.bz2') or
            asset_item.endswith('.tar.bz')
        ):
            self._handleTar()
        elif asset_item.endswith('.zip'):
            self._handleZip()
        else:
            self._handleBinary()

    def _tempdir(self):
        logging.debug('HandleFile:_tempdir')
        workdir = tempfile.TemporaryDirectory(dir=self.config.get('tempdir')).name
        self.config.put('workdir', workdir)
        logging.debug(f"Unpacking archive to {workdir}")
        return workdir

    def _findbinary(self):
        logging.debug('HandleFile:_findbinary')
        pattern = self.config.get('target_binary_regex', 'NONE')
        file    = self.config.get('target_binary', 'NONE')
        for root, dirs, files in os.walk(self.config.get('workdir')):
            if file != 'NONE' and file in files:
                return os.path.join(root, file)
            if pattern != 'NONE':
                for a_filename in files:
                    filename=os.path.join(root, a_filename)
                    logging.debug(f"Checking filename: '{filename}' to match '{pattern}'")
                    match = re.search(pattern, filename)
                    if match:
                        logging.debug("Matched")
                        return filename
        raise FileNotFoundError

    def _handleDeb(self):
        logging.debug('HandleFile:_handleDeb')
        # TODO: Untested!
        os.makedirs(f"{self.config.get('path')}", mode=0o755, exist_ok=True)
        shutil.move(self.target_file, f"{self.config.get('path')}")
    
    def _handleTar(self):
        logging.debug('HandleFile:_handleTar')
        workdir = self._tempdir()
        with tarfile.open(self.target_file, 'r') as tar:
            tar.extractall(path=workdir)
        self.target_file = self._findbinary()
        self._handleBinary()

    def _handleBinary(self):
        logging.debug('HandleFile:_handleBinary')
        workdir = self._tempdir()
        try:
            bin_path='bin'
            if self.config.get('root_only', 'NONE') != 'NONE':
                bin_path='sbin'
            if self.config.get('target') == 'deb':
                # Get the version number
                version_search = re.search(r'^[^0-9]*([0-9].*)', self.asset.tag)
                if version_search:
                    version = version_search.group(1)
                else:
                    version = self.asset.release_date
                # Build the control file text
                control = [
                    f"Package:      {self.config.get('repo')}",
                    f"Version:      {version}",
                    f"Architecture: {self.config.get('architecture')}",
                    "Section:      misc",
                    f"Maintainer:   '{self.config.get('maintainer', self.config.get('owner'))} <{self.config.get('maintainer', self.config.get('owner'))}@users.noreply.github.com>'",
                    f"Description:  {self.config.get('package_description', 'An internally packaged release of the named package from Github.')}",
                    f"Homepage:     https://github.com/{self.config.get('owner')}/{self.config.get('repo')}"
                ]
                if self.config.exists('dependency'):
                    control.append(f"Depends: {self.config.get('dependency')}")

                os.makedirs(f"{workdir}/DEBIAN", mode=0o755, exist_ok=True)
                with open(f"{workdir}/DEBIAN/control", mode="w") as file:
                    logging.debug("Creating DEBIAN/control file")
                    for line in control:
                        logging.debug(f"Writing {line}")
                        file.write(line + "\n")

                os.makedirs(f"{workdir}/usr/{bin_path}", mode=0o755, exist_ok=True)
                shutil.move(self.target_file, f"{workdir}/usr/{bin_path}")

                if self.config.exists('autocomplete_bash'):
                    os.makedirs(f"{workdir}/etc/bash_completion.d", mode=0o755, exist_ok=True)
                    with open(f"{workdir}/etc/bash_completion.d/{self.config.get('repo')}", mode="w") as file:
                        logging.debug(f"Creating etc/bash_completion.d/{self.config.get('repo')}")
                        if isinstance(self.config.get('autocomplete_bash'), str):
                            file.write(self.config.get('autocomplete_bash') + "\n")
                        elif isinstance(self.config.get('autocomplete_bash'), list):
                            for line in self.config.get('autocomplete_bash'):
                                logging.debug(f"Writing {line}")
                                file.write(line + "\n")

                os.makedirs(self.config.get('path'), mode=0o755, exist_ok=True)
                output=f"{self.config.get('path')}/{self.config.get('repo')}_{version}_{self.config.get('architecture')}.deb"
                cmd=f"dpkg-deb --build '{workdir}' '{output}'"
                subprocess.run(cmd, shell=True, check=True)
                return output
        except BaseException as e:
            logging.error(repr(e))
            debug=self.config.get('debug')
            if (isinstance(debug, bool) and self.config.get('debug')) or (isinstance(self.config.get('debug'), str) and self.config.get('debug').lower == 'true'):
                logging.error(repr(e))
                logging.error(f"Please find the current state of the build in {workdir}")
                subprocess.run("sleep 10000", shell=True, check=True)
                exit(1)

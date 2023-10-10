import io
import os
import re
import gnupg
import shutil
import logging
import tarfile
import zipfile
import tempfile
import subprocess
from   datetime                    import datetime
from   getgithubrelease            import GithubAsset
from   consolidateconfig           import ConsolidateConfig
from   createCompressedHashedFiles import CreateCompressedHashedFiles

class HandleFile:
    def __init__(self, config: ConsolidateConfig, asset_to_handle: str, asset: GithubAsset):
        logging.debug('HandleFile:__init__')
        self.config = config
        self.asset  = asset
        asset_item  = self.config.get('object_regex')

        self.asset_to_handle=asset_to_handle

        # Get the version number
        # This regex looks for everthing at the start of the string which is not a number, and removes it
        version_search = re.search(r'^[^0-9]*([0-9].*)', self.asset.tag)
        if version_search:
            self.version = version_search.group(1)
        else:
            self.version = self.asset.release_date

        # Check whether we already have this release of the package. Return if we do.
        run_process=True
        if self.config.get('target') == 'deb':
            # Default: deb hxxp://repo.example.org {owner}/{repo} latest
            # e.g. for package terminate-notice/terminate-notice this would be
            # deb hxxp://repo.example.org terminate-notice/terminate-notice latest
            # BUT it could be overridden (with deb_component=v1) to:
            # deb hxxp://repo.example.org terminate-notice/terminate-notice v1
            # OR (with deb_suite=terminate-notice)
            # deb hxxp://repo.example.org terminate-notice v1
            self.target_deb_directory=os.path.join(self.config.get('deb_repo_path', self.config.get('path')), 'pool', self.config.get('deb_component', 'latest'))
            self.target_deb_filename=f"{self.config.get('repo')}_{self.version}_{self.config.get('deb_architecture')}.deb"
            self.target_deb_final_path=os.path.join(self.target_deb_directory, self.target_deb_filename)
            self.target_deb_repo_directory=os.path.join(self.config.get('deb_repo_path', self.config.get('path')), 'dists', self.config.get('deb_codename', os.path.join(self.config.get('owner'), self.config.get('repo'))))
            self.target_deb_repo_package_fragment=os.path.join(self.config.get('deb_component', 'latest'), f"binary-{self.config.get('deb_architecture')}")
            self.target_deb_repo_package_directory=os.path.join(self.target_deb_repo_directory, self.target_deb_repo_package_fragment)

            if os.path.exists(self.target_deb_final_path):
                logging.info(f"Target file ({self.target_deb_final_path}) already exists. Skipping.")
                run_process=False

        if run_process:
            if asset_item.endswith('.deb'):
                if self.config.get('target') == 'deb':
                    self._handleDeb()
                else:
                    raise ValueError('Mixed .deb file with non deb target')
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
            
        if self.config.get('target') == 'deb':
            self._handleDebPool()

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
        os.makedirs(self.target_deb_directory, mode=0o755, exist_ok=True)
        shutil.move(self.asset_to_handle, self.target_deb_final_path)
    
    def _handleTar(self):
        logging.debug('HandleFile:_handleTar')
        workdir = self._tempdir()
        with tarfile.open(self.asset_to_handle, 'r') as tar:
            tar.extractall(path=workdir)
        self.asset_to_handle = self._findbinary()
        self._handleBinary()
    
    def _handleZip(self):
        logging.debug('HandleFile:_handleZip')
        workdir = self._tempdir()
        with zipfile.ZipFile(self.asset_to_handle, 'r') as zip:
            zip.extractall(path=workdir)
        self.asset_to_handle = self._findbinary()
        self._handleBinary()

    def _handleBinary(self):
        logging.debug('HandleFile:_handleBinary')
        workdir = self._tempdir()
        try:
            bin_path='bin'
            if self.config.get('root_only', 'NONE') != 'NONE':
                bin_path='sbin'
            if self.config.get('target') == 'deb':
                # Build the control file text
                control = [
                    f"Package:      {self.config.get('repo')}",
                    f"Version:      {self.version}",
                    f"Architecture: {self.config.get('deb_architecture')}",
                    f"Section:      {self.config.get('deb_section', 'misc')}",
                    f"Maintainer:   '{self.config.get('maintainer', self.config.get('owner'))} <{self.config.get('maintainer', self.config.get('owner'))}@users.noreply.github.com>'",
                    f"Description:  {self.config.get('package_description', 'An internally packaged release of the named package from Github.')}",
                    f"Homepage:     https://github.com/{self.config.get('owner')}/{self.config.get('repo')}"
                ]
                if self.config.exists('dependency'):
                    control.append(f"Depends: {self.config.get('dependency')}")

                os.makedirs(os.path.join(workdir, "DEBIAN"), mode=0o755, exist_ok=True)
                with open(os.path.join(workdir, "DEBIAN", "control"), mode="w") as file:
                    logging.debug("Creating DEBIAN/control file")
                    for line in control:
                        logging.debug(f"Writing {line}")
                        file.write(line + "\n")

                os.makedirs(os.path.join(workdir, "usr", bin_path), mode=0o755, exist_ok=True)
                shutil.move(self.asset_to_handle, os.path.join(workdir, "usr", bin_path))

                if self.config.exists('autocomplete_bash'):
                    os.makedirs(os.path.join(workdir, "etc", "bash_completion.d"), mode=0o755, exist_ok=True)
                    with open(os.path.join(workdir, "etc", "bash_completion.d", self.config.get('repo')), mode="w") as file:
                        logging.debug(f"Creating etc/bash_completion.d/{self.config.get('repo')}")
                        if isinstance(self.config.get('autocomplete_bash'), str):
                            file.write(self.config.get('autocomplete_bash') + "\n")
                        elif isinstance(self.config.get('autocomplete_bash'), list):
                            for line in self.config.get('autocomplete_bash'):
                                logging.debug(f"Writing {line}")
                                file.write(line + "\n")

                os.makedirs(self.target_deb_directory, mode=0o755, exist_ok=True)
                cmd=f"dpkg-deb --build '{workdir}' '{self.target_deb_final_path}'"
                subprocess.run(cmd, shell=True, check=True)
                return True
        except BaseException as e:
            logging.error(repr(e))
            debug=self.config.get('debug')
            if (isinstance(debug, bool) and debug) or (isinstance(debug, str) and debug.lower == 'true'):
                logging.error(repr(e))
                logging.error(f"Please find the current state of the build in {workdir}")
                subprocess.run("sleep 10000", shell=True, check=True)
                exit(1)

    def _handleDebPool(self):
        gpg = self.config.get('gpg')

        os.makedirs(self.target_deb_repo_package_directory, mode=0o755, exist_ok=True)
        cmd=f"dpkg-scanpackages --arch {self.config.get('deb_architecture')} pool/"
        packageFile=os.path.join(self.target_deb_repo_package_directory, 'Packages')
        logging.debug(f'About to run {cmd}')
        try:
            scanpackage = subprocess.run(
                cmd,
                cwd=self.config.get('deb_repo_path', self.config.get('path')),
                capture_output = True,
                shell=True,
                text=True
            )
            logging.debug('Finished. Output follows:')
            logging.debug(scanpackage.stdout)
            logging.debug(f'Writing this to {packageFile}, {packageFile}.gz, {packageFile}.bz2 and {packageFile}.xz')
            packageFileText = scanpackage.stdout
            packageFiles = CreateCompressedHashedFiles(packageFile, packageFileText)
            logging.debug('Done')
        except BaseException as e:
            raise e

        releases = [
            f"Origin: SOMESTRING",
            f"Label: SOMESTRING",
            f"Suite: {self.config.get('deb_codename', os.path.join(self.config.get('owner'), self.config.get('repo')))}",
            f"Codename: {self.config.get('deb_codename', os.path.join(self.config.get('owner'), self.config.get('repo')))}",
            f"Version: {self.asset.release_date}",
            f"Architectures: {self.config.get('deb_architecture')}",
            f"Components: {self.config.get('deb_component', 'latest')}",
            f"Description: {self.config.get('package_description', 'An internally packaged release of the named package from Github.')}",
            f"Date: {datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')}",
             "MD5Sum:",
            f" {packageFiles.hashes['plain']['md5'].hexdigest()} {str(packageFiles.hashes['plain']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages",
            f" {packageFiles.hashes['gzip']['md5'].hexdigest()} {str(packageFiles.hashes['gzip']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.gz",
            f" {packageFiles.hashes['bzip2']['md5'].hexdigest()} {str(packageFiles.hashes['bzip2']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.bz2",
            f" {packageFiles.hashes['xz']['md5'].hexdigest()} {str(packageFiles.hashes['xz']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.xz",
             "SHA1:",
            f" {packageFiles.hashes['plain']['sha1'].hexdigest()} {str(packageFiles.hashes['plain']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages",
            f" {packageFiles.hashes['gzip']['sha1'].hexdigest()} {str(packageFiles.hashes['gzip']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.gz",
            f" {packageFiles.hashes['bzip2']['sha1'].hexdigest()} {str(packageFiles.hashes['bzip2']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.bz2",
            f" {packageFiles.hashes['xz']['sha1'].hexdigest()} {str(packageFiles.hashes['xz']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.xz",
             "SHA256:",
            f" {packageFiles.hashes['plain']['sha256'].hexdigest()} {str(packageFiles.hashes['plain']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages",
            f" {packageFiles.hashes['gzip']['sha256'].hexdigest()} {str(packageFiles.hashes['gzip']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.gz",
            f" {packageFiles.hashes['bzip2']['sha256'].hexdigest()} {str(packageFiles.hashes['bzip2']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.bz2",
            f" {packageFiles.hashes['xz']['sha256'].hexdigest()} {str(packageFiles.hashes['xz']['size']).rjust(16)} {self.target_deb_repo_package_fragment}/Packages.xz",
             "Acquire-By-Hash: yes"
        ]

        logging.debug(f"Creating {os.path.join(self.target_deb_repo_directory, 'Release')} content")
        file_content = io.BytesIO()
        for line in releases:
            file_content.write((line + "\n").encode('utf-8'))

        logging.debug(f"Writing {os.path.join(self.target_deb_repo_directory, 'Release')} content")
        os.makedirs(self.target_deb_repo_directory, mode=0o755, exist_ok=True)
        with open(os.path.join(self.target_deb_repo_directory, "Release"), mode="wb") as file:
            logging.debug(f"Creating Release file in {os.path.join(self.target_deb_repo_directory, 'Release')}")
            file.write(file_content.getvalue())

        with open(os.path.join(self.target_deb_repo_directory, "Release.gpg"), mode="w") as file:
            logging.debug(f"Creating Release file in {os.path.join(self.target_deb_repo_directory, 'Release.gpg')}")
            file.write(gpg.sign(file_content.getvalue(), detach=True).data.decode('utf-8'))
        with open(os.path.join(self.target_deb_repo_directory, "InRelease"), mode="w") as file:
            logging.debug(f"Creating Release file in {os.path.join(self.target_deb_repo_directory, 'InRelease')}")
            file.write(gpg.sign(file_content.getvalue(), detach=True, clearsign=True).data.decode('utf-8'))
        
        logging.debug('All done?!')

        return True

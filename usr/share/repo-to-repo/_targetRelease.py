import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
import zipfile

import requests

from _exceptions import RepoTargetInvalidValue, RepoTargetMissingValue, GithubApiNotAvailable, ApiNotAvailable


class TargetRelease:
    def __init__(self, target: dict, runtime_config: dict = None):
        self.result = target

        if runtime_config is not None:
            self.config = runtime_config
        else:
            self.config = {}
            self.config["headers"] = {}
            self.config["path"] = ""
            self.config["workdir"] = ""
            self.config["builddir"] = ""
            self.config["pathmode"] = None
            self.config["gnupghome"] = ""
            self.config["privatekey"] = ""
            self.config["privatekey_id"] = ""
            self.config["privatekey_uid"] = ""

        self._setArchitecture()
        self._validateValues()

    def __repr__(self) -> str:
        return json.dumps(self.result)

    def _setArchitecture(self):
        if "architecture" in self.result:
            architecture = self.result["architecture"]
            self.result["debian_architecture"] = architecture
            self.result["redhat_architecture"] = architecture
            if architecture in ['all', 'noarch', 'any']:
                self.result["debian_architecture"] = 'all'
                self.result["redhat_architecture"] = 'noarch'
            if architecture in ['x86_64', 'amd64', 'x86-64']:  # 64bit Intel
                self.result["debian_architecture"] = 'amd64'
                self.result["redhat_architecture"] = 'x86_64'
            if architecture in ['aarch64', 'arm64']:  # 64bit ARM
                self.result["debian_architecture"] = 'arm64'
                self.result["redhat_architecture"] = 'aarch64'

    def _validateValues(self):
        # Variables used for other tests below
        invalid_formats = []
        unused_autocompletes = []
        # Used for architecture cross-mapping
        validArchitectures = [
            # Default "any" architectures (e.g. shell scripts, interpreted scripts)
            'noarch', 'all', 'any',
            'x86-64', 'amd64',      # Intel/AMD architectures
            'arm64', 'aarch64'      # ARM architectures
        ]                           # Note that no other architectures are listed as neither RedHat nor Debian
        # have these releases commonly available. As always, Pull requests, welcome!
        # Used by Debian Packages
        validArchives = ['main', 'contrib', 'non-free']
        validSuites = [
            'admin', 'cli-mono', 'comm', 'database', 'debug', 'devel', 'doc', 'editors',
            'education', 'electronics', 'embedded', 'fonts', 'games', 'gnome', 'gnu-r', 'gnustep',
            'graphics', 'hamradio', 'haskell', 'httpd', 'interpreters', 'introspection', 'java',
            'javascript', 'kde', 'kernel', 'libdevel', 'libs', 'lisp', 'localization', 'mail',
            'math', 'metapackages', 'misc', 'net', 'news', 'ocaml', 'oldlibs', 'otherosfs', 'perl',
            'php', 'python', 'ruby', 'rust', 'science', 'shells', 'sound', 'tasks', 'tex', 'text',
            'utils', 'vcs', 'video', 'web', 'x11', 'xfce', 'zope'
        ]
        validPriorities = ['required', 'important',
                           'standard', 'optional', 'extra']

        if not isinstance(self.result['object_regex'], str):
            raise RepoTargetInvalidValue(
                f"object_regex must be a string, got {type(self.result['object_regex'])}")
        if self.result['object_regex'] is None or self.result['object_regex'] == '':
            raise RepoTargetMissingValue("object_regex is a required value.")

        if not isinstance(self.result['formats'], list):
            raise RepoTargetInvalidValue(
                f"formats must be a list, got {type(self.result['formats'])}")
        if self.result['formats'] is None or self.result['formats'] == []:
            raise RepoTargetMissingValue("formats is a required value.")
        for format in self.result['formats']:
            if format not in ['deb', 'rpm']:
                invalid_formats += [format]
        if len(invalid_formats) > 0:
            raise RepoTargetInvalidValue(
                f"formats should only (currently) be one of 'deb' or 'rpm', got {invalid_formats}. [Pull requests, welcome!](https://github.com/repo-to-repo/repo-to-repo)")

        if not isinstance(self.result['architecture'], str):
            raise RepoTargetInvalidValue(
                f"architecture must be a string, got {type(self.result['architecture'])}")
        if self.result['architecture'] is None or self.result['architecture'] == '':
            raise RepoTargetMissingValue("architecture is a required value.")
        if not self.result['architecture'] in validArchitectures:
            if not self.config['quiet']:
                logging.warning(
                    f"architecture ('{self.result['architecture']}') is not, but should be, one of ('noarch' == 'all' == 'any'), ('x86-64' == 'amd64'), or ('arm64' == 'aarch64') due to architecture mapping. [Pull requests, welcome!](https://github.com/repo-to-repo/repo-to-repo)")

        if not isinstance(self.result['owner'], str):
            raise RepoTargetInvalidValue(
                f"owner must be a string, got {type(self.result['owner'])}")
        if self.result['owner'] is None or self.result['owner'] == '':
            raise RepoTargetMissingValue("owner is a required value.")

        if not isinstance(self.result['repo'], str):
            raise RepoTargetInvalidValue(
                f"repo must be a string, got {type(self.result['repo'])}")
        if self.result['repo'] is None or self.result['repo'] == '':
            raise RepoTargetMissingValue("repo is a required value.")

        if not (self.result['object_regex'].endswith('.deb') or self.result['object_regex'].endswith('.rpm')):
            if not isinstance(self.result['target_binary'], str):
                raise RepoTargetInvalidValue(
                    f"target_binary must be a string, got {type(self.result['target_binary'])}")
            if self.result['target_binary'] is None or self.result['target_binary'] == '':
                raise RepoTargetMissingValue(
                    "target_binary is a required value.")

            if self.result['autocomplete'] is not None and len(self.result['autocomplete']) > 0:
                for shell in self.result['autocomplete']:
                    if shell != 'bash':
                        unused_autocompletes += [shell]
                if len(unused_autocompletes) > 0:
                    if not self.config['quiet']:
                        logging.warning(
                            f"You have specified shells in autocomplete which are not currently handled ({unused_autocompletes}). These won't be actioned. [Pull requests, welcome!](https://github.com/repo-to-repo/repo-to-repo)")

        if 'deb' in self.result['formats']:
            # Debian specific formats
            if not isinstance(self.result['archive'], str):
                raise RepoTargetInvalidValue(
                    f"archive must be a string, got {type(self.result['archive'])}")
            if self.result['archive'] is None or self.result['archive'] == '':
                raise RepoTargetMissingValue(
                    "archive is a required value for debian format packages.")
            if not self.result['archive'] in validArchives:
                if not self.config['quiet']:
                    logging.warning(
                        f"Archive ('{self.result['archive']}') is not, but should be, one of the valid archives from the list in the [Debian Policy](https://www.debian.org/doc/debian-policy/ch-archive.html#archive-areas). Ensure you're comfortable with this before publishing.")

            if self.result['suite'] is None or self.result['suite'] == '':
                raise RepoTargetMissingValue(
                    "suite is a required value for debian format packages.")
            if not isinstance(self.result['suite'], str):
                raise RepoTargetInvalidValue(
                    f"suite must be a string, got {type(self.result['suite'])}")
            if not self.result['suite'] in validSuites:
                if not self.config['quiet']:
                    logging.warning(
                        f"suite ('{self.result['suite']}') is not, but should be, one of the valid suites from the list in the [Debian Policy](https://www.debian.org/doc/debian-policy/ch-archive.html#s-subsections). Ensure you're comfortable with this before publishing.")

            if self.result['priority'] is None or self.result['priority'] == '':
                raise RepoTargetMissingValue(
                    "priority is a required value for debian format packages.")
            if not isinstance(self.result['priority'], str):
                raise RepoTargetInvalidValue(
                    f"priority must be a string, got {type(self.result['priority'])}")
            if not self.result['priority'] in validPriorities:
                raise RepoTargetInvalidValue(
                    f"priority ('{self.result['priority']}') is not, but must be, one of the valid priority values from the list in the [Debian Policy](https://www.debian.org/doc/debian-policy/ch-archive.html#s-priorities).")

        logging.debug(f"Values validated for RepoTarget: object_regex: {self.result['object_regex']} | formats: {self.result['formats']} | architecture: {self.result['architecture']} | owner: {self.result['owner']} | repo: {self.result['repo']} | target_binary: {self.result['target_binary']} | version_match: {self.result['version_match']} | autocomplete: {self.result['autocomplete']} | suite: {self.result['suite']} | archive: {self.result['archive']}")

    def _getData(self, api_url: str) -> json:
        try:
            logging.debug(f"Getting API {api_url}")
            response = requests.get(api_url, headers=self.config["headers"])
        except:
            raise ApiNotAvailable("Unable to load github api")
        if response.status_code != 200:
            raise ApiNotAvailable(
                f"Failed to retrieve data from GitHub API Endpoint: {api_url}. Status code: {response.status_code}")

        return response.json()

    def _getReleaseData(self, page: int = 1) -> bool:
        # TODO: Consider how to handle a non Github Repo
        # TODO: Consider how to handle more than a single binary release, e.g. aws-cli
        if "platform" not in self.result or self.result['platform'] == 'github':
            if 'license' not in self.result:
                data = self._getData(
                    f'https://api.github.com/repos/{self.result["owner"]}/{self.result["repo"]}')
                self.result['license'] = 'TBC'
                if (
                    'license' in data and
                    len(data['license']) > 0 and
                    'name' in data['license'] and
                    len(data['license']['name']) > 0
                ):
                    self.result['license'] = data['license']['name']

            data = self._getData(
                f'https://api.github.com/repos/{self.result["owner"]}/{self.result["repo"]}/releases?page={page}')
            if self.result["version_match"] is None or self.result["version_match"] == '' or self.result["version_match"] == 'latest':
                self.release = data[0]
                return True
            else:
                for entry in data:
                    tag = entry['tag_name']
                    version_match = self.result["version_match"]
                    logging.debug(
                        f"Tag matching? {tag} == {version_match}: {tag.startswith(version_match)}")
                    if version_match != '':
                        if tag.startswith(self.result['version_match']):
                            self.release = entry
                            return True
                    else:
                        self.release = entry
                        return True

            if len(data) > 0:
                return self._getReleaseData(page+1)
            else:
                raise RecursionError("Failed to get a release")
        else:
            raise ValueError(
                f"Invalid platform defined. Got {self.result['platform']}")

    def _getAsset(self) -> bool:
        if "platform" not in self.result or self.result['platform'] == 'github':
            for asset in self.release['assets']:
                nameMatch = re.match(self.result.get(
                    'object_regex'), asset['name'])
                if nameMatch:
                    self.result['name'] = asset['name']

                    versionSearch = re.search(
                        r'^[^0-9]*([0-9].*)', self.release['tag_name'])
                    if versionSearch:
                        versionNumber = versionSearch.group(1)
                    else:
                        versionNumber = self.release['published_at']

                    self.result['versionNumber'] = versionNumber
                    self.package_id = f"{self.result['repo']}-{versionNumber}-{self.result['architecture']}"
                    self.package_path = os.path.join(
                        self.config["workdir"], 'SOURCES', self.package_id)

                    with open(os.path.join(self.config["workdir"], asset['name']), 'wb') as downloadFile:
                        response = requests.get(
                            asset['browser_download_url'], self.config["headers"])
                        if response.status_code == 200:
                            downloadFile.write(response.content)
                            self.result['file'] = downloadFile.name
                            downloadFile.close()
                            logging.debug(
                                f"Written file to {downloadFile.name}")
                        else:
                            raise FileNotFoundError(
                                f"Failed to download the file: {asset['browser_download_url']}")

                    file_extensions = ['.tgz', '.gz', '.bz2', '.xz', '.zip']
                    unpack_dir = os.path.join(self.config['workdir'], 'unpack')

                    if any(self.result['file'].endswith(ext) for ext in file_extensions):
                        # Unpack the file based on its extension
                        if self.result['file'].endswith('.zip'):
                            with zipfile.ZipFile(self.result['file'], 'r') as zip_ref:
                                zip_ref.extractall(unpack_dir)
                        elif self.result['file'].endswith('.tgz') or self.result['file'].endswith('.gz'):
                            with tarfile.open(self.result['file'], 'r:gz') as tar_ref:
                                tar_ref.extractall(unpack_dir)
                        elif self.result['file'].endswith('.bz2'):
                            with tarfile.open(self.result['file'], 'r:bz2') as tar_ref:
                                tar_ref.extractall(unpack_dir)
                        elif self.result['file'].endswith('.xz'):
                            with tarfile.open(self.result['file'], 'r:xz') as tar_ref:
                                tar_ref.extractall(unpack_dir)

                        file_regex = self.result.get(
                            'file_regex', f"^{self.result['target_binary']}$")
                        for root, _, files in os.walk(unpack_dir):
                            for file in files:
                                file_path = os.path.join(root, file)
                                if os.path.isfile(file_path) and re.match(file_regex, file):
                                    self.result['file'] = file_path
                    return True
            raise ValueError("Did not match the asset in the object_regex")
        else:
            raise ValueError(
                f"Invalid platform defined. Got {self.result['platform']}")

    def _set_ownership(self, directory_path, owner, group, directory_perm, file_perm):
        for root, dirs, files in os.walk(directory_path):
            for filename in files:
                file_path = os.path.join(root, filename)
                os.chown(file_path, owner, group)
                os.chmod(file_path, file_perm)
            for directory in dirs:
                dir_path = os.path.join(root, directory)
                os.chown(dir_path, owner, group)
                os.chmod(dir_path, directory_perm)
                self._set_ownership(dir_path, owner, group,
                                    directory_perm, file_perm)

    def _preparePackage(self) -> list:
        if not os.path.exists(self.config["workdir"]):
            raise FileNotFoundError(
                f"Workdir Path not found {self.config['workdir']}")
        if not os.path.exists(self.config["builddir"]):
            raise FileNotFoundError(
                f"Builddir Path not found {self.config['builddir']}")

        os.makedirs(os.path.join(self.package_path, 'usr', 'local', 'bin'))
        shutil.copy(self.result['file'], os.path.join(
            self.package_path, 'usr', 'local', 'bin', self.result['target_binary']))
        self._set_ownership(self.package_path, 0, 0, 0o755, 0o755)
        # TODO: Support more autocomplete systems
        if 'bash' in self.result['autocomplete']:
            os.makedirs(os.path.join(self.package_path,
                        'etc', 'bash_completion.d'))
            with open(os.path.join(self.package_path, 'etc', 'bash_completion.d', self.result['target_binary']), 'w') as file:
                file.write(self.result['autocomplete']['bash'])
                file.write("\n")

            self._set_ownership(os.path.join(
                self.package_path, 'etc'), 0, 0, 0o644, 0o755)

    def _renderRpmPackage(self):
        if self.result['name'].endswith('.rpm'):
            self.result["rpm_package_filename"] = self.result['name']
            self.result["rpm_package"] = os.path.join(
                self.config["builddir"], self.result['name'])
            os.rename(self.result['file'], self.result["rpm_package"])
        else:
            rpmmap = [
                's~^usr/include~%{_includedir}~',
                's~^etc~%{_sysconfdir}~',
                's~^usr/bin~%{_bindir}~',
                's~^usr/sbin~%{_sbindir}~',
            ]

            if self.result['redhat_architecture'] == 'x64':
                rpmmap.append('s~^usr/lib64~%{_libdir}~')
                rpmmap.append('s~^usr/lib~%{_prefix}/lib~')
            else:
                rpmmap.append('s~^usr/lib64~%{_prefix}/lib64~')
                rpmmap.append('s~^usr/lib~%{_libdir}~')

            rpmmap.append('s~^usr/libexec~%{_libexecdir}~')
            rpmmap.append('s~^usr/share/info~%{_infodir}~')
            rpmmap.append('s~^usr/share/man~%{_mandir}~')
            rpmmap.append('s~^usr/share/doc~%{_docdir}~')
            rpmmap.append('s~^usr/share~%{_datadir}~')
            rpmmap.append('s~^usr~%{_prefix}~')
            rpmmap.append('s~^run~%{_rundir}~')
            rpmmap.append('s~^var/lib~%{_sharedstatedir}~')
            rpmmap.append('s~^var~%{_localstatedir}~')

            self._preparePackage()
            if not os.path.exists(os.path.join(self.config["workdir"], 'SPEC')):
                os.makedirs(os.path.join(self.config["workdir"], 'SPEC'))
            specfile = os.path.join(
                self.config["workdir"], 'SPEC', f"{self.package_id}.spec")
            content = [
                f"Name:      {self.result['repo']}",
                f"Version:   {self.result['versionNumber']}",
                f"Release:   1",
                f"Summary:   {self.result['description']}",
                f"Source0:   {self.package_path}",
                f"License:   {self.result['license']}",
            ]
            if 'redhat_dependencies' in self.result and self.result['redhat_dependencies'] != '':
                content.append(
                    f"Requires:  {self.result['redhat_dependencies']}")
            if 'homepage' in self.result and len(self.result['homepage']) > 0:
                content.append(f"URL:       {self.result['homepage']}")
            content.append("")
            content.append(f"{'%'}description")
            content.append(self.result['description'])
            content.append("")
            content.append(f"{'%'}prep")
            content.append("")
            content.append(f"{'%'}build")
            content.append("")
            content.append(f"{'%'}install")
            install_files = []
            for root, _, files in os.walk(os.path.join(self.package_path)):
                for file in files:
                    file_path = os.path.join(root, file)
                    rpm_path_file = file_path.replace(
                        f"{self.package_path}/", '')
                    for pattern in rpmmap:
                        local_file = re.sub(pattern, '', rpm_path_file)
                    mode = '755' if os.access(
                        file_path, os.X_OK) else '644'
                    content.append(
                        f'install -D -m {mode} -o root -g root %{{SOURCE0}}/{local_file} ${{RPM_BUILD_ROOT}}/{rpm_path_file}')
                    install_files.append(rpm_path_file)
            content.append(f"{'%'}files")
            for install_file in install_files:
                content.append(f"/{install_file}")

            with open(specfile, 'w') as file:
                for line in content:
                    file.write(f"{line}\n")

            target_filename = f"{self.result['repo']}-{self.result['versionNumber']}-1.{self.result['redhat_architecture']}.rpm"
            self.result["rpm_package_filename"] = target_filename
            self.result["rpm_package"] = os.path.join(
                self.config["builddir"], target_filename)
            cmd = f"rpmbuild --target {self.result['redhat_architecture']} --define '_topdir {self.config['workdir']}' -bb {specfile}"
            logging.debug(f"Executing command: {cmd}")
            with subprocess.Popen(cmd, cwd=self.config["builddir"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                exit_code = process.wait()
                stdout = process.stdout.read().decode('utf-8')
                stderr = process.stderr.read().decode('utf-8')
                if exit_code > 0:
                    logging.error(
                        f"Build of {self.result['rpm_package']} failed")
                    logging.error(f"stdout: {stdout}")
                    logging.error(f"stderr: {stderr}")
                    raise Exception("Build failure")

            os.rename(os.path.join(
                self.config['workdir'], 'RPMS', self.result['redhat_architecture'], target_filename), self.result["rpm_package"])

            cmd = f'rpm --define "%_signature gpg" --define "%_gpg_name {self.config["privatekey_id"]}" --addsign "{self.result["rpm_package"]}"'
            logging.debug(f"Executing command: {cmd}")
            with subprocess.Popen(cmd, cwd=self.config["builddir"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                exit_code = process.wait()
                stdout = process.stdout.read().decode('utf-8')
                stderr = process.stderr.read().decode('utf-8')
                if exit_code > 0:
                    logging.error(
                        f"Signature {self.result['rpm_package']} failed")
                    logging.error(f"stdout: {stdout}")
                    logging.error(f"stderr: {stderr}")
                    raise Exception("Signature failure")

            logging.debug(
                f"Build of {self.result['rpm_package']} succeeded")

    def _renderDebPackage(self):
        if self.result['name'].endswith('.deb'):
            self.result["deb_package_filename"] = self.result['name']
            self.result["deb_package"] = os.path.join(
                self.config["builddir"], self.result['name'])
            os.rename(self.result['file'], self.result["deb_package"])
        else:
            self._preparePackage()
            os.makedirs(os.path.join(self.package_path, 'DEBIAN'))
            with open(os.path.join(self.package_path, 'DEBIAN', 'control'), 'w') as file:
                content = [
                    f"Package:      {self.result['repo']}",
                    f"Version:      {self.result['versionNumber']}",
                    f"Section:      {self.result['suite']}",
                    f"Priority:     {self.result['priority'] or 'optional'}",
                    f"Architecture: {self.result['debian_architecture']}",
                ]
                if 'debian_dependencies' in self.result and self.result['debian_dependencies'] != '':
                    content.append(
                        f"Depends:      {self.result['debian_dependencies']}")
                content.append(
                    f"Maintainer:   {self.result['maintainer']}")
                content.append(
                    f"Description:  {self.result['description']}")
                if 'homepage' in self.result and len(self.result['homepage']) > 0:
                    content.append(
                        f"Homepage:     {self.result['homepage']}")
                for line in content:
                    file.write(f"{line}\n")

            target_filename = f"{self.result['repo']}_{self.result['versionNumber']}_{self.result['debian_architecture']}.deb"
            self.result["deb_package_filename"] = target_filename
            self.result["deb_package"] = os.path.join(
                self.config["builddir"], target_filename)
            cmd = f"dpkg-deb --build {self.package_path} {target_filename}"
            logging.debug(f"Executing command: {cmd}")
            with subprocess.Popen(cmd, cwd=self.config["builddir"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                exit_code = process.wait()
                stdout = process.stdout.read().decode('utf-8')
                stderr = process.stderr.read().decode('utf-8')
                if exit_code > 0:
                    logging.error(
                        f"Build of {self.result['deb_package']} failed")
                    logging.error(f"stdout: {stdout}")
                    logging.error(f"stderr: {stderr}")
                    raise Exception("Build failure")

                logging.debug(
                    f"Build of {self.result['deb_package']} succeeded")
            shutil.rmtree(self.package_path)

    def getRelease(self):
        self._getReleaseData()
        self._getAsset()
        if 'deb' in self.result['formats']:
            self._renderDebPackage()
        if 'rpm' in self.result['formats']:
            self._renderRpmPackage()
        if os.path.exists(os.path.join(self.package_path)):
            shutil.rmtree(os.path.join(self.package_path))

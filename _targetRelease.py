import json
import logging
import os
import re
import shutil
import subprocess

import requests

from _exceptions import RepoTargetInvalidValue, RepoTargetMissingValue, GithubApiNotAvailable

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
            if architecture in ['x86-64', 'amd64']: # 64bit Intel
                self.result["debian_architecture"] = 'amd64'
                self.result["redhat_architecture"] = 'x86-64'
            if architecture in ['aarch64', 'arm64']: # 64bit ARM
                self.result["debian_architecture"] = 'arm64'
                self.result["redhat_architecture"] = 'aarch64'

    def _validateValues(self):
        # Variables used for other tests below
        invalid_formats = []
        unused_autocompletes = []
        # Used for architecture cross-mapping
        validArchitectures = [
            'noarch', 'all', 'any', # Default "any" architectures (e.g. shell scripts, interpreted scripts)
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
        validPriorities = ['required', 'important', 'standard', 'optional', 'extra']

        if not isinstance(self.result['object_regex'], str):
            raise RepoTargetInvalidValue(f"object_regex must be a string, got {type(self.result['object_regex'])}")
        if self.result['object_regex'] is None or self.result['object_regex'] == '':
            raise RepoTargetMissingValue("object_regex is a required value.")

        if not isinstance(self.result['formats'], list):
            raise RepoTargetInvalidValue(f"formats must be a list, got {type(self.result['formats'])}")
        if self.result['formats'] is None or self.result['formats'] == []:
            raise RepoTargetMissingValue("formats is a required value.")
        for format in self.result['formats']:
            if format not in ['deb', 'rpm']:
                invalid_formats += [format]
        if len(invalid_formats) > 0:
            raise RepoTargetInvalidValue(f"formats should only (currently) be one of 'deb' or 'rpm', got {invalid_formats}. [Pull requests, welcome!](https://github.com/repo-to-repo/repo-to-repo)")

        if not isinstance(self.result['architecture'], str):
            raise RepoTargetInvalidValue(f"architecture must be a string, got {type(self.result['architecture'])}")
        if self.result['architecture'] is None or self.result['architecture'] == '':
            raise RepoTargetMissingValue("architecture is a required value.")
        if not self.result['architecture'] in validArchitectures:
            if not self.config['quiet']:
                logging.warning(f"architecture ('{self.result['architecture']}') is not, but should be, one of ('noarch' == 'all' == 'any'), ('x86-64' == 'amd64'), or ('arm64' == 'aarch64') due to architecture mapping. [Pull requests, welcome!](https://github.com/repo-to-repo/repo-to-repo)")

        if not isinstance(self.result['owner'], str):
            raise RepoTargetInvalidValue(f"owner must be a string, got {type(self.result['owner'])}")
        if self.result['owner'] is None or self.result['owner'] == '':
            raise RepoTargetMissingValue("owner is a required value.")

        if not isinstance(self.result['repo'], str):
            raise RepoTargetInvalidValue(f"repo must be a string, got {type(self.result['repo'])}")
        if self.result['repo'] is None or self.result['repo'] == '':
            raise RepoTargetMissingValue("repo is a required value.")

        if not (self.result['object_regex'].endswith('.deb') or self.result['object_regex'].endswith('.rpm')):
            if not isinstance(self.result['target_binary'], str):
                raise RepoTargetInvalidValue(f"target_binary must be a string, got {type(self.result['target_binary'])}")
            if self.result['target_binary'] is None or self.result['target_binary'] == '':
                raise RepoTargetMissingValue("target_binary is a required value.")
        
            if self.result['autocomplete'] is not None and len(self.result['autocomplete']) > 0:
                for shell in self.result['autocomplete']:
                    if shell != 'bash':
                        unused_autocompletes += [shell]
                if len(unused_autocompletes) > 0:
                    if not self.config['quiet']:
                        logging.warning(f"You have specified shells in autocomplete which are not currently handled ({unused_autocompletes}). These won't be actioned. [Pull requests, welcome!](https://github.com/repo-to-repo/repo-to-repo)")

        if 'deb' in self.result['formats']:
            # Debian specific formats
            if not isinstance(self.result['archive'], str):
                raise RepoTargetInvalidValue(f"archive must be a string, got {type(self.result['archive'])}")
            if self.result['archive'] is None or self.result['archive'] == '':
                raise RepoTargetMissingValue("archive is a required value for debian format packages.")
            if not self.result['archive'] in validArchives:
                if not self.config['quiet']:
                    logging.warning(f"Archive ('{self.result['archive']}') is not, but should be, one of the valid archives from the list in the [Debian Policy](https://www.debian.org/doc/debian-policy/ch-archive.html#archive-areas). Ensure you're comfortable with this before publishing.")
            
            if self.result['suite'] is None or self.result['suite'] == '':
                raise RepoTargetMissingValue("suite is a required value for debian format packages.")
            if not isinstance(self.result['suite'], str):
                raise RepoTargetInvalidValue(f"suite must be a string, got {type(self.result['suite'])}")
            if not self.result['suite'] in validSuites:
                if not self.config['quiet']:
                    logging.warning(f"suite ('{self.result['suite']}') is not, but should be, one of the valid suites from the list in the [Debian Policy](https://www.debian.org/doc/debian-policy/ch-archive.html#s-subsections). Ensure you're comfortable with this before publishing.")
            
            if self.result['priority'] is None or self.result['priority'] == '':
                raise RepoTargetMissingValue("priority is a required value for debian format packages.")
            if not isinstance(self.result['priority'], str):
                raise RepoTargetInvalidValue(f"priority must be a string, got {type(self.result['priority'])}")
            if not self.result['priority'] in validPriorities:
                raise RepoTargetInvalidValue(f"priority ('{self.result['priority']}') is not, but must be, one of the valid priority values from the list in the [Debian Policy](https://www.debian.org/doc/debian-policy/ch-archive.html#s-priorities).")

        logging.debug(f"Values validated for RepoTarget: object_regex: {self.result['object_regex']} | formats: {self.result['formats']} | architecture: {self.result['architecture']} | owner: {self.result['owner']} | repo: {self.result['repo']} | target_binary: {self.result['target_binary']} | version_match: {self.result['version_match']} | autocomplete: {self.result['autocomplete']} | suite: {self.result['suite']} | archive: {self.result['archive']}")

    def _getReleaseData(self, page: int = 1) -> bool:
        github_api_url = f'https://api.github.com/repos/{self.result["owner"]}/{self.result["repo"]}/releases?page={page}'

        if self.result["version_match"] is None or self.result["version_match"] == '' or self.result["version_match"] == 'latest':
            github_api_url = f'https://api.github.com/repos/{self.result["owner"]}/{self.result["repo"]}/releases/latest'
        else:
            logging.info("Asking Github for a list of all releases.")

        try:
            logging.debug(f"Getting API {github_api_url}")
            response = requests.get(github_api_url, headers=self.config["headers"])
        except:
            raise GithubApiNotAvailable("Unable to load github api")

        if response.status_code != 200:
            raise GithubApiNotAvailable(f"Failed to retrieve data from GitHub API. Status code: {response.status_code}")

        data = response.json()
        if self.result["version_match"] is None or self.result["version_match"] == '' or self.result["version_match"] == 'latest':
            self.release = data
            return True
        else:
            for entry in data:
                tag = entry['tag_name']
                version_match = self.result["version_match"]
                logging.debug(f"Tag matching? {tag} == {version_match}: {tag.startswith(version_match)}")
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
    
    def _getAsset(self) -> bool:
        for asset in self.release['assets']:
            nameMatch = re.match(self.result.get('object_regex'), asset['name'])
            if nameMatch:
                self.result['name'] = asset['name']

                versionSearch = re.search(r'^[^0-9]*([0-9].*)', self.release['tag_name'])
                if versionSearch:
                    versionNumber = versionSearch.group(1)
                else:
                    versionNumber = self.release['published_at']

                self.result['versionNumber'] = versionNumber

                with open(os.path.join(self.config["workdir"], asset['name']), 'wb') as downloadFile:
                    response = requests.get(asset['browser_download_url'], self.config["headers"])
                    if response.status_code == 200:
                        downloadFile.write(response.content)
                        self.result['file'] = downloadFile.name
                        logging.debug(f"Written file to {downloadFile.name}")
                    else:
                        raise FileNotFoundError("Failed to download the file")
                return True
        raise ValueError("Did not match the asset in the object_regex")

    def _preparePackage(self):
        if not os.path.exists(self.config["workdir"]):
            raise FileNotFoundError(f"Workdir Path not found {self.config['workdir']}")
        if not os.path.exists(self.config["builddir"]):
            raise FileNotFoundError(f"Builddir Path not found {self.config['builddir']}")

        os.makedirs(os.path.join(self.config["workdir"], self.result['repo'], 'usr', 'local', 'bin'))
        # TODO: Does *not* handle compressed files at all.
        os.rename(self.result['file'], os.path.join(self.config["workdir"], self.result['repo'], 'usr', 'local', 'bin', self.result['target_binary']))
        if 'bash' in self.result['autocomplete']:
            os.makedirs(os.path.join(self.config["workdir"], self.result['repo'], 'etc', 'bash_completion.d'))
            with open(os.path.join(self.config["workdir"], self.result['repo'], 'etc', 'bash_completion.d', self.result['target_binary']), 'w') as file:
                file.write(self.result['autocomplete']['bash'])
                file.write("\n")

    def _renderDebPackage(self):
        if self.result['name'].endswith('.deb'):
            self.result["deb_package_filename"] = self.result['name']
            self.result["deb_package"] = os.path.join(self.config["builddir"], self.result['name'])
            os.rename(self.result['file'], self.result["deb_package"])
        else:
            try:
                self._preparePackage()
                os.makedirs(os.path.join(self.config["workdir"], self.result['repo'], 'DEBIAN'))
                with open(os.path.join(self.config["workdir"], self.result['repo'], 'DEBIAN', 'control'), 'w') as file:
                    content = [
                        f"Package:      {self.result['repo']}",
                        f"Version:      {self.result['versionNumber']}",
                        f"Section:      {self.result['suite']}",
                        f"Priority:     {self.result['priority'] or 'optional'}",
                        f"Architecture: {self.result['debian_architecture']}",
                    ]
                    if 'debian_dependencies' in self.result and self.result['debian_dependencies'] != '':
                        content.append(f"Depends:      {self.result['debian_dependencies']}")
                    content.append(f"Maintainer:   {self.result['maintainer']}")
                    content.append(f"Description:  {self.result['description']}")
                    if 'homepage' in self.result and len(self.result['homepage']) > 0:
                        content.append(f"Homepage:     {self.result['homepage']}")
                    for line in content:
                        file.write(f"{line}\n")
                
                target_filename = f"{self.result['repo']}_{self.result['versionNumber']}_{self.result['debian_architecture']}.deb"
                self.result["deb_package_filename"] = target_filename
                self.result["deb_package"] = os.path.join(self.config["builddir"], target_filename)
                cmd = f"dpkg-deb --build {os.path.join(self.config['workdir'], self.result['repo'])} {target_filename}"
                with subprocess.Popen(cmd, cwd=self.config["builddir"], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
                    exit_code = process.wait()
                    stdout = process.stdout.read().decode('utf-8')
                    stderr = process.stderr.read().decode('utf-8')
                    if exit_code > 0:
                        logging.error(f"Build of {self.result['deb_package']} failed")
                        logging.error(f"stdout: {stdout}")
                        logging.error(f"stderr: {stderr}")
                        raise Exception("Build failure")

                    logging.debug(f"Build of {self.result['deb_package']} succeeded")

            except Exception as e:
                print(f"Builddir = '{self.config['builddir']}', Workdir = '{self.config['workdir']}'")
                input("Pausing in-flight to verify issue. Press enter to continue")
                raise e


    def getRelease(self):
        self._getReleaseData()
        self._getAsset()
        if 'deb' in self.result['formats']:
            self._renderDebPackage()
        if os.path.exists(os.path.join(self.config["workdir"], self.result['repo'])):
            shutil.rmtree(os.path.join(self.config["workdir"], self.result['repo']))
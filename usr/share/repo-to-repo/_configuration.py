
import os
import json
import base64
import re
import shutil
import logging
from datetime import datetime
import tempfile
import subprocess

from _exceptions import PGPLoadError, NoConfigurationFileFound, NoTargetPathDefined, ConfigErrorNoRepositories
from _targetRelease import TargetRelease


class Configuration:
    def __init__(self, config_file: str = None, pgp_privatekey_filename: str = None, arguments=None, runtime_config: dict = None):
        self.config_file = os.environ.get('config_file') or config_file
        self.pgp_privatekey_filename = os.environ.get(
            'pgp_key') or pgp_privatekey_filename
        self.arguments = arguments
        if runtime_config is None:
            self.runtime_config = {}
        else:
            self.runtime_config = runtime_config

        if arguments is not None:
            self.runtime_config["quiet"] = arguments.quiet
            self.runtime_config["output_path"] = arguments.output_path
            self.runtime_config["clean"] = arguments.clean
            self.runtime_config["timestamp"] = arguments.timestamp
        else:
            if "quiet" not in self.runtime_config:
                self.runtime_config["quiet"] = False
            if "output_path" not in self.runtime_config:
                self.runtime_config["output_path"] = "/tmp/repo_to_repo"
            if "clean" not in self.runtime_config:
                self.runtime_config["clean"] = False
            if "timestamp" not in self.runtime_config:
                self.runtime_config["timestamp"] = "%Y%m%d%H%M%S"

        basedir = tempfile.TemporaryDirectory().name
        self.runtime_config["basedir"] = basedir

        workdir = os.path.join(basedir, 'workdir')
        os.makedirs(workdir)
        self.runtime_config["workdir"] = workdir

        builddir = os.path.join(basedir, 'builddir')
        os.makedirs(builddir)
        self.runtime_config["builddir"] = builddir

        gnupghome = os.path.join(basedir, 'gnupghome')
        os.makedirs(gnupghome, 0o700)
        self.runtime_config["gnupghome"] = gnupghome
        os.environ['GNUPGHOME'] = gnupghome

        self.parse_pgp_privatekey()

        self.runtime_config["privatekey"] = self.private_key_content

    def load_pgp_privatekey(self):
        process = subprocess.Popen(['gpg', '--import'], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate(self.private_key_content)

        if process.returncode == 0:
            logging.debug("Import successful")
            logging.debug(stdout)
        else:
            logging.error(stderr)
            raise PGPLoadError("Unable to import the GPG key")

        result = subprocess.run(
            ['gpg', '--list-secret-keys', '--keyid-format', 'LONG'], capture_output=True, text=True)
        output_lines = result.stdout.split('\n')

        for line in output_lines:
            re_key_id = re.search(r"^\s*([A-F0-9]{40})\s*$", line)
            re_uid = re.search(r"^uid\s+\[[^\]]+\]\s+(.*)$", line)

            if re_key_id:
                self.runtime_config["privatekey_id"] = re_key_id.group(1)

            if re_uid:
                self.runtime_config["privatekey_uid"] = re_uid.group(1)

    def cleanUp(self):
        if "basedir" in self.runtime_config:
            shutil.rmtree(self.runtime_config["basedir"])

    def parse_pgp_privatekey(self):
        self.private_key_content = os.environ.get('pgp_key_base64') or None
        if self.private_key_content is not None:
            logging.debug("PGP Private Key loaded from environment variable.")
            logging.debug(
                f"PGP Private Key content:\n{self.private_key_content}")
            self.private_key_content = base64.b64decode(
                str(self.private_key_content)).decode() or self.private_key_content
        elif self.pgp_privatekey_filename is None and os.environ.get('pgp_key') is not None:
            self.pgp_privatekey_filename = os.environ.get('pgp_key')
            logging.debug(
                f"PGP Private Key Filename: {self.pgp_privatekey_filename}")
            with open(self.pgp_privatekey_filename, "r") as file:
                self.private_key_content = file.read()
            logging.debug(
                f"PGP Private Key content:\n{self.private_key_content}")
        elif self.pgp_privatekey_filename is not None:
            logging.debug(
                f"PGP Private Key Filename: {self.pgp_privatekey_filename}")
            with open(self.pgp_privatekey_filename, "r") as file:
                self.private_key_content = file.read()
            logging.debug(
                f"PGP Private Key content:\n{self.private_key_content}")
        if self.private_key_content is None or self.private_key_content == '':
            raise PGPLoadError("No private key content supplied.")
        if (
            not self.private_key_content.startswith(
                "-----BEGIN PGP PRIVATE KEY BLOCK-----")
                or
            not self.private_key_content.endswith(
                "-----END PGP PRIVATE KEY BLOCK-----\n")
        ):
            raise PGPLoadError(
                f"Invalid private key content. Got: {self.private_key_content}")

    def get_targets(self):
        if self.config_file is None:
            raise NoConfigurationFileFound("No configuration file found.")
        logging.debug(f"Configuration file: {self.config_file}")
        config = []
        with open(self.config_file, "r") as file:
            for line in file:
                config.append(line.split("//")[0].strip())
        self.configuration = "\n".join(config)
        logging.debug(f"Configuration File content:\n{self.configuration}")

        config: dict = json.loads(self.configuration)
        logging.debug(f"Parsed configuration file into {config}")

        if "path" in config:
            self.runtime_config["path"] = config["path"]
        else:
            raise NoTargetPathDefined("Config Error: No target path specified")

        if self.runtime_config["clean"]:
            self.runtime_config["pathmode"] = None
        else:
            self.runtime_config["pathmode"] = datetime.now().strftime(
                self.runtime_config["timestamp"])

        self.runtime_config["headers"]: dict = {}
        if "headers" in config:
            self.runtime_config["headers"] = config['headers']
        if os.environ.get('GITHUB_TOKEN') is not None and os.environ.get('GITHUB_TOKEN') != '':
            self.runtime_config["headers"].update(
                {"Authorization": os.environ.get('GITHUB_TOKEN')})

        default_architecture = "amd64"
        if "architecture" in config:
            default_architecture = config["architecture"]
        else:
            logging.debug(
                "No default architecture specified in the configuration file; default: amd64")

        default_formats = ["deb", "rpm"]
        if "formats" in config:
            default_formats = config["formats"]
        else:
            logging.debug(
                "No default formats specified in the configuration file; default: ['deb', 'rpm']")

        default_suite = "misc"
        if "suite" in config:
            default_suite = config["suite"]
        else:
            logging.debug(
                "No default suite specified in the configuration file; default: misc")

        default_archive = "main"
        if "archive" in config:
            default_archive = config["archive"]
        else:
            logging.debug(
                "No default archive specified in the configuration file; default: main")

        default_homepage = ""
        if "homepage" in config:
            default_homepage = config["homepage"]
        else:
            logging.debug(
                "No default homepage specified in the configuration file; default: None")

        default_maintainer = ""
        if "maintainer" in config:
            default_maintainer = config["maintainer"]
        else:
            logging.debug(
                "No default maintainer specified in the configuration file; default: None")

        default_description = ""
        if "description" in config:
            default_description = config["description"]
        else:
            logging.debug(
                "No default description specified in the configuration file; default: None")

        default_priority = "optional"
        if "priority" in config:
            default_priority = config["priority"]
        else:
            logging.debug(
                "No default priority specified in the configuration file; default: None")

        self.targets = []

        if "repos" not in config:
            config["repos"] = []

        if len(config["repos"]) == 0:
            raise ConfigErrorNoRepositories("No repositories specified.")

        for this_repo in config["repos"]:

            if "platform" not in this_repo:
                this_repo["platform"] = "github"
            repo_platform = this_repo["platform"]

            if "owner" not in this_repo:
                raise ValueError(
                    f"Config Error: Failure parsing repo - missing owner field. Repo values: {this_repo}")
            repo_owner = this_repo["owner"]

            if "repo" not in this_repo:
                raise ValueError(
                    f"Config Error: Failure parsing repo - missing repo field. Repo values: {this_repo}")
            repo_repo = this_repo["repo"]

            if "target_binary" not in this_repo:
                this_repo["target_binary"] = ""
            repo_target_binary = this_repo["target_binary"]

            if "architecture" not in this_repo:
                this_repo["architecture"] = default_architecture
            repo_architecture = this_repo["architecture"]

            if "formats" not in this_repo:
                this_repo["formats"] = default_formats
            repo_formats = this_repo["formats"]

            if "version_match" not in this_repo:
                this_repo["version_match"] = ""
            repo_version_match = this_repo["version_match"]

            if "autocomplete" not in this_repo:
                this_repo["autocomplete"] = {}
            repo_autocomplete = this_repo["autocomplete"]

            if "suite" not in this_repo:
                this_repo["suite"] = default_suite
            repo_suite = this_repo["suite"]

            if "archive" not in this_repo:
                this_repo["archive"] = default_archive
            repo_archive = this_repo["archive"]

            if "homepage" not in this_repo:
                this_repo["homepage"] = default_homepage
            if this_repo["homepage"] == '':
                this_repo["homepage"] = f"https://github.com/{this_repo['owner']}/{this_repo['repo']}"
            repo_homepage = this_repo["homepage"]

            if "maintainer" not in this_repo:
                this_repo["maintainer"] = default_maintainer
            if this_repo["maintainer"] == '':
                this_repo["maintainer"] = f"{this_repo['owner']} <{this_repo['owner']}@users.noreply.github.com>"
            repo_maintainer = this_repo["maintainer"]

            if "description" not in this_repo:
                this_repo["description"] = default_description
            if this_repo["description"] == '':
                this_repo[
                    "description"] = f"A repo-to-repo package of a release at https://github.com/{this_repo['owner']}/{this_repo['repo']}"
            repo_description = this_repo["description"]

            if "priority" not in this_repo:
                this_repo["priority"] = default_priority
            repo_priority = this_repo["priority"]

            if "debian_dependencies" not in this_repo:
                this_repo["debian_dependencies"] = ""
            repo_debian_dependencies = this_repo["debian_dependencies"]

            if "redhat_dependencies" not in this_repo:
                this_repo["redhat_dependencies"] = ""
            repo_redhat_dependencies = this_repo["redhat_dependencies"]

            if "targets" not in this_repo:
                if repo_target_binary == '':
                    raise ValueError(
                        f"Config Error: Failure parsing repo - missing target_binary field. Repo values: {this_repo}"
                    )
                else:
                    self.targets.append(
                        TargetRelease(
                            {
                                "owner": repo_owner,
                                "repo": repo_repo,
                                "target_binary": repo_target_binary,
                                "autocomplete": repo_autocomplete,
                                "suite": repo_suite,
                                "archive": repo_archive,
                                "formats": repo_formats,
                                "homepage": repo_homepage,
                                "maintainer": repo_maintainer,
                                "description": repo_description,
                                "priority": repo_priority,
                                "architecture": repo_architecture,
                                "debian_dependencies": repo_debian_dependencies,
                                "redhat_dependencies": repo_redhat_dependencies,
                                "version_match": repo_version_match,
                                "object_regex": repo_target_binary,
                                "platform": repo_platform
                            },
                            self.runtime_config
                        )
                    )
            else:
                for target in this_repo["targets"]:
                    if "object_regex" not in target:
                        target_object_regex = repo_target_binary
                    else:
                        target_object_regex = target["object_regex"]

                    if "formats" not in target:
                        target_formats = repo_formats
                    else:
                        target_formats = target["formats"]

                    if "architecture" not in target:
                        target_architecture = repo_architecture
                    else:
                        target_architecture = target["architecture"]

                    if "version_match" not in target:
                        target_version_match = repo_version_match
                    else:
                        target_version_match = target["version_match"]

                    if "homepage" not in target:
                        target_homepage = repo_homepage
                    else:
                        target_homepage = target["homepage"]

                    if "maintainer" not in target:
                        target_maintainer = repo_maintainer
                    else:
                        target_maintainer = target["maintainer"]

                    if "description" not in target:
                        target_description = repo_description
                    else:
                        target_description = target["description"]

                    if "priority" not in target:
                        target_priority = repo_priority
                    else:
                        target_priority = target["priority"]

                    if "debian_dependencies" not in target:
                        target_debian_dependencies = repo_debian_dependencies
                    else:
                        target_debian_dependencies = target["debian_dependencies"]

                    if "redhat_dependencies" not in target:
                        target_redhat_dependencies = repo_redhat_dependencies
                    else:
                        target_redhat_dependencies = target["redhat_dependencies"]

                    if repo_target_binary == '' and not (target_object_regex.endswith('.deb') or target_object_regex.endswith('.rpm')):
                        raise ValueError(
                            f"Config Error: Failure parsing repo - missing target_binary field. Repo values: {this_repo}"
                        )
                    else:
                        self.targets.append(
                            TargetRelease(
                                {
                                    "owner": repo_owner,
                                    "repo": repo_repo,
                                    "target_binary": repo_target_binary,
                                    "autocomplete": repo_autocomplete,
                                    "suite": repo_suite,
                                    "archive": repo_archive,
                                    "formats": target_formats,
                                    "homepage": target_homepage,
                                    "maintainer": target_maintainer,
                                    "description": target_description,
                                    "priority": target_priority,
                                    "architecture": target_architecture,
                                    "debian_dependencies": target_debian_dependencies,
                                    "redhat_dependencies": target_redhat_dependencies,
                                    "version_match": target_version_match,
                                    "object_regex": target_object_regex,
                                    "platform": repo_platform
                                },
                                self.runtime_config
                            )
                        )
        logging.debug(f"Built list of targets: {self.targets}")

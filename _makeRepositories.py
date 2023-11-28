import bz2
import gzip
import hashlib
import logging
import os
import shutil

from datetime import datetime, timezone
import subprocess

from _targetRelease import TargetRelease

class MakeRepository:
    def __init__(self, runtime_config):
        self.runtime_config = runtime_config
        if self.runtime_config["pathmode"] is None:
            shutil.rmtree(self.runtime_config["path"])

    def finalize(self):
        if self.runtime_config["pathmode"] is not None:
            if os.path.exists(
                os.path.join(
                    self.runtime_config["path"],
                    "latest"
                )
            ):
                os.remove(
                    os.path.join(
                        self.runtime_config["path"],
                        "latest"
                    )
                )

            os.symlink(
                src=self.runtime_config["pathmode"],
                dst=os.path.join(
                    self.runtime_config["path"],
                    "latest"
                )
            )

class MakeDebRepository:
    def __init__(self, targets, runtime_config):
        target: TargetRelease = None
        suites_and_archives = {}
        for target in targets:
            asset = target.result
            if asset['suite'] not in suites_and_archives:
                suites_and_archives[asset['suite']] = {}
            if asset['archive'] not in suites_and_archives[asset['suite']]:
                suites_and_archives[asset['suite']][asset['archive']] = []
            if asset['debian_architecture'] not in suites_and_archives[asset['suite']][asset['archive']]:
                suites_and_archives[asset['suite']][asset['archive']].append(asset['debian_architecture'])

            if runtime_config["pathmode"] is None:
                target_path = target.path
            else:
                target_path = os.path.join(
                    runtime_config["path"],
                    runtime_config["pathmode"]
                )

            pool_dir = os.path.join(
                target_path,
                'deb',
                'pool',
                asset['suite'],
                asset['archive']
            )
            if not os.path.exists(pool_dir):
                os.makedirs(pool_dir)

            os.rename(target.result['deb_package'], os.path.join(pool_dir, target.result['deb_package_filename']))

        for suite in suites_and_archives:
            arch_list = []
            for archive in suites_and_archives[suite]:
                for architecture in suites_and_archives[suite][archive]:
                    if architecture not in arch_list:
                        arch_list.append(architecture)
                    result = subprocess.run(
                        ['dpkg-scanpackages', '--arch', architecture, os.path.join("pool", suite, archive)],
                        capture_output=True, text=True, cwd=os.path.join(target_path, "deb")
                    )
                    content = result.stdout
                    logging.debug(f'In {os.path.join(target_path, "deb")}, running the command {" ".join(result.args)}')
                    logging.debug(f'Return Code: {result.returncode}')
                    logging.debug(f'stderr: {result.stderr}')
                    logging.debug(f'stdout: {result.stdout}')
                    if len(content) > 0:
                        index_dir = os.path.join(
                            target_path,
                            'deb',
                            'dists',
                            suite,
                            archive,
                            f"binary-{architecture}"
                        )
                        packages_file = os.path.join(index_dir, "Packages")
                        if not os.path.exists(index_dir):
                            os.makedirs(index_dir)
                        with open(packages_file, 'w') as file:
                            file.write(content)
                        with gzip.open(f'{packages_file}.gz', 'wb', compresslevel=9) as file:
                            file.write(content.encode())
                        with bz2.open(f'{packages_file}.bz2', 'wb', compresslevel=9) as file:
                            file.write(content.encode())

            content = [
                f"Suite: {suite}",
                f"Codename: {suite}",
                f"Architectures: {' '.join(arch_list)}",
                f"Components: {' '.join(suites_and_archives[suite])}",
                 "Description: A repo-to-repo built collection of packages",
                f"Date: {datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S %z')}",
            ]
            hash_types = {"MD5Sum": "md5", "SHA1": "sha1", "SHA256": "sha256", "SHA512": "sha512"}
            for key in hash_types:
                content.append(f'{key}:')
                for root, _, list_of_files in os.walk(os.path.join(target_path, "deb", "dists", suite)):
                    for hashable_file in list_of_files:
                        if not hashable_file.endswith("Release"):
                            file_path = os.path.join(root, hashable_file)
                            file_path_label = file_path.replace(f'{os.path.join(target_path, "deb", "dists", suite)}/', "")
                            with open(file_path, 'rb') as f:
                                file_content = f.read()
                                hash_value = hashlib.new(hash_types[key], file_content).hexdigest()
                                file_size = os.path.getsize(file_path)
                                content.append(f" {hash_value} {file_size} {file_path_label}")

            with open(os.path.join(target_path, "deb", "dists", suite, "Release"), 'w') as file:
                for line in content:
                    file.write(f"{line}\n")
            
            self._sign_file(
                os.path.join(target_path, "deb", "dists", suite, "Release"),
                os.path.join(target_path, "deb", "dists", suite, "Release.gpg")
            )
            
            self._sign_file(
                os.path.join(target_path, "deb", "dists", suite, "Release"),
                os.path.join(target_path, "deb", "dists", suite, "InRelease"),
                clearsign=True
            )

    def _sign_file(self, input_file, output_file, clearsign=False):
        command = ['gpg', '--detach-sign', '--armor', '--sign']
        
        if clearsign:
            command.append('--clearsign')
        
        with open(input_file, 'rb') as input_data, open(output_file, 'wb') as output_data:
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=output_data)
            process.communicate(input_data.read())

class MakeRPMRepository:
    def __init__(self, targets):
        print("TODO: Make RPM Repo")

import os
import shutil

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
                os.path.join(
                    self.runtime_config["path"],
                    self.runtime_config["pathmode"]
                ),
                os.path.join(
                    self.runtime_config["path"],
                    "latest"
                )
            )

class MakeDebRepository:
    def __init__(self, targets, runtime_config):
        target: TargetRelease = None
        owner: str = runtime_config["privatekey_uid"]
        architectures = []
        suites_and_archives = []
        for target in targets:

            print(target)
            asset = target.result
            if asset['debian_architecture'] not in architectures:
                architectures.append(asset['debian_architecture'])
            if os.path.join(asset['suite'], asset['archive']) not in suites_and_archives:
                suites_and_archives.append(os.path.join(asset['suite'], asset['archive']))

            if runtime_config["pathmode"] is None:
                target_path = target.path
            else:
                target_path = os.path.join(
                    runtime_config["path"],
                    runtime_config["pathmode"]
                )
                
            index_dir = os.path.join(
                target_path,
                'deb',
                'dists',
                asset['suite'],
                asset['archive'],
                f"binary-{asset['debian_architecture']}"
            )
            if not os.path.exists(index_dir):
                os.makedirs(index_dir)

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

        for suite_and_archive in suites_and_archives:
            for architecture in architectures:
                # TODO: Actually make this happen.
                packages_file = os.path.join(target_path, "deb", "dists", suite_and_archive, f"binary-{asset['debian_architecture']}", "Packages")
                print(f'dpkg-scanpackages --help --arch {architecture} "pool/{suite_and_archive}" > "{packages_file}"')
                print(f'gzip -9 > "{packages_file}.gz" < "{packages_file}"')
                print(f'bzip2 -9 > "{packages_file}.bz2" < "{packages_file}"')
                # TODO: Make release file.
                # {
                #     echo "Origin: ${ORIGIN}"
                #     echo "Label: ${REPO_OWNER}"
                #     echo "Suite: ${SUITE:-stable}"
                #     echo "Codename: ${SUITE:-stable}"
                #     echo "Version: 1.0"
                #     echo "Architectures: all"
                #     echo "Components: ${COMPONENTS:-main}" # list of "archives" ffffff
                #     echo "Description: ${DESCRIPTION:-A repository for packages released by ${REPO_OWNER}}"
                #     echo "Date: $(date -Ru)"
                #     generate_hashes MD5Sum md5sum
                #     generate_hashes SHA1 sha1sum
                #     generate_hashes SHA256 sha256sum
                # } > os.path.join(target_path, "deb", "dists", suite, "Release")
                # TODO: Sign the release file
                # gpg --detach-sign --armor --sign > Release.gpg < Release
                # gpg --detach-sign --armor --sign --clearsign > InRelease < Release


class MakeRPMRepository:
    def __init__(self, targets):
        print("TODO: Make RPM Repo")

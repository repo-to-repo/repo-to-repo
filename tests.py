import json
import unittest
from unittest.mock import patch
import tempfile
import os

from repo_to_repo import Configuration
from _exceptions import PGPKeyFileNotFoundError


class AllTests(unittest.TestCase):
    def setUp(self):
        self.config_file_with_off_policy_archive = json.dumps(
            {"path": "/tmp", "archive": "blob", "repos": [{"owner": "test", "repo": "test", "target_binary": "test"}]})
        self.config_file_with_off_policy_suite = json.dumps(
            {"path": "/tmp", "suite": "postbox", "repos": [{"owner": "test", "repo": "test", "target_binary": "test"}]})
        self.config_file_with_off_policy_architecture = json.dumps(
            {"path": "/tmp", "architecture": "pdp12", "repos": [{"owner": "test", "repo": "test", "target_binary": "test"}]})
        self.config_file_with_unmanaged_autocomplete = json.dumps(
            {"path": "/tmp", "repos": [{"owner": "test", "repo": "test", "target_binary": "test", "autocomplete": {"tcsh": "do something here"}}]})
        self.minimal_config = json.dumps(
            {"path": "/tmp", "repos": [{"owner": "test", "repo": "test", "target_binary": "test"}]})
        self.small_config = json.dumps(
            {"path": "/tmp", "repos": [{"owner": "test", "repo": "test", "target_binary": "test", "targets": [{}]}]})
        self.complete_config = json.dumps({
            "path": "/tmp",
            "formats": ["deb", "rpm"],
            "architecture": "amd64",
            "suite": "misc",
            "archive": "main",
            "repos": [
                {
                    "autocomplete": {
                        "bash": "some_autocomplete_script"
                    },
                    "owner": "test",
                    "repo": "test",
                    "target_binary": "test",
                    "targets": [
                        {
                            "formats": ["deb"],
                            "architecture": "arm64",
                            "object_regex": "test_v*_arm64.tar.gz"
                        }
                    ]
                }
            ]
        })
        self.valid_pgp_block = b"-----BEGIN PGP PRIVATE KEY BLOCK-----\nDEMO PGP CONTENT HERE\n-----END PGP PRIVATE KEY BLOCK-----\n"


class TestTargets(AllTests):
    @patch('logging.warning')
    def test_archive_warning_logged(self, mock_warning):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(
                self.config_file_with_off_policy_archive.encode())
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        Configuration(config_file.name, pgp_file.name)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

        # Check if logging.warning was called
        mock_warning.assert_called_once_with(
            "Archive ('blob') is not, but should be, one of the valid archives from the list in the [Debian Policy](https://www.debian.org/doc/debian-policy/ch-archive.html#archive-areas). Ensure you're comfortable with this before publishing.")

    @patch('logging.warning')
    def test_suite_warning_logged(self, mock_warning):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(
                self.config_file_with_off_policy_suite.encode())
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        Configuration(config_file.name, pgp_file.name)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

        # Check if logging.warning was called
        mock_warning.assert_called_once_with(
            "suite ('postbox') is not, but should be, one of the valid suites from the list in the [Debian Policy](https://www.debian.org/doc/debian-policy/ch-archive.html#s-subsections). Ensure you're comfortable with this before publishing.")

    @patch('logging.warning')
    def test_architecture_warning_logged(self, mock_warning):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(
                self.config_file_with_off_policy_architecture.encode())
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        Configuration(config_file.name, pgp_file.name)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

        # Check if logging.warning was called
        mock_warning.assert_called_once_with(
            "architecture ('pdp12') is not, but should be, one of ('noarch' == 'all' == 'any'), ('x86-64' == 'amd64'), or ('arm64' == 'aarch64') due to architecture mapping. [Pull requests, welcome!](https://github.com/repo-to-repo/repo-to-repo)")

    @patch('logging.warning')
    def test_autocomplete_warning_logged(self, mock_warning):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(
                self.config_file_with_unmanaged_autocomplete.encode())
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        Configuration(config_file.name, pgp_file.name)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

        # Check if logging.warning was called
        mock_warning.assert_called_once_with(
            "You have specified shells in autocomplete which are not currently handled (['tcsh']). These won't be actioned. [Pull requests, welcome!](https://github.com/repo-to-repo/repo-to-repo)")


class TestConfiguration(AllTests):
    def test_valid_config_file_parse(self):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(self.minimal_config.encode())
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        config = Configuration(config_file.name, pgp_file.name)
        self.assertEqual(len(config.targets), 1)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

    def test_valid_config_file_parse_longer(self):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(self.small_config.encode())
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        config = Configuration(config_file.name, pgp_file.name)
        self.assertEqual(len(config.targets), 1)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

    def test_valid_config_file_parse_complete(self):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(self.complete_config.encode())
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        config = Configuration(config_file.name, pgp_file.name)
        self.assertEqual(len(config.targets), 1)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

    def test_no_files_supplied(self):
        with self.assertRaises(ValueError):
            Configuration()

    def test_config_file_not_found(self):
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        with self.assertRaises(FileNotFoundError):
            Configuration("/nonexistent_file.json", pgp_file.name)
        os.remove(pgp_file.name)

    def test_config_file_parse_error(self):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(b"invalid json")
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(b"pgp_key")
        with self.assertRaises(ValueError):
            Configuration(config_file.name, pgp_file.name)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

    def test_pgp_file_not_found(self):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(b"{}")
        with self.assertRaises(FileNotFoundError):
            Configuration(config_file.name, "/nonexistent_file.asc")
        os.remove(config_file.name)

    def test_config_file_and_pgp_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            Configuration("/nonexistent_file.json", "/nonexistent_file.asc")

    def test_pgp_key_base64(self):
        # Set the pgp_key_base64 environment variable
        os.environ['pgp_key_base64'] = 'LS0tLS1CRUdJTiBQR1AgUFJJVkFURSBLRVkgQkxPQ0stLS0tLQpERU1PIFBHUCBDT05URU5UIEhFUkUKLS0tLS1FTkQgUEdQIFBSSVZBVEUgS0VZIEJMT0NLLS0tLS0K'

        # Run the Configuration initialization
        config = Configuration(config_file='config.json')

        # Assert that the private_key_content is correctly loaded
        self.assertEquals(str(config.private_key_content),
                          self.valid_pgp_block.decode())

        # Clean up the environment variable
        del os.environ['pgp_key_base64']

    def test_pgp_key(self):
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        # Set the pgp_key environment variable
        os.environ['pgp_key'] = pgp_file.name

        # Run the Configuration initialization
        config = Configuration(config_file='config.json')

        # Assert that the private_key_content is correctly loaded
        self.assertEquals(str(config.private_key_content),
                          self.valid_pgp_block.decode())

        # Clean up the environment variable
        del os.environ['pgp_key']

    def test_config_file_parse_no_path(self):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(b'{"architecture": "amd64", "repos": []}')
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        with self.assertRaises(ValueError):
            Configuration(config_file.name, pgp_file.name)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

    def test_config_file_parse_no_path(self):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(b'{}')
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(b"pgp_key")
        with self.assertRaises(ValueError):
            Configuration(config_file.name, pgp_file.name)
        os.remove(config_file.name)
        os.remove(pgp_file.name)

    def test_config_file_parse_no_repos(self):
        with tempfile.NamedTemporaryFile(delete=False) as config_file:
            config_file.write(b'{"path": "/tmp", "architecture": "amd64"}')
        with tempfile.NamedTemporaryFile(delete=False) as pgp_file:
            pgp_file.write(self.valid_pgp_block)
        with self.assertRaises(ValueError):
            Configuration(config_file.name, pgp_file.name)
        os.remove(config_file.name)
        os.remove(pgp_file.name)


if __name__ == "__main__":
    unittest.main()

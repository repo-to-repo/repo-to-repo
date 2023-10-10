import os
import gnupg
import logging
import tempfile

class MissingEnvironmentVariableError(Exception):
    def __init__(self, variable_name):
        self.variable_name = variable_name
        self.message = f"The environment variable '{variable_name}' is missing."

class FailedToImportGPGKey(Exception):
    def __init__(self, variable_name):
        self.variable_name = variable_name
        self.message = "Failed to import the supplied GPG Private Key."

class ConsolidateConfig:
    def __init__(self, config, args, tempdir):
        self.config={
            "tempdir": tempdir,
            "workdir": tempdir,
            "architecture": 'all'
        }

        for arg_name in config:
            logging.debug(f"Config: {arg_name}: {config[arg_name]}")
            self.config[arg_name] = config[arg_name]

        for arg_name, arg_value in vars(args).items():
            if arg_value != 'UNDEF':
                logging.debug(f"Argument: {arg_name}: {arg_value}")
                if arg_name in self.config:
                    logging.debug(f"Argument {arg_name} overrides existing config value.")
                self.config[arg_name] = arg_value
        if os.environ.get('GH_PAT') is not None:
            self.config['headers'] = {'Authorization': f"Bearer {os.environ.get('GH_PAT')}"}

        if 'deb_architecture' not in self.config:
            self.config['deb_architecture'] = self.config['architecture']
            if self.config['architecture'] == 'x86_64':
                self.config['deb_architecture'] = 'amd64'
        
        if 'rpm_architecture' not in self.config:
            self.config['rpm_architecture'] = self.config['architecture']
            if self.config['architecture'] == 'all':
                self.config['rpm_architecture'] = 'noarch'

        if os.environ.get('PRIVATE_KEY') is not None:
            self.config['gpg_key'] = os.environ.get('PRIVATE_KEY')
        elif 'private_key' in self.config and self.config['private_key'] is not None:
            with open(self.config['private_key'], 'r') as file:
                self.config['gpg_key'] = file.read()
        else:
            raise MissingEnvironmentVariableError('PRIVATE_KEY')
        
        try:
            logging.debug("Loading GPG")
            gnupghome=tempfile.TemporaryDirectory(dir=tempdir).name
            os.makedirs(gnupghome, mode=0o700, exist_ok=True)
            self.config['gpg'] = gnupg.GPG(gnupghome=gnupghome)

            logging.debug("Importing key")
            gpg_key = self.config.get('gpg_key')
            import_result = self.config['gpg'].import_keys(gpg_key)
            
            if import_result.count == 1:
                logging.debug("Imported private key ready for signing.")
            else:
                raise FailedToImportGPGKey
        except BaseException as e:
            raise e

    def exists(self, key: str) -> bool:
        if key in self.config:
            return True
        return False
    
    def put(self, key: str, value: str):
        self.config[key] = value

    def get(self, key: str, default: str='UNDEF') -> str:
        if key in self.config:
            return self.config[key]
        if default != 'UNDEF':
            return default
        logging.debug("About to raise a LookupError. The following is the consolidated configuration values.")
        logging.debug(self.config)
        raise LookupError(f"Did not find key {key} in consolidated configuration values.")
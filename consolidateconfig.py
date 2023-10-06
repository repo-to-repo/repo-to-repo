import logging

class ConsolidateConfig:
    def __init__(self, config, args, tempdir):
        self.configValues={
            "tempdir": tempdir,
            "workdir": tempdir,
            "architecture": 'amd64'
        }
        for arg_name in config:
            logging.debug(f"Config: {arg_name}: {config[arg_name]}")
            self.configValues[arg_name] = config[arg_name]
        for arg_name, arg_value in vars(args).items():
            if arg_value != 'UNDEF':
                logging.debug(f"Argument: {arg_name}: {arg_value}")
                if arg_name in self.configValues:
                    logging.debug(f"Argument {arg_name} overrides existing config value.")
                self.configValues[arg_name] = arg_value

    def exists(self, key: str) -> bool:
        if key in self.configValues:
            return True
        return False
    
    def put(self, key: str, value: str):
        self.configValues[key] = value

    def get(self, key: str, default: str='UNDEF') -> str:
        if key in self.configValues:
            return self.configValues[key]
        if default != 'UNDEF':
            return default
        logging.debug("About to raise a LookupError. The following is the consolidated configuration values.")
        logging.debug(self.configValues)
        raise LookupError(f"Did not find key {key} in consolidated configuration values.")
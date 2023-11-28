class RepoTargetInvalidValue(Exception):
    pass

class RepoTargetMissingValue(Exception):
    pass

class GithubApiNotAvailable(Exception):
    pass

class PGPKeyFileNotFoundError(Exception):
    pass

class PGPLoadError(Exception):
    pass

class NoConfigurationFileFound(ValueError):
    pass

class NoTargetPathDefined(ValueError):
    pass

class ConfigErrorNoRepositories(ValueError):
    pass
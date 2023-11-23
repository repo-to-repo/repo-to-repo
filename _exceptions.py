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
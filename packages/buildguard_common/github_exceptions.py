from typing import Optional, Union


class GithubError(Exception):
    pass


class GithubConfigurationError(GithubError):
    pass


class GithubRateLimitError(GithubError):
    def __init__(self, message: str, retry_after: Union[int, float, None] = None):
        super().__init__(message)
        self.retry_after = retry_after


class GithubRetryableError(GithubError):
    pass


class GithubAllRateLimitError(GithubError):

    def __init__(self, message: str, retry_after: Union[int, float, None] = None):
        super().__init__(message)
        self.retry_after = retry_after

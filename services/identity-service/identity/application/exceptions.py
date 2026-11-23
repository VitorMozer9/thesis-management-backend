class InvalidCredentialsError(Exception):
    pass


class TooManyLoginAttemptsError(Exception):
    pass


class TokenServiceUnavailableError(Exception):
    pass


class InvalidAccessTokenError(Exception):
    pass

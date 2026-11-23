class InvalidCredentialsError(Exception):
    pass


class TooManyLoginAttemptsError(Exception):
    pass


class TokenServiceUnavailableError(Exception):
    pass


class InvalidAccessTokenError(Exception):
    pass


class AdministrationDeniedError(Exception):
    pass


class AccountNotFoundError(Exception):
    pass


class AdministrationConflictError(Exception):
    pass

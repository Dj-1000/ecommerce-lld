class AuthenticationError(Exception):
    """Base authentication exception."""


class InvalidCredentialsError(AuthenticationError):
    """Raised when email/password authentication fails."""


class AccountLockedError(AuthenticationError):
    """Raised when login is temporarily blocked."""
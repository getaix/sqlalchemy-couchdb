"""
Exception classes for CouchDB dialect.

Implements DB-API 2.0 exception hierarchy.
"""


class CouchDBError(Exception):
    """Base exception for all CouchDB-related errors."""

    pass


# DB-API 2.0 required exception - alias for compatibility
Error = CouchDBError


class Warning(CouchDBError):
    """Exception raised for important warnings."""

    pass


class InterfaceError(CouchDBError):
    """
    Exception raised for errors related to the database interface.

    Examples:
    - Invalid connection parameters
    - Interface protocol errors
    - Driver initialization errors
    """

    pass


class DatabaseError(CouchDBError):
    """
    Exception raised for errors related to the database.

    Base class for all database-specific errors.
    """

    pass


class OperationalError(DatabaseError):
    """
    Exception raised for operational errors.

    Examples:
    - Connection failures
    - Network timeouts
    - Authentication errors
    - Database not found
    """

    pass


class ProgrammingError(DatabaseError):
    """
    Exception raised for programming errors.

    Examples:
    - Invalid SQL syntax
    - Unsupported SQL features
    - Invalid parameters
    """

    pass


class IntegrityError(DatabaseError):
    """
    Exception raised for data integrity errors.

    Examples:
    - Document conflicts (_rev mismatch)
    - Constraint violations
    - Duplicate keys
    """

    pass


class DataError(DatabaseError):
    """
    Exception raised for data errors.

    Examples:
    - Type conversion failures
    - Invalid JSON
    - Malformed data
    """

    pass


class NotSupportedError(DatabaseError):
    """
    Exception raised for unsupported operations.

    Examples:
    - Transactions (rollback)
    - JOIN operations
    - GROUP BY without views
    - Foreign keys
    """

    pass


class InternalError(DatabaseError):
    """
    Exception raised for internal database errors.

    Examples:
    - CouchDB server errors
    - Unexpected responses
    - Internal state corruption
    """

    pass


# Convenience function for creating exceptions from HTTP responses
def exception_from_response(response, default_message=None):
    """
    Create appropriate exception from HTTP response.

    Args:
        response: httpx.Response object or status code integer
        default_message: Default error message (optional)

    Returns:
        Exception instance

    Examples:
        >>> response.status_code == 404
        >>> raise exception_from_response(response)  # OperationalError: Document not found
    """
    # Handle None response
    if response is None:
        return DatabaseError(default_message or "No response object")

    # Handle case where response is an integer (status code)
    if isinstance(response, int):
        status_code = response
        error_msg = default_message or f"HTTP {status_code}"
    else:
        status_code = response.status_code
        error_msg = f"HTTP {status_code}: {response.text}"

    # 状态码映射
    if status_code == 401:
        return OperationalError(f"Authentication failed: {error_msg}")
    elif status_code == 404:
        return OperationalError(f"Resource not found: {error_msg}")
    elif status_code == 409:
        return IntegrityError(f"Document conflict: {error_msg}")
    elif status_code == 412:  # Precondition Failed
        return IntegrityError(f"Precondition failed: {error_msg}")
    elif status_code == 400:
        return ProgrammingError(f"Bad request: {error_msg}")
    elif status_code == 503:  # Service Unavailable
        return OperationalError(f"Service unavailable: {error_msg}")
    elif status_code >= 500:
        return InternalError(f"Server error: {error_msg}")
    else:
        return DatabaseError(error_msg)

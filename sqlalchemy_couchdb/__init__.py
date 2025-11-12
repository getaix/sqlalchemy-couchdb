"""
SQLAlchemy CouchDB Dialect

A powerful SQLAlchemy 2.0+ dialect for CouchDB with async support
and hybrid database architecture.

Features:
- Full SQLAlchemy 2.0+ Dialect implementation
- Sync and async operations
- SQL to Mango Query compilation
- Hybrid database architecture (CouchDB + any RDBMS)
- Intelligent query routing
- Dual-write synchronization

Usage:
    # Phase 1: Pure CouchDB mode
    from sqlalchemy import create_engine
    engine = create_engine('couchdb://user:pass@localhost:5984/mydb')

    # Async
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine('couchdb+async://user:pass@localhost:5984/mydb')

    # Phase 2: Hybrid mode
    engine = create_engine(
        'couchdb+hybrid://user:pass@localhost:5984/mydb'
        '?secondary_db=postgresql://user:pass@localhost:5432/mydb'
    )
"""

from sqlalchemy_couchdb.dialect import CouchDBDialect, AsyncCouchDBDialect
from sqlalchemy_couchdb.exceptions import (
    CouchDBError,
    DatabaseError,
    OperationalError,
    ProgrammingError,
    IntegrityError,
    NotSupportedError,
    DataError,
    InternalError,
)
from sqlalchemy_couchdb.helpers import bulk_insert, async_bulk_insert

__version__ = "0.1.3"
__author__ = "getaix"
__license__ = "MIT"

__all__ = [
    # Dialects
    "CouchDBDialect",
    "AsyncCouchDBDialect",
    # Exceptions
    "CouchDBError",
    "DatabaseError",
    "OperationalError",
    "ProgrammingError",
    "IntegrityError",
    "NotSupportedError",
    "DataError",
    "InternalError",
    # Helpers
    "bulk_insert",
    "async_bulk_insert",
]

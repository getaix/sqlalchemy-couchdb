"""
DBAPI 2.0 模块接口

提供符合 DB-API 2.0 规范的连接工厂函数和类型对象。
"""

from sqlalchemy_couchdb.dbapi.base import (
    apilevel,
    threadsafety,
    paramstyle,
    STRING,
    BINARY,
    NUMBER,
    DATETIME,
    ROWID,
)
from sqlalchemy_couchdb.dbapi.sync import Connection, Cursor
from sqlalchemy_couchdb.dbapi.async_ import AsyncConnection, AsyncCursor
from sqlalchemy_couchdb.client import SyncCouchDBClient, AsyncCouchDBClient

# 导入异常类 (DB-API 2.0 要求)
from sqlalchemy_couchdb.exceptions import (
    Warning,
    Error,
    DatabaseError,
    OperationalError,
    ProgrammingError,
    IntegrityError,
    DataError,
    NotSupportedError,
    InternalError,
)


def connect(
    host: str = "localhost",
    port: int = 5984,
    username: str = None,
    password: str = None,
    database: str = None,
    **kwargs,
) -> Connection:
    """
    创建同步数据库连接

    参数:
        host: CouchDB 服务器地址
        port: CouchDB 服务器端口
        username: 用户名
        password: 密码
        database: 数据库名
        **kwargs: 其他参数

    返回:
        Connection 实例

    示例:
        >>> conn = connect(
        ...     host='localhost',
        ...     port=5984,
        ...     username='admin',
        ...     password='password',
        ...     database='mydb'
        ... )
        >>> cursor = conn.cursor()
        >>> cursor.execute("SELECT ...")
    """
    client = SyncCouchDBClient(
        host=host, port=port, username=username, password=password, database=database, **kwargs
    )
    client.connect()
    return Connection(client)


async def async_connect(
    host: str = "localhost",
    port: int = 5984,
    username: str = None,
    password: str = None,
    database: str = None,
    **kwargs,
) -> AsyncConnection:
    """
    创建异步数据库连接

    参数:
        host: CouchDB 服务器地址
        port: CouchDB 服务器端口
        username: 用户名
        password: 密码
        database: 数据库名
        **kwargs: 其他参数

    返回:
        AsyncConnection 实例

    示例:
        >>> conn = await async_connect(
        ...     host='localhost',
        ...     port=5984,
        ...     username='admin',
        ...     password='password',
        ...     database='mydb'
        ... )
        >>> cursor = conn.cursor()
        >>> await cursor.execute("SELECT ...")
    """
    client = AsyncCouchDBClient(
        host=host, port=port, username=username, password=password, database=database, **kwargs
    )
    await client.connect()
    return AsyncConnection(client)


__all__ = [
    # 模块属性
    "apilevel",
    "threadsafety",
    "paramstyle",
    # 类型对象
    "STRING",
    "BINARY",
    "NUMBER",
    "DATETIME",
    "ROWID",
    # 同步接口
    "Connection",
    "Cursor",
    "connect",
    # 异步接口
    "AsyncConnection",
    "AsyncCursor",
    "async_connect",
]

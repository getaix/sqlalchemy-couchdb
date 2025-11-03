"""
pytest 配置和共享 fixtures
"""

import pytest
import asyncio
from typing import Dict, Any

# ==================== 测试配置 ====================

# CouchDB 测试服务器配置
TEST_CONFIG = {
    "host": "localhost",
    "port": 5984,
    "username": "admin",
    "password": "123456",
    "database": "test_db",
    "use_ssl": False,
}


# ==================== Pytest 配置 ====================


def pytest_configure(config):
    """pytest 配置钩子"""
    # 注册自定义标记
    config.addinivalue_line("markers", "unit: 单元测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "sync: 同步模式测试")
    config.addinivalue_line("markers", "async: 异步模式测试")
    config.addinivalue_line("markers", "slow: 慢速测试")


# ==================== 异步支持 ====================


@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环供整个测试会话使用"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# ==================== 同步客户端 Fixtures ====================


@pytest.fixture
def sync_client():
    """创建同步 CouchDB 客户端"""
    from sqlalchemy_couchdb.client import SyncCouchDBClient

    client = SyncCouchDBClient(**TEST_CONFIG)
    client.connect()

    yield client

    # 清理
    client.close()


@pytest.fixture
def sync_client_with_db(sync_client):
    """创建同步客户端并确保测试数据库存在"""
    # 创建数据库（如果不存在）
    try:
        sync_client.create_database()
    except Exception:
        # 数据库已存在，清空数据
        pass

    yield sync_client

    # 清理：删除所有测试文档
    try:
        docs = sync_client.find(selector={"_id": {"$gt": None}})
        for doc in docs:
            sync_client.delete_document(doc["_id"], doc["_rev"])
    except Exception:
        pass


# ==================== 异步客户端 Fixtures ====================


@pytest.fixture
async def async_client():
    """创建异步 CouchDB 客户端"""
    from sqlalchemy_couchdb.client import AsyncCouchDBClient

    client = AsyncCouchDBClient(**TEST_CONFIG)
    await client.connect()

    yield client

    # 清理
    await client.close()


@pytest.fixture
async def async_client_with_db(async_client):
    """创建异步客户端并确保测试数据库存在"""
    # 创建数据库（如果不存在）
    try:
        await async_client.create_database()
    except Exception:
        pass

    yield async_client

    # 清理
    try:
        docs = await async_client.find(selector={"_id": {"$gt": None}})
        for doc in docs:
            await async_client.delete_document(doc["_id"], doc["_rev"])
    except Exception:
        pass


# ==================== DBAPI Fixtures ====================


@pytest.fixture
def dbapi_connection():
    """创建同步 DBAPI 连接"""
    from sqlalchemy_couchdb.dbapi import connect

    conn = connect(**TEST_CONFIG)

    yield conn

    # 清理
    conn.close()


@pytest.fixture
async def async_dbapi_connection():
    """创建异步 DBAPI 连接"""
    from sqlalchemy_couchdb.dbapi import async_connect

    conn = await async_connect(**TEST_CONFIG)

    yield conn

    # 清理
    await conn.close()


# ==================== SQLAlchemy Engine Fixtures ====================


@pytest.fixture
def sync_engine():
    """创建同步 SQLAlchemy 引擎"""
    from sqlalchemy import create_engine

    # 构建 URL
    url = (
        f"couchdb://{TEST_CONFIG['username']}:{TEST_CONFIG['password']}"
        f"@{TEST_CONFIG['host']}:{TEST_CONFIG['port']}/{TEST_CONFIG['database']}"
    )

    engine = create_engine(url)

    yield engine

    # 清理
    engine.dispose()


@pytest.fixture
async def async_engine():
    """创建异步 SQLAlchemy 引擎"""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.pool import NullPool

    # 构建 URL
    url = (
        f"couchdb+async://{TEST_CONFIG['username']}:{TEST_CONFIG['password']}"
        f"@{TEST_CONFIG['host']}:{TEST_CONFIG['port']}/{TEST_CONFIG['database']}"
    )

    # 异步引擎必须使用 NullPool
    engine = create_async_engine(url, poolclass=NullPool)

    yield engine

    # 清理
    await engine.dispose()


# ==================== 测试数据 Fixtures ====================


@pytest.fixture
def sample_users():
    """示例用户数据"""
    return [
        {"type": "users", "name": "Alice", "age": 30, "email": "alice@example.com"},
        {"type": "users", "name": "Bob", "age": 25, "email": "bob@example.com"},
        {"type": "users", "name": "Carol", "age": 35, "email": "carol@example.com"},
        {"type": "users", "name": "Dave", "age": 28, "email": "dave@example.com"},
    ]


@pytest.fixture
def sample_user():
    """单个示例用户"""
    return {"type": "users", "name": "Alice", "age": 30, "email": "alice@example.com"}


# ==================== 表定义 Fixtures ====================


@pytest.fixture
def users_table():
    """用户表定义"""
    from sqlalchemy import MetaData, Table, Column, String, Integer

    metadata = MetaData()

    return Table(
        "users",
        metadata,
        Column("_id", String, primary_key=True),
        Column("_rev", String),
        Column("name", String(50)),
        Column("age", Integer),
        Column("email", String(100)),
    )


# ==================== 辅助函数 ====================


@pytest.fixture
def assert_doc_equals():
    """断言文档相等（忽略 _id 和 _rev）"""

    def _assert(doc1: Dict[str, Any], doc2: Dict[str, Any]):
        """比较两个文档，忽略 CouchDB 内部字段"""
        # 复制文档以避免修改原始数据
        d1 = {k: v for k, v in doc1.items() if k not in ("_id", "_rev")}
        d2 = {k: v for k, v in doc2.items() if k not in ("_id", "_rev")}

        assert d1 == d2

    return _assert


# ==================== 跳过测试的条件 ====================


def pytest_collection_modifyitems(config, items):
    """修改测试项，添加跳过条件"""
    import httpx

    # 检查 CouchDB 是否可用
    try:
        response = httpx.get(f"http://{TEST_CONFIG['host']}:{TEST_CONFIG['port']}", timeout=2.0)
        couchdb_available = response.status_code == 200
    except Exception:
        couchdb_available = False

    if not couchdb_available:
        skip_integration = pytest.mark.skip(reason="CouchDB 服务器不可用，跳过集成测试")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)

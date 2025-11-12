# 从 Session 访问 CouchDB Client

## 问题

当使用 SQLAlchemy Session 时，如何访问底层的 CouchDBClient 来使用索引分析等功能，而不需要手动再实例化一个 client？

## 解决方案

DBAPI Connection 对象现在暴露了 `.client` 属性，你可以通过 Session 访问它。

### 使用方法

#### 从同步 Session 获取 Client

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

# 创建引擎
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

# 创建 Session
with Session(engine) as session:
    # 获取底层的 DBAPI connection
    dbapi_conn = session.connection().connection

    # 访问 CouchDB client
    client = dbapi_conn.client

    # 现在可以使用 client 的所有功能
    query = '{"type": "select", ...}'
    report = client.analyze_query_index_needs(query, format="text")
    print(report)
```

#### 从异步 Session 获取 Client

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

# 创建异步引擎
engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

# 创建异步 Session
async with AsyncSession(engine) as session:
    # 获取底层的 DBAPI connection
    dbapi_conn = await session.connection()
    raw_conn = await dbapi_conn.get_raw_connection()

    # 访问 CouchDB client
    client = raw_conn.driver_connection.client

    # 使用 client 的功能（注意：client 方法可能需要 await）
    query = '{"type": "select", ...}'
    report = client.analyze_query_index_needs(query, format="markdown")
    print(report)
```

### 实际例子：在查询失败时自动分析

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError

engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

with Session(engine) as session:
    try:
        # 尝试执行查询
        stmt = select(AuditLog).where(
            AuditLog.log_type == "operation",
            AuditLog.tenant_id == "12345"
        ).order_by(AuditLog.create_time.desc())

        result = session.execute(stmt)
    except OperationalError as e:
        if "no_usable_index" in str(e):
            # 获取 client
            dbapi_conn = session.connection().connection
            client = dbapi_conn.client

            # 重新编译查询以获取 JSON
            from sqlalchemy import create_engine
            compiled = stmt.compile(engine)
            query_json = str(compiled)

            # 生成索引建议
            print("\n缺少索引！建议创建以下索引：")
            print(client.analyze_query_index_needs(query_json, format="text"))

            raise  # 重新抛出异常
```

### 便利的辅助函数

你可以创建一个辅助函数来简化访问：

```python
def get_client_from_session(session):
    """从 SQLAlchemy Session 获取 CouchDB Client"""
    try:
        # 尝试同步方式
        dbapi_conn = session.connection().connection
        return dbapi_conn.client
    except AttributeError:
        # 可能是异步 session
        raise ValueError(
            "无法从 session 获取 client。"
            "对于异步 session，请使用 await session.connection() 并获取 raw connection。"
        )

# 使用
with Session(engine) as session:
    client = get_client_from_session(session)
    report = client.analyze_query_index_needs(query_json)
```

### 注意事项

1. **Connection 对象有 `.client` 属性**：这是在 `connect()` 函数中创建的 `SyncCouchDBClient` 或 `AsyncCouchDBClient` 实例

2. **Client 的生命周期**：Client 与 Connection 绑定，当 Connection 关闭时，Client 也会关闭

3. **线程安全**：每个 Session 都有自己的 Connection 和 Client 实例，因此是线程安全的

4. **查询分析功能**：
   - `client.analyze_query_index_needs(compiled_query, format)` - 生成索引建议报告
   - `client.query_analyzer` - 访问底层的 QueryAnalyzer
   - `client.index_manager` - 管理索引

## 架构说明

```
SQLAlchemy Session
    ↓
SQLAlchemy Connection
    ↓
DBAPI Connection (sync.Connection / async_.AsyncConnection)
    ↓ .client 属性
CouchDBClient (SyncCouchDBClient / AsyncCouchDBClient)
    ↓ .query_analyzer 属性
QueryAnalyzer (query_analyzer.QueryAnalyzer)
```

## 完整示例

```python
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from your_models import AuditLog

# 创建引擎
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

def analyze_query_requirements(session, stmt):
    """分析查询的索引需求"""
    # 编译查询
    compiled = stmt.compile(engine)
    query_json = str(compiled)

    # 从 session 获取 client
    dbapi_conn = session.connection().connection
    client = dbapi_conn.client

    # 生成分析报告
    return client.analyze_query_index_needs(query_json, format="markdown")

# 使用
with Session(engine) as session:
    # 构建查询
    stmt = select(AuditLog).where(
        AuditLog.log_type == "operation"
    ).order_by(AuditLog.create_time.desc()).limit(20)

    # 分析索引需求
    report = analyze_query_requirements(session, stmt)

    # 打印报告
    print(report)

    # 然后执行查询
    results = session.execute(stmt).scalars().all()
```

这种方式的优势：
- ✅ 不需要手动实例化 Client
- ✅ 自动使用相同的连接参数
- ✅ 线程安全
- ✅ 与 Session 的生命周期一致

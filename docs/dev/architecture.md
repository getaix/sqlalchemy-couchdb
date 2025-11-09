# SQLAlchemy CouchDB 驱动 - 架构设计文档

## 1. 概述

### 1.1 项目背景

**项目名称**: sqlalchemy-couchdb

**核心目标**:
- 为 CouchDB 提供 SQLAlchemy 2.0+ 驱动支持
- 支持同步和异步操作
- 实现混合数据库架构（CouchDB + 关系型数据库）

**技术栈**:
- Python 3.11+
- SQLAlchemy 2.0+
- httpx (HTTP 客户端)
- CouchDB 3.x

### 1.2 核心特性

#### Phase 1: 纯 CouchDB 驱动
- ✅ 完整的 SQLAlchemy Dialect 实现
- ✅ SQL → Mango Query 编译器
- ✅ 同步和异步 DBAPI
- ✅ 类型系统（SQL ↔ JSON）
- ✅ 基于 httpx 的 HTTP 客户端

#### Phase 2: 混合数据库架构
- ✅ 自动查询路由（简单查询 → CouchDB，复杂查询 → 关系型数据库）
- ✅ 双写同步机制（实时双写 + 最终一致性）
- ✅ 字段映射系统（CouchDB ↔ RDBMS）
- ✅ 后台一致性监控
- ✅ 支持任意 SQLAlchemy 兼容的关系型数据库

---

## 2. 系统架构

### 2.1 Phase 1 架构（纯 CouchDB 模式）

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                            │
│              (User's SQLAlchemy Code)                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                SQLAlchemy Core API Layer                         │
│  • create_engine()                                               │
│  • Connection.execute()                                          │
│  • text(), select(), insert(), update(), delete()                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│              CouchDBDialect (sqlalchemy_couchdb/dialect.py)      │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  1. create_connect_args()                              │     │
│  │     - 解析 URL: couchdb://user:pass@host:port/db       │     │
│  │     - 返回连接参数                                       │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  2. import_dbapi()                                     │     │
│  │     - 返回 DBAPI 模块                                    │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  3. statement_compiler                                 │     │
│  │     - CouchDBCompiler                                  │     │
│  │     - SQL → Mango Query 转换                            │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  4. type_compiler                                      │     │
│  │     - CouchDBTypeCompiler                              │     │
│  │     - 类型系统映射                                       │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│         SQL Compiler (sqlalchemy_couchdb/compiler.py)            │
│                                                                  │
│  ┌──────────────────┬──────────────────┬──────────────────┐     │
│  │  visit_select()  │  visit_insert()  │  visit_update()  │     │
│  │  visit_delete()  │  visit_where()   │  visit_column()  │     │
│  └──────────────────┴──────────────────┴──────────────────┘     │
│                                                                  │
│  SQL AST → Mango Query JSON                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│          DBAPI Layer (sqlalchemy_couchdb/dbapi/)                 │
│                                                                  │
│  ┌──────────────────────┬──────────────────────────────┐        │
│  │  Sync DBAPI          │  Async DBAPI                 │        │
│  │  ────────────        │  ──────────                  │        │
│  │  • Connection        │  • AsyncConnection           │        │
│  │  • Cursor            │  • AsyncCursor               │        │
│  │  • execute()         │  • async execute()           │        │
│  │  • fetchall()        │  • async fetchall()          │        │
│  └──────────────────────┴──────────────────────────────┘        │
│                                                                  │
│  符合 DB-API 2.0 规范                                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│        CouchDB Client (sqlalchemy_couchdb/client.py)             │
│                                                                  │
│  ┌──────────────────────┬──────────────────────────────┐        │
│  │  SyncCouchDBClient   │  AsyncCouchDBClient          │        │
│  │  ──────────────────  │  ───────────────────         │        │
│  │  • httpx.Client      │  • httpx.AsyncClient         │        │
│  │  • create_document() │  • async create_document()   │        │
│  │  • get_document()    │  • async get_document()      │        │
│  │  • update_document() │  • async update_document()   │        │
│  │  • delete_document() │  • async delete_document()   │        │
│  │  • find()            │  • async find()              │        │
│  │  • bulk_docs()       │  • async bulk_docs()         │        │
│  └──────────────────────┴──────────────────────────────┘        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
                   ┌──────────────────────┐
                   │   CouchDB Server     │
                   │   HTTP/JSON API      │
                   └──────────────────────┘
```

### 2.2 Phase 2 架构（混合数据库模式）

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                            │
│              (User's SQLAlchemy Code)                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                SQLAlchemy Core API Layer                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│        HybridCouchDBDialect (sqlalchemy_couchdb/hybrid/)         │
│                                                                  │
│  继承自 CouchDBDialect + 新增混合功能                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  1. Query Analyzer (router.py)                         │     │
│  │     ┌─────────────────────────────────────────┐        │     │
│  │     │  分析 SQL 语句复杂度                      │        │     │
│  │     │  • 检查 JOIN                             │        │     │
│  │     │  • 检查 GROUP BY / HAVING                │        │     │
│  │     │  • 检查子查询                             │        │     │
│  │     │  • 检查窗口函数                           │        │     │
│  │     └─────────────────────────────────────────┘        │     │
│  │     ↓                                                  │     │
│  │     路由决策:                                           │     │
│  │     • 简单查询 → CouchDB                               │     │
│  │     • 复杂查询 → 关系型数据库                           │     │
│  │     • 写操作 → 双写（both）                            │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  2. Dual Write Coordinator (dual_write.py)            │     │
│  │     ┌─────────────────────────────────────────┐        │     │
│  │     │  INSERT:                                 │        │     │
│  │     │  1. 写入 CouchDB (主库)                   │        │     │
│  │     │  2. 写入 RDBMS (从库)                     │        │     │
│  │     │  3. 失败 → 补偿队列                       │        │     │
│  │     └─────────────────────────────────────────┘        │     │
│  │     ┌─────────────────────────────────────────┐        │     │
│  │     │  UPDATE:                                 │        │     │
│  │     │  1. 获取 _rev                            │        │     │
│  │     │  2. 更新 CouchDB                         │        │     │
│  │     │  3. 更新 RDBMS                           │        │     │
│  │     │  4. 失败 → 补偿队列                       │        │     │
│  │     └─────────────────────────────────────────┘        │     │
│  │     ┌─────────────────────────────────────────┐        │     │
│  │     │  DELETE:                                 │        │     │
│  │     │  1. 删除 CouchDB                         │        │     │
│  │     │  2. 删除 RDBMS                           │        │     │
│  │     │  3. 失败 → 补偿队列                       │        │     │
│  │     └─────────────────────────────────────────┘        │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  3. Field Mapper (field_mapper.py)                     │     │
│  │     ┌─────────────────────────────────────────┐        │     │
│  │     │  CouchDB → RDBMS:                        │        │     │
│  │     │  • _id  → id                             │        │     │
│  │     │  • _rev → rev                            │        │     │
│  │     │  • type → (不映射)                        │        │     │
│  │     │  • field1 → field1                       │        │     │
│  │     └─────────────────────────────────────────┘        │     │
│  │     ┌─────────────────────────────────────────┐        │     │
│  │     │  RDBMS → CouchDB:                        │        │     │
│  │     │  • id  → _id                             │        │     │
│  │     │  • rev → _rev                            │        │     │
│  │     │  • 添加 type 字段                         │        │     │
│  │     │  • field1 → field1                       │        │     │
│  │     └─────────────────────────────────────────┘        │     │
│  └────────────────────────────────────────────────────────┘     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐     │
│  │  4. Sync Monitor (sync_monitor.py)                    │     │
│  │     ┌─────────────────────────────────────────┐        │     │
│  │     │  后台任务（定时执行）:                     │        │     │
│  │     │  1. 获取 CouchDB 所有文档                 │        │     │
│  │     │  2. 获取 RDBMS 所有行                     │        │     │
│  │     │  3. 比对差异                              │        │     │
│  │     │  4. 修复不一致                            │        │     │
│  │     │     • CouchDB 有 RDBMS 无 → 补写         │        │     │
│  │     │     • RDBMS 有 CouchDB 无 → 删除         │        │     │
│  │     │     • 数据不匹配 → 以 CouchDB 为准        │        │     │
│  │     └─────────────────────────────────────────┘        │     │
│  └────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
              ┌───────────────┴───────────────┐
              ↓                               ↓
  ┌───────────────────────┐       ┌───────────────────────┐
  │  CouchDB Backend      │       │  任意关系型数据库      │
  │  ─────────────────    │       │  ─────────────────    │
  │  • 简单查询（快）      │       │  • 复杂查询（强大）    │
  │  • 主写入             │       │  • 从写入             │
  │  • 文档存储           │       │  • 备份和查询         │
  │  • Mango Query       │       │  • JOIN/GROUP BY等    │
  └───────────────────────┘       │  • PostgreSQL         │
                                  │  • MySQL              │
                                  │  • SQLite             │
                                  │  • Oracle             │
                                  │  • ...                │
                                  └───────────────────────┘
```

---

## 3. 核心模块设计

### 3.1 SQL 编译器（Compiler）

#### 3.1.1 职责
将 SQLAlchemy SQL AST 转换为 CouchDB Mango Query JSON。

#### 3.1.2 转换规则

**SELECT 语句**:
```python
# SQL
SELECT name, age FROM users WHERE age > 25 ORDER BY age DESC LIMIT 10

# Mango Query
{
  "selector": {
    "type": "users",
    "age": {"$gt": 25}
  },
  "fields": ["name", "age"],
  "sort": [{"age": "desc"}],
  "limit": 10
}
```

**INSERT 语句**:
```python
# SQL
INSERT INTO users (name, age) VALUES ('Alice', 30)

# CouchDB Document
{
  "type": "users",
  "name": "Alice",
  "age": 30
}
```

**UPDATE 语句**:
```python
# SQL
UPDATE users SET age = 31 WHERE name = 'Alice'

# 分两步:
# 1. Find: {"selector": {"type": "users", "name": "Alice"}}
# 2. Update: {"age": 31}
```

**DELETE 语句**:
```python
# SQL
DELETE FROM users WHERE age < 18

# 分两步:
# 1. Find: {"selector": {"type": "users", "age": {"$lt": 18}}}
# 2. Delete each document
```

#### 3.1.3 WHERE 子句操作符映射

| SQL 操作符 | Mango Query 操作符 | 示例 |
|-----------|-------------------|------|
| `=` | 直接值 | `{"age": 25}` |
| `>` | `$gt` | `{"age": {"$gt": 25}}` |
| `>=` | `$gte` | `{"age": {"$gte": 25}}` |
| `<` | `$lt` | `{"age": {"$lt": 25}}` |
| `<=` | `$lte` | `{"age": {"$lte": 25}}` |
| `!=` | `$ne` | `{"age": {"$ne": 25}}` |
| `IN` | `$in` | `{"age": {"$in": [25, 30]}}` |
| `NOT IN` | `$nin` | `{"age": {"$nin": [25, 30]}}` |
| `LIKE` | `$regex` | `{"name": {"$regex": "^A"}}` |
| `AND` | `$and` | `{"$and": [{...}, {...}]}` |
| `OR` | `$or` | `{"$or": [{...}, {...}]}` |

### 3.2 类型系统（Types）

#### 3.2.1 类型映射表

| SQLAlchemy 类型 | Python 类型 | CouchDB JSON 类型 | 处理器 |
|----------------|------------|------------------|--------|
| `Integer` | `int` | `number` | `CouchDBInteger` |
| `String` | `str` | `string` | `CouchDBString` |
| `Text` | `str` | `string` | `CouchDBString` |
| `Boolean` | `bool` | `boolean` | `CouchDBBoolean` |
| `DateTime` | `datetime` | `string (ISO 8601)` | `CouchDBDateTime` |
| `Float` | `float` | `number` | `Float` (原生) |
| `JSON` | `dict/list` | `object/array` | `CouchDBJSON` |

#### 3.2.2 类型处理器

**绑定处理器（bind_processor）**: Python → JSON
```python
class CouchDBDateTime(sa_types.DateTime):
    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            return value.isoformat()  # 转为 ISO 8601 字符串
        return process
```

**结果处理器（result_processor）**: JSON → Python
```python
class CouchDBDateTime(sa_types.DateTime):
    def result_processor(self, dialect, coltype):
        def process(value):
            if value is None:
                return None
            from datetime import datetime
            return datetime.fromisoformat(value)  # 从 ISO 8601 解析
        return process
```

### 3.3 DBAPI 层

#### 3.3.1 接口规范
符合 [PEP 249 (DB-API 2.0)](https://peps.python.org/pep-0249/)

#### 3.3.2 核心对象

**Connection**:
```python
class Connection:
    def cursor() -> Cursor
    def commit()   # CouchDB 自动提交，空操作
    def rollback() # 不支持，抛出 NotSupportedError
    def close()
```

**Cursor**:
```python
class Cursor:
    # 属性
    description: Optional[List[Tuple]]  # 列描述
    rowcount: int                        # 影响行数
    arraysize: int = 1                   # fetchmany 默认大小

    # 方法
    def execute(operation, parameters=None)
    def executemany(operation, seq_of_parameters)
    def fetchone() -> Optional[Tuple]
    def fetchmany(size=None) -> List[Tuple]
    def fetchall() -> List[Tuple]
    def close()
```

#### 3.3.3 execute 执行流程

```
execute(operation, parameters)
    ↓
解析 operation (已经是 Mango Query JSON 字符串)
    ↓
调用 CouchDB Client 相应方法
    ↓
存储结果到 self._rows
    ↓
更新 description 和 rowcount
    ↓
返回 self
```

### 3.4 HTTP 客户端（Client）

#### 3.4.1 接口设计

```python
class SyncCouchDBClient:
    def __init__(self, host, port, username, password, database, use_ssl=False)
    def connect() -> httpx.Client
    def close()
    def ping() -> bool
    def create_document(doc: dict) -> dict  # 返回 {'id': ..., 'rev': ...}
    def get_document(doc_id: str) -> dict
    def update_document(doc_id: str, doc: dict, rev: str) -> dict
    def delete_document(doc_id: str, rev: str) -> dict
    def find(selector: dict, fields=None, limit=None, skip=None) -> list
    def bulk_docs(docs: list) -> list
```

#### 3.4.2 CouchDB API 映射

| 客户端方法 | HTTP 方法 | CouchDB API 端点 |
|-----------|----------|-----------------|
| `create_document` | POST | `/{db}` |
| `get_document` | GET | `/{db}/{doc_id}` |
| `update_document` | PUT | `/{db}/{doc_id}?rev={rev}` |
| `delete_document` | DELETE | `/{db}/{doc_id}?rev={rev}` |
| `find` | POST | `/{db}/_find` (Mango Query) |
| `bulk_docs` | POST | `/{db}/_bulk_docs` |

---

## 4. 数据流

### 4.1 查询流程（Phase 1）

```
用户代码:
  engine.execute(text("SELECT * FROM users WHERE age > 25"))
       ↓
SQLAlchemy Core:
  解析 SQL → SQL AST
       ↓
CouchDBDialect:
  调用 CouchDBCompiler.compile(sql_ast)
       ↓
CouchDBCompiler:
  visit_select() → 生成 Mango Query JSON
  {
    "selector": {"type": "users", "age": {"$gt": 25}},
    "fields": ["*"]
  }
       ↓
DBAPI Cursor:
  execute(mango_query_json)
       ↓
CouchDB Client:
  find(selector={"type": "users", "age": {"$gt": 25}})
       ↓
httpx:
  POST /{db}/_find
  {
    "selector": {"type": "users", "age": {"$gt": 25}}
  }
       ↓
CouchDB Server:
  执行查询，返回结果
       ↓
httpx:
  返回 JSON 响应
       ↓
CouchDB Client:
  解析响应，返回文档列表
       ↓
DBAPI Cursor:
  存储结果到 self._rows
  构建 description
       ↓
SQLAlchemy ResultProxy:
  包装结果，提供迭代器
       ↓
用户代码:
  for row in result:
      print(row)
```

### 4.2 插入流程（Phase 2 混合模式）

```
用户代码:
  conn.execute(text("INSERT INTO users (name, age) VALUES ('Alice', 30)"))
       ↓
HybridCouchDBDialect:
  Query Analyzer 分析 → 判定为写操作 → 路由到 'both'
       ↓
Dual Write Coordinator:
  execute_insert(table='users', values={'name': 'Alice', 'age': 30})
       ↓
步骤 1: 写入 CouchDB (主库)
  couchdb_doc = {
    'type': 'users',
    'name': 'Alice',
    'age': 30
  }
  result = couchdb.create_document(couchdb_doc)
  # 返回: {'id': 'abc123', 'rev': '1-xyz'}
       ↓
步骤 2: 写入关系型数据库 (从库)
  rdbms_values = FieldMapper.to_rdbms(couchdb_doc, 'abc123', '1-xyz')
  # 返回: {'id': 'abc123', 'rev': '1-xyz', 'name': 'Alice', 'age': 30}
       ↓
  secondary_engine.execute(
    "INSERT INTO users (id, rev, name, age) VALUES (:id, :rev, :name, :age)",
    rdbms_values
  )
       ↓
成功 → 返回结果
失败 → 记录到补偿队列，后台重试
```

### 4.3 复杂查询流程（Phase 2 混合模式）

```
用户代码:
  conn.execute(text("""
    SELECT u.name, COUNT(o.id) as order_count
    FROM users u
    JOIN orders o ON u.id = o.user_id
    GROUP BY u.name
  """))
       ↓
HybridCouchDBDialect:
  Query Analyzer 分析:
    - 检测到 JOIN → 添加 'has_join' 特征
    - 检测到 GROUP BY → 添加 'has_group_by' 特征
  路由决策: 'secondary' (关系型数据库)
       ↓
直接转发到二级数据库引擎:
  secondary_engine.execute(原始 SQL)
       ↓
PostgreSQL/MySQL/... 执行查询
       ↓
返回结果给用户
```

---

## 5. 错误处理

### 5.1 异常层次结构

```
Exception
  └─ CouchDBError (基础异常)
      ├─ DatabaseError
      │   ├─ OperationalError (连接、网络错误)
      │   ├─ ProgrammingError (SQL 语法错误)
      │   ├─ IntegrityError (数据完整性错误)
      │   ├─ DataError (类型转换错误)
      │   ├─ InternalError (内部错误)
      │   └─ NotSupportedError (不支持的操作)
      └─ Warning
```

### 5.2 错误处理策略

| 错误类型 | 处理策略 |
|---------|---------|
| 连接失败 | 抛出 `OperationalError`，提示用户检查 CouchDB 是否运行 |
| 认证失败 | 抛出 `OperationalError`，提示用户检查用户名密码 |
| 文档不存在 | 抛出 `DataError`，包含文档 ID |
| 冲突（_rev 不匹配）| 抛出 `IntegrityError`，提示用户重试 |
| 不支持的 SQL 特性 | 抛出 `NotSupportedError`，说明限制 |
| 双写从库失败 | 记录日志，不抛异常，后台补偿 |

---

## 6. 性能优化

### 6.1 连接池

**httpx 连接池配置**:
```python
limits = httpx.Limits(
    max_connections=100,        # 最大连接数
    max_keepalive_connections=20  # 保持活跃的连接数
)
client = httpx.Client(limits=limits)
```

### 6.2 批量操作

**使用 bulk_docs API**:
```python
# 批量插入 1000 条文档
docs = [{"type": "users", "name": f"User{i}"} for i in range(1000)]
results = client.bulk_docs(docs)
```

### 6.3 查询优化

**建议用户创建索引**:
```python
# 在 CouchDB 中为常用查询创建索引
POST /{db}/_index
{
  "index": {
    "fields": ["type", "age"]
  },
  "name": "type-age-index"
}
```

### 6.4 缓存（未来）

- 结果集缓存
- 编译后的查询缓存
- 元数据缓存

---

## 7. 安全性

### 7.1 认证

支持 CouchDB Basic Auth:
```python
engine = create_engine('couchdb://username:password@localhost:5984/mydb')
```

### 7.2 SQL 注入防护

**使用参数化查询**:
```python
# 安全 ✅
conn.execute(text("SELECT * FROM users WHERE name = :name"), {"name": user_input})

# 不安全 ❌
conn.execute(text(f"SELECT * FROM users WHERE name = '{user_input}'"))
```

### 7.3 HTTPS 支持

```python
engine = create_engine('couchdb://user:pass@localhost:5984/mydb?use_ssl=true')
```

---

## 8. 限制和约束

### 8.1 Phase 1 限制

| SQL 特性 | 支持情况 | 说明 |
|---------|---------|------|
| `SELECT` | ✅ 部分支持 | 简单查询，无 JOIN |
| `INSERT` | ✅ 支持 | |
| `UPDATE` | ✅ 支持 | |
| `DELETE` | ✅ 支持 | |
| `JOIN` | ❌ 不支持 | CouchDB 不支持 |
| `GROUP BY` | ❌ 不支持 | 需要使用视图 |
| `HAVING` | ❌ 不支持 | 需要使用视图 |
| `UNION` | ❌ 不支持 | |
| `子查询` | ❌ 不支持 | |
| `事务` | ❌ 不支持 | CouchDB 只有文档级原子性 |
| `外键` | ❌ 不支持 | 文档数据库无外键概念 |

### 8.2 Phase 2 混合模式

通过路由到关系型数据库，上述限制得到缓解：
- ✅ 复杂查询（JOIN, GROUP BY 等）路由到关系型数据库
- ✅ 保留 CouchDB 的简单查询性能优势

---

## 9. 测试策略

### 9.1 单元测试

- 类型转换测试
- SQL 编译测试
- DBAPI 接口测试
- 字段映射测试
- 路由决策测试

### 9.2 集成测试

- 端到端 CRUD 测试
- 同步/异步操作测试
- 双写一致性测试
- 多数据库集成测试（PostgreSQL, MySQL, SQLite）

### 9.3 性能测试

- 简单查询延迟
- 批量插入吞吐量
- 双写延迟
- 一致性检查性能

---

## 10. 部署和运维

### 10.1 依赖

**必需**:
- Python >= 3.11
- SQLAlchemy >= 2.0.0
- httpx >= 0.27.0
- CouchDB >= 3.0

**可选（Phase 2）**:
- PostgreSQL + asyncpg
- MySQL + aiomysql
- SQLite (内置)

### 10.2 配置示例

**Phase 1**:
```python
from sqlalchemy import create_engine

# 同步
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

# 异步
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')
```

**Phase 2**:
```python
# 混合模式
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost:5432/mydb'
)
```

### 10.3 监控

**关键指标**:
- CouchDB 连接数
- 查询延迟（P50, P95, P99）
- 双写成功率
- 补偿队列长度
- 一致性检查结果

---

## 11. 未来扩展

### Phase 3: ORM 支持
- 模型映射
- Relationship（文档引用模式）
- Session 管理
- Lazy/Eager Loading

### Phase 4: 高级特性
- 视图和索引管理
- 附件处理
- 变更 Feed
- 复制功能

### Phase 5: 性能优化
- 查询缓存
- 元数据缓存
- 批量操作优化
- 连接池调优

---

**文档版本**: v1.0
**创建日期**: 2025-01-02
**最后更新**: 2025-01-02

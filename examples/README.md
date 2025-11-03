# 使用示例

本目录包含 SQLAlchemy CouchDB Dialect 的使用示例。

## 前提条件

1. 安装 CouchDB 服务器（3.x+）
2. 创建测试数据库
3. 安装依赖包

```bash
# 安装包
pip install -e ..

# 或者从 PyPI 安装（发布后）
pip install sqlalchemy-couchdb
```

## 配置 CouchDB

```bash
# 启动 CouchDB
docker run -d -p 5984:5984 \
  -e COUCHDB_USER=admin \
  -e COUCHDB_PASSWORD=password \
  couchdb:3

# 创建测试数据库
curl -X PUT http://admin:password@localhost:5984/mydb
```

## 运行示例

### 1. 同步模式示例

```bash
python basic_sync.py
```

演示内容:
- 创建引擎和连接
- 定义表结构
- INSERT、SELECT、UPDATE、DELETE 操作
- 使用 Session
- 批量操作
- 错误处理

### 2. 异步模式示例

```bash
python basic_async.py
```

演示内容:
- 创建异步引擎
- 异步 INSERT、SELECT、UPDATE、DELETE
- 使用 AsyncSession
- 异步批量操作
- 并发操作
- 错误处理

## 注意事项

### URL 格式

**同步模式:**
```python
engine = create_engine("couchdb://user:pass@host:port/database")
```

**异步模式:**
```python
engine = create_async_engine("couchdb+async://user:pass@host:port/database")
```

### 表结构定义

CouchDB 是文档数据库，"表" 对应于 `type` 字段的值:

```python
users = Table(
    "users",  # 表名 → CouchDB 文档的 type 字段
    metadata,
    Column("_id", String, primary_key=True),  # CouchDB 文档 ID
    Column("_rev", String),  # CouchDB 文档版本
    Column("name", String(50)),  # 自定义字段
    Column("age", Integer),
)
```

### SQL 功能限制

由于 CouchDB 是文档数据库，有以下限制:

**支持的功能:**
- ✅ 基本 CRUD (INSERT, SELECT, UPDATE, DELETE)
- ✅ WHERE 条件 (=, >, <, >=, <=, !=, IN, LIKE)
- ✅ AND/OR 逻辑运算
- ✅ ORDER BY
- ✅ LIMIT/OFFSET

**不支持的功能:**
- ❌ JOIN 操作
- ❌ GROUP BY
- ❌ HAVING
- ❌ 子查询
- ❌ 窗口函数
- ❌ 事务回滚（CouchDB 自动提交）

## 查询示例

### 简单查询

```python
# 查询所有用户
stmt = select(users)
result = conn.execute(stmt)

# 带条件
stmt = select(users).where(users.c.age > 25)
result = conn.execute(stmt)

# 排序和限制
stmt = select(users).order_by(users.c.age.desc()).limit(10)
result = conn.execute(stmt)
```

### 插入数据

```python
# 单条插入
stmt = insert(users).values(name="Alice", age=30)
conn.execute(stmt)

# 批量插入
conn.execute(insert(users), [
    {"name": "Bob", "age": 25},
    {"name": "Carol", "age": 28}
])
```

### 更新数据

```python
stmt = update(users).where(users.c.name == "Alice").values(age=31)
conn.execute(stmt)
```

### 删除数据

```python
stmt = delete(users).where(users.c.age < 18)
conn.execute(stmt)
```

## 错误处理

```python
from sqlalchemy_couchdb.exceptions import (
    CouchDBError,
    OperationalError,
    ProgrammingError
)

try:
    result = conn.execute(stmt)
except OperationalError as e:
    # 操作错误（连接、网络等）
    print(f"操作错误: {e}")
except ProgrammingError as e:
    # 编程错误（SQL 语法等）
    print(f"编程错误: {e}")
except CouchDBError as e:
    # 其他 CouchDB 错误
    print(f"CouchDB 错误: {e}")
```

## 下一步

查看完整文档:
- [架构设计](../docs/architecture.md)
- [API 文档](../docs/api.md)（待完成）

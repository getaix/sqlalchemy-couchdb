# 基础用法

## 第一次使用

### 1. 创建引擎

```python
from sqlalchemy import create_engine

# 同步引擎
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

# 异步引擎
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')
```

### 2. 定义表结构

```python
from sqlalchemy import Table, Column, Integer, String, MetaData

metadata = MetaData()

# 注意：在 CouchDB 中，"表"实际上是通过 `type` 字段区分的
users = Table('users', metadata,
    Column('_id', String, primary_key=True),  # CouchDB 主键
    Column('_rev', String),                    # 版本号（用于乐观锁）
    Column('name', String),
    Column('age', Integer),
    Column('email', String),
    Column('type', String)  # 用于区分文档类型
)

# 创建表（在 CouchDB 中会创建视图）
metadata.create_all(engine)
```

### 3. 插入数据

```python
from sqlalchemy import text

# 方式1: 使用原生 SQL
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (_id, name, age, email, type)
        VALUES (:id, :name, :age, :email, 'user')
    """), {
        'id': 'user:123',
        'name': 'Alice',
        'age': 30,
        'email': 'alice@example.com'
    })
    conn.commit()

# 方式2: 使用字典（更常用）
with engine.connect() as conn:
    result = conn.execute(text("""
        INSERT INTO users (_id, name, age, email, type)
        VALUES (:_id, :name, :age, :email, 'user')
        RETURNING *
    """), {
        '_id': 'user:124',
        'name': 'Bob',
        'age': 25,
        'email': 'bob@example.com'
    })
    row = result.fetchone()
    print(f"插入的文档ID: {row._id}")
    conn.commit()
```

### 4. 查询数据

```python
from sqlalchemy import text

with engine.connect() as conn:
    # 简单查询
    result = conn.execute(text("""
        SELECT * FROM users WHERE type = 'user'
    """))

    for row in result:
        print(f"ID: {row._id}, 姓名: {row.name}, 年龄: {row.age}")

    # 带条件查询
    result = conn.execute(text("""
        SELECT * FROM users
        WHERE type = 'user' AND age > :age
        ORDER BY age DESC
        LIMIT 10
    """), {'age': 20})

    for row in result:
        print(f"{row.name}: {row.age} 岁")

    conn.commit()
```

### 5. 更新数据

```python
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        UPDATE users
        SET age = :age
        WHERE _id = :id AND type = 'user'
        RETURNING *
    """), {
        'id': 'user:123',
        'age': 31
    })

    updated_row = result.fetchone()
    print(f"更新后的文档: {updated_row._id}, _rev: {updated_row._rev}")
    conn.commit()
```

### 6. 删除数据

```python
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("""
        DELETE FROM users
        WHERE _id = :id AND type = 'user'
    """), {
        'id': 'user:123'
    })
    conn.commit()
```

## 文档结构

### CouchDB 文档格式

在 CouchDB 中，每个文档都是 JSON 对象：

```json
{
  "_id": "user:123",
  "_rev": "1-abc123def456",
  "type": "users",
  "name": "Alice",
  "age": 30,
  "email": "alice@example.com"
}
```

**字段说明**:
- `_id`: 文档唯一标识符
- `_rev`: 版本号（用于乐观锁）
- `type`: 文档类型（用于模拟"表"）
- 其他字段: 自定义数据

### 类型字段约定

| 表名 | type 字段值 | 示例 _id |
|------|-----------|---------|
| `users` | `users` | `user:123` |
| `orders` | `orders` | `order:456` |
| `products` | `products` | `product:789` |

## 最佳实践

### 1. 使用上下文管理器

```python
# ✅ 推荐
with engine.connect() as conn:
    conn.execute(text("..."))
    conn.commit()

# ❌ 不推荐
conn = engine.connect()
conn.execute(text("..."))
conn.commit()
conn.close()
```

### 2. 参数化查询

```python
# ✅ 推荐：安全，防止 SQL 注入
conn.execute(text("SELECT * FROM users WHERE age > :age"), {'age': 20})

# ❌ 危险：SQL 注入风险
conn.execute(text(f"SELECT * FROM users WHERE age > {age}"))
```

### 3. 使用事务

```python
with engine.begin() as conn:  # 自动 commit
    conn.execute(text("INSERT INTO users ..."))
    conn.execute(text("INSERT INTO orders ..."))
    # 自动 commit

# 或手动控制
with engine.connect() as conn:
    try:
        conn.execute(text("INSERT INTO users ..."))
        conn.execute(text("INSERT INTO orders ..."))
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
```

### 4. 批量操作

```python
# 批量插入
with engine.connect() as conn:
    users_data = [
        {'_id': 'user:1', 'name': 'Alice', 'type': 'users'},
        {'_id': 'user:2', 'name': 'Bob', 'type': 'users'},
        {'_id': 'user:3', 'name': 'Charlie', 'type': 'users'},
    ]

    for user_data in users_data:
        conn.execute(text("""
            INSERT INTO users (_id, name, type)
            VALUES (:_id, :name, :type)
        """), user_data)

    conn.commit()
```

## 常见错误

### 1. 乐观锁错误

```python
# 如果文档已被修改，会抛出异常
# 解决方案：重新获取最新文档
try:
    conn.execute(text("UPDATE users SET age=31 WHERE _id='user:123'"))
    conn.commit()
except Exception as e:
    # 重新获取文档
    result = conn.execute(text("SELECT * FROM users WHERE _id='user:123'"))
    latest_doc = result.fetchone()
    # 重新尝试更新
```

### 2. 文档不存在

```python
# 检查文档是否存在
result = conn.execute(text("SELECT * FROM users WHERE _id = :id"), {'id': 'user:999'})
if result.rowcount == 0:
    print("文档不存在")
else:
    row = result.fetchone()
```

## 下一步

- [连接配置](connection.md)
- [同步操作](../guide/sync-operations.md)
- [异步操作](../guide/async-operations.md)
- [类型映射](../guide/type-mapping.md)

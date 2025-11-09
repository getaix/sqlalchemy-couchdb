# 同步操作指南

## 概述

SQLAlchemy CouchDB 方言支持完整的同步操作，使用标准的 SQLAlchemy 2.0 API。所有同步操作都基于 `couchdb://` URL 模式。

## 创建同步引擎

```python
from sqlalchemy import create_engine

# 基础连接
engine = create_engine('couchdb://localhost:5984/mydb')

# 带认证的连接
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

# 带连接池配置的连接
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    pool_size=10,
    max_overflow=20,
)
```

## CRUD 操作

### CREATE - 插入数据

#### 单条插入

```python
from sqlalchemy import text

with engine.connect() as conn:
    # 插入文档
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

    print("✅ 插入成功")
```

#### 批量插入

```python
from sqlalchemy import text

with engine.connect() as conn:
    users_data = [
        {'id': 'user:1', 'name': 'Alice', 'age': 30, 'email': 'alice@example.com'},
        {'id': 'user:2', 'name': 'Bob', 'age': 25, 'email': 'bob@example.com'},
        {'id': 'user:3', 'name': 'Charlie', 'age': 35, 'email': 'charlie@example.com'},
    ]

    for user_data in users_data:
        conn.execute(text("""
            INSERT INTO users (_id, name, age, email, type)
            VALUES (:id, :name, :age, :email, 'user')
        """), user_data)

    conn.commit()
    print(f"✅ 批量插入 {len(users_data)} 条记录")
```

#### 批量插入 (高效方式)

```python
from sqlalchemy import text

with engine.connect() as conn:
    users_data = [
        {'id': 'user:1', 'name': 'Alice', 'age': 30, 'email': 'alice@example.com'},
        {'id': 'user:2', 'name': 'Bob', 'age': 25, 'email': 'bob@example.com'},
        {'id': 'user:3', 'name': 'Charlie', 'age': 35, 'email': 'charlie@example.com'},
    ]

    conn.execute(text("""
        INSERT INTO users (_id, name, age, email, type)
        VALUES (:id, :name, :age, :email, 'user')
    """), users_data)

    conn.commit()
    print("✅ 批量插入成功")
```

### READ - 查询数据

#### 简单查询

```python
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT * FROM users WHERE type = 'user'
    """))

    for row in result:
        print(f"ID: {row._id}, 姓名: {row.name}, 年龄: {row.age}")
```

#### 条件查询

```python
from sqlalchemy import text

with engine.connect() as conn:
    # 大于查询
    result = conn.execute(text("""
        SELECT * FROM users
        WHERE type = 'user' AND age > :age
    """), {'age': 25})

    for row in result:
        print(f"{row.name}: {row.age} 岁")

    # IN 查询
    result = conn.execute(text("""
        SELECT * FROM users
        WHERE type = 'user' AND _id IN (:id1, :id2, :id3)
    """), {
        'id1': 'user:1',
        'id2': 'user:2',
        'id3': 'user:3'
    })

    # LIKE 查询
    result = conn.execute(text("""
        SELECT * FROM users
        WHERE type = 'user' AND name LIKE :pattern
    """), {'pattern': '%Alice%'})
```

#### 排序和分页

```python
from sqlalchemy import text

with engine.connect() as conn:
    # 排序
    result = conn.execute(text("""
        SELECT * FROM users
        WHERE type = 'user'
        ORDER BY age DESC, name ASC
    """))

    for row in result:
        print(f"{row.name}: {row.age} 岁")

    # 分页
    result = conn.execute(text("""
        SELECT * FROM users
        WHERE type = 'user'
        ORDER BY _id
        LIMIT 10 OFFSET 20
    """))

    for row in result:
        print(f"{row.name}")
```

#### 获取单条记录

```python
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT * FROM users
        WHERE type = 'user' AND _id = :id
    """), {'id': 'user:123'})

    if result.rowcount > 0:
        row = result.fetchone()
        print(f"找到用户: {row.name}")
    else:
        print("用户不存在")
```

### UPDATE - 更新数据

#### 更新单条记录

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

    if result.rowcount > 0:
        updated_row = result.fetchone()
        print(f"✅ 更新成功, 新版本: {updated_row._rev}")
    else:
        print("❌ 文档不存在")

    conn.commit()
```

#### 更新多条记录

```python
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        UPDATE users
        SET age = age + 1
        WHERE type = 'user' AND age < :max_age
        RETURNING *
    """), {'max_age': 30})

    updated_count = result.rowcount
    print(f"✅ 更新了 {updated_count} 条记录")

    conn.commit()
```

### DELETE - 删除数据

#### 删除单条记录

```python
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        DELETE FROM users
        WHERE _id = :id AND type = 'user'
    """), {'id': 'user:123'})

    if result.rowcount > 0:
        print("✅ 删除成功")
    else:
        print("❌ 文档不存在")

    conn.commit()
```

#### 批量删除

```python
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text("""
        DELETE FROM users
        WHERE type = 'user' AND age < :min_age
    """), {'min_age': 18})

    deleted_count = result.rowcount
    print(f"✅ 删除了 {deleted_count} 条记录")

    conn.commit()
```

## 事务管理

### 自动提交

```python
from sqlalchemy import text

# 使用 begin() 自动提交
with engine.begin() as conn:
    conn.execute(text("""
        INSERT INTO users (_id, name, age, type)
        VALUES (:id, :name, :age, 'user')
    """), {'id': 'user:456', 'name': 'David', 'age': 28})

    # 自动 commit
```

### 手动事务

```python
from sqlalchemy import text

with engine.connect() as conn:
    try:
        # 开始事务
        conn.execute(text("""
            INSERT INTO users (_id, name, age, type)
            VALUES (:id1, :name1, :age1, 'user')
        """), {'id1': 'user:1', 'name1': 'Alice', 'age1': 30})

        conn.execute(text("""
            INSERT INTO orders (_id, user_id, amount, type)
            VALUES (:id2, :user_id, :amount, 'order')
        """), {'id2': 'order:1', 'user_id': 'user:1', 'amount': 99.99})

        # 提交事务
        conn.commit()
        print("✅ 事务提交成功")
    except Exception as e:
        # 回滚事务
        conn.rollback()
        print(f"❌ 事务回滚: {e}")
```

## 错误处理

### DB-API 异常

```python
from sqlalchemy import text
from sqlalchemy_couchdb.exceptions import CouchDBError

try:
    with engine.connect() as conn:
        conn.execute(text("""
            INSERT INTO users (_id, name, age, type)
            VALUES (:id, :name, :age, 'user')
        """), {
            'id': 'user:123',  # 假设已存在
            'name': 'Alice',
            'age': 30
        })
        conn.commit()
except CouchDBError as e:
    print(f"CouchDB 错误: {e}")
except Exception as e:
    print(f"通用错误: {e}")
```

### 乐观锁错误处理

```python
from sqlalchemy import text

def update_with_retry(conn, user_id, new_age, max_retries=3):
    """带重试的乐观锁更新"""
    for attempt in range(max_retries):
        try:
            result = conn.execute(text("""
                UPDATE users
                SET age = :age
                WHERE _id = :id AND type = 'user'
                RETURNING *
            """), {
                'id': user_id,
                'age': new_age
            })

            if result.rowcount > 0:
                return result.fetchone()
            else:
                raise Exception("文档不存在")

        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"尝试 {attempt + 1} 失败: {e}，重试中...")
            # 重新获取最新文档
            time.sleep(0.1)

# 使用
with engine.connect() as conn:
    updated_row = update_with_retry(conn, 'user:123', 35)
    conn.commit()
```

## 性能优化

### 1. 使用批量操作

```python
# ✅ 推荐：批量插入
users_data = [...]
conn.execute(text("INSERT INTO ..."), users_data)

# ❌ 慢：循环插入
for data in users_data:
    conn.execute(text("INSERT INTO ..."), data)
```

### 2. 使用索引

```python
# 自动创建索引（通过 ORDER BY）
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user' AND age > 25
    ORDER BY age DESC  -- 自动创建 age 索引
"""))
```

### 3. 限制返回字段

```python
# ✅ 只查询需要的字段
result = conn.execute(text("""
    SELECT _id, name, age FROM users
    WHERE type = 'user'
"""))

# ❌ 查询所有字段
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
"""))
```

## 连接管理

### 连接池

```python
from sqlalchemy import create_engine

engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    pool_size=10,          # 池大小
    max_overflow=20,       # 最大溢出
    pool_recycle=3600,     # 连接回收时间
    pool_pre_ping=True,    # 预检查连接
)

# 监控连接池
def check_pool(engine):
    pool = engine.pool
    print(f"池大小: {pool.size()}")
    print("已借出:", pool.checkedout())
    print("已返回:", pool.returned())

check_pool(engine)
```

### 连接测试

```python
def ping_database(engine):
    """测试数据库连接"""
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ 数据库连接正常")
            return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

ping_database(engine)
```

## 下一步

- [异步操作](async-operations.md)
- [类型映射](type-mapping.md)
- [SQL 转 Mango Query](sql-to-mango.md)

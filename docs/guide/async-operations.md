# 异步操作指南

## 概述

SQLAlchemy CouchDB 方言支持完整的异步操作，使用 `couchdb+async://` URL 模式。异步模式基于 SQLAlchemy 2.0+ 的 asyncio 支持和 greenlet 机制。

## 创建异步引擎

```python
from sqlalchemy.ext.asyncio import create_async_engine

# 基础异步连接
engine = create_async_engine('couchdb+async://localhost:5984/mydb')

# 带认证的异步连接
engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

# 带连接池配置的异步连接
engine = create_async_engine(
    'couchdb+async://admin:password@localhost:5984/mydb',
    pool_size=10,
    max_overflow=20,
)
```

## 异步 CRUD 操作

### CREATE - 异步插入

#### 单条插入

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def insert_single_user():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        await conn.execute(text("""
            INSERT INTO users (_id, name, age, email, type)
            VALUES (:id, :name, :age, :email, 'user')
        """), {
            'id': 'user:async-123',
            'name': 'Alice Async',
            'age': 30,
            'email': 'alice@example.com'
        })

        await conn.commit()
        print("✅ 异步插入成功")

    await engine.dispose()

# 运行
asyncio.run(insert_single_user())
```

#### 批量插入

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def batch_insert():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        users_data = [
            {'id': 'user:async-1', 'name': 'Alice', 'age': 30, 'email': 'alice@example.com'},
            {'id': 'user:async-2', 'name': 'Bob', 'age': 25, 'email': 'bob@example.com'},
            {'id': 'user:async-3', 'name': 'Charlie', 'age': 35, 'email': 'charlie@example.com'},
        ]

        await conn.execute(text("""
            INSERT INTO users (_id, name, age, email, type)
            VALUES (:id, :name, :age, :email, 'user')
        """), users_data)

        await conn.commit()
        print(f"✅ 异步批量插入 {len(users_data)} 条记录")

    await engine.dispose()

asyncio.run(batch_insert())
```

### READ - 异步查询

#### 简单查询

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def query_users():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT * FROM users WHERE type = 'user'
        """))

        # 注意：使用同步迭代（结果已在 execute 时缓存）
        for row in result:
            print(f"ID: {row._id}, 姓名: {row.name}, 年龄: {row.age}")

    await engine.dispose()

asyncio.run(query_users())
```

#### 条件查询

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def query_with_conditions():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        # 大于查询
        result = await conn.execute(text("""
            SELECT * FROM users
            WHERE type = 'user' AND age > :age
        """), {'age': 25})

        for row in result:
            print(f"{row.name}: {row.age} 岁")

        # IN 查询
        result = await conn.execute(text("""
            SELECT * FROM users
            WHERE type = 'user' AND _id IN (:id1, :id2)
        """), {
            'id1': 'user:async-1',
            'id2': 'user:async-2'
        })

        # LIKE 查询
        result = await conn.execute(text("""
            SELECT * FROM users
            WHERE type = 'user' AND name LIKE :pattern
        """), {'pattern': '%Alice%'})

    await engine.dispose()

asyncio.run(query_with_conditions())
```

#### 获取单条记录

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def get_single_user():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        result = await conn.execute(text("""
            SELECT * FROM users
            WHERE type = 'user' AND _id = :id
        """), {'id': 'user:async-123'})

        if result.rowcount > 0:
            row = result.fetchone()
            print(f"找到用户: {row.name}")
        else:
            print("用户不存在")

    await engine.dispose()

asyncio.run(get_single_user())
```

### UPDATE - 异步更新

#### 更新单条记录

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def update_user():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        result = await conn.execute(text("""
            UPDATE users
            SET age = :age
            WHERE _id = :id AND type = 'user'
            RETURNING *
        """), {
            'id': 'user:async-123',
            'age': 31
        })

        if result.rowcount > 0:
            updated_row = result.fetchone()
            print(f"✅ 更新成功, 新版本: {updated_row._rev}")
        else:
            print("❌ 文档不存在")

        await conn.commit()

    await engine.dispose()

asyncio.run(update_user())
```

### DELETE - 异步删除

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def delete_user():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        result = await conn.execute(text("""
            DELETE FROM users
            WHERE _id = :id AND type = 'user'
        """), {'id': 'user:async-123'})

        if result.rowcount > 0:
            print("✅ 删除成功")
        else:
            print("❌ 文档不存在")

        await conn.commit()

    await engine.dispose()

asyncio.run(delete_user())
```

## 并发操作

### 并发查询

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def concurrent_queries():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        # 并发执行多个查询
        tasks = [
            conn.execute(text("SELECT * FROM users WHERE type = 'user' AND age > :age"), {'age': 20}),
            conn.execute(text("SELECT * FROM users WHERE type = 'user' AND age < :age"), {'age': 30}),
            conn.execute(text("SELECT COUNT(*) as count FROM users WHERE type = 'user'")),
        ]

        results = await asyncio.gather(*tasks)

        for i, result in enumerate(results):
            print(f"查询 {i+1} 结果数: {result.rowcount}")

    await engine.dispose()

asyncio.run(concurrent_queries())
```

### 并发插入

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
import uuid

async def concurrent_inserts():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        # 生成多个用户数据
        users_data = [
            {
                'id': f'user:concurrent-{uuid.uuid4()}',
                'name': f'User{i}',
                'age': 20 + i,
                'email': f'user{i}@example.com'
            }
            for i in range(10)
        ]

        # 并发插入
        tasks = []
        for user_data in users_data:
            task = conn.execute(text("""
                INSERT INTO users (_id, name, age, email, type)
                VALUES (:id, :name, :age, :email, 'user')
            """), user_data)
            tasks.append(task)

        await asyncio.gather(*tasks)
        await conn.commit()
        print(f"✅ 并发插入 {len(users_data)} 条记录")

    await engine.dispose()

asyncio.run(concurrent_inserts())
```

## 异步事务管理

### 自动提交

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def auto_commit():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    # 使用 begin() 自动提交
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO users (_id, name, age, type)
            VALUES (:id, :name, :age, 'user')
        """), {
            'id': 'user:auto-123',
            'name': 'Auto User',
            'age': 28
        })
        # 自动 commit

    await engine.dispose()

asyncio.run(auto_commit())
```

### 手动事务

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def manual_transaction():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        try:
            await conn.execute(text("""
                INSERT INTO users (_id, name, age, type)
                VALUES (:id1, :name1, :age1, 'user')
            """), {'id1': 'user:tx-1', 'name1': 'Alice', 'age1': 30})

            await conn.execute(text("""
                INSERT INTO orders (_id, user_id, amount, type)
                VALUES (:id2, :user_id, :amount, 'order')
            """), {'id2': 'order:tx-1', 'user_id': 'user:tx-1', 'amount': 99.99})

            # 提交事务
            await conn.commit()
            print("✅ 异步事务提交成功")

        except Exception as e:
            # 回滚事务
            await conn.rollback()
            print(f"❌ 异步事务回滚: {e}")

    await engine.dispose()

asyncio.run(manual_transaction())
```

## 异步上下文管理器

### 推荐模式

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def recommended_pattern():
    """推荐的异步使用模式"""
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    try:
        async with engine.connect() as conn:
            # 执行操作
            await conn.execute(text("..."))
            await conn.commit()
    finally:
        # 确保资源释放
        await engine.dispose()

asyncio.run(recommended_pattern())
```

### 使用 async with (推荐)

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def use_async_with():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        # 在这个块中操作
        await conn.execute(text("INSERT INTO ..."))
        await conn.commit()
        print("✅ 操作完成")

    # 引擎自动.dispose()

asyncio.run(use_async_with())
```

## 错误处理

### 异常捕获

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from sqlalchemy_couchdb.exceptions import CouchDBError

async def handle_errors():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    try:
        async with engine.connect() as conn:
            await conn.execute(text("INSERT INTO ..."))
            await conn.commit()
    except CouchDBError as e:
        print(f"CouchDB 异步错误: {e}")
    except Exception as e:
        print(f"通用异步错误: {e}")
    finally:
        await engine.dispose()

asyncio.run(handle_errors())
```

### 异步重试机制

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def async_retry_update(user_id, new_age, max_retries=3):
    """异步重试更新"""
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    for attempt in range(max_retries):
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("""
                    UPDATE users
                    SET age = :age
                    WHERE _id = :id AND type = 'user'
                    RETURNING *
                """), {
                    'id': user_id,
                    'age': new_age
                })

                if result.rowcount > 0:
                    await conn.commit()
                    return result.fetchone()
                else:
                    raise Exception("文档不存在")

        except Exception as e:
            if attempt == max_retries - 1:
                raise
            print(f"尝试 {attempt + 1} 失败: {e}，重试中...")
            await asyncio.sleep(0.1)
    finally:
        await engine.dispose()

# 使用
asyncio.run(async_retry_update('user:async-123', 35))
```

## 性能优化

### 1. 使用连接池

```python
engine = create_async_engine(
    'couchdb+async://admin:password@localhost:5984/mydb',
    pool_size=20,          # 增加异步池大小
    max_overflow=30,
    pool_recycle=1800,     # 较短回收时间
)
```

### 2. 合理使用并发

```python
# ✅ 好：合理并发
tasks = [query_task(i) for i in range(10)]
results = await asyncio.gather(*tasks)

# ❌ 坏：过多并发
tasks = [query_task(i) for i in range(1000)]  # 可能耗尽资源
```

### 3. 避免 N+1 查询

```python
# ✅ 好：预查询
all_users = await conn.execute(text("SELECT _id FROM users WHERE type = 'user'"))
user_ids = [row._id for row in all_users]

# ❌ 坏：N+1 查询
for user_id in user_ids:
    result = await conn.execute(text("SELECT * FROM users WHERE _id = :id"), {'id': user_id})
```

## 注意事项

### Greenlet 机制

异步模式使用 greenlet 机制：

```python
# ✅ 正确：结果已缓存，可同步迭代
result = await conn.execute(text("SELECT * FROM users"))
for row in result:  # 同步迭代
    print(row.name)

# ❌ 错误：不要使用 async for
# result = await conn.execute(text("SELECT * FROM users"))
# async for row in result:  # 错误！
```

### 连接释放

```python
async def cleanup_example():
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    try:
        async with engine.connect() as conn:
            # 操作
            pass
    finally:
        # 确保释放资源
        await engine.dispose()

asyncio.run(cleanup_example())
```

## 下一步

- [同步操作](sync-operations.md)
- [类型映射](type-mapping.md)
- [混合数据库模式](hybrid-mode.md)

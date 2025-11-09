# 高级特性示例

## 概述

本文档展示 SQLAlchemy CouchDB 方言的高级特性和最佳实践。

## 目录

1. [复杂查询](#复杂查询)
2. [批量操作](#批量操作)
3. [事务管理](#事务管理)
4. [错误处理](#错误处理)
5. [性能优化](#性能优化)
6. [自定义类型](#自定义类型)
7. [并发操作](#并发操作)
8. [监控和日志](#监控和日志)

## 复杂查询

### 1. 多条件查询

```python
from sqlalchemy import text

def complex_where_query(engine):
    """复杂 WHERE 条件查询"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM users
            WHERE type = 'user'
              AND age > 25
              AND age < 40
              AND (status = 'active' OR status = 'pending')
              AND name IN ('Alice', 'Bob', 'Charlie')
            ORDER BY age DESC, name ASC
            LIMIT 20
        """))

        users = result.fetchall()
        print(f"找到 {len(users)} 个用户")

        for user in users:
            print(f"{user.name} ({user.age} 岁) - {user.status}")

        return users
```

### 2. 分页查询

```python
def paginated_query(engine, page=1, page_size=10):
    """分页查询"""
    offset = (page - 1) * page_size

    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM users
            WHERE type = 'user'
            ORDER BY _id
            LIMIT :limit
            OFFSET :offset
        """), {
            'limit': page_size,
            'offset': offset
        })

        users = result.fetchall()

        # 获取总数（用于分页导航）
        count_result = conn.execute(text("""
            SELECT COUNT(*) as total
            FROM users
            WHERE type = 'user'
        """))

        total = count_result.fetchone().total
        total_pages = (total + page_size - 1) // page_size

        print(f"第 {page}/{total_pages} 页，每页 {page_size} 条，共 {total} 条")

        return users, total, total_pages

# 使用
users, total, pages = paginated_query(engine, page=2, page_size=10)
```

### 3. 聚合查询（视图）

```python
def aggregate_query(engine):
    """聚合查询（使用视图）"""
    with engine.connect() as conn:
        # 注意：CouchDB 不支持原生 GROUP BY
        # 需要使用 MapReduce 视图

        # 获取所有用户
        users_result = conn.execute(text("""
            SELECT * FROM users WHERE type = 'user'
        """))

        users = users_result.fetchall()

        # 在应用层聚合
        age_groups = {}
        for user in users:
            if user.age < 20:
                group = 'teen'
            elif user.age < 40:
                group = 'adult'
            else:
                group = 'senior'

            if group not in age_groups:
                age_groups[group] = {'count': 0, 'total_age': 0}

            age_groups[group]['count'] += 1
            age_groups[group]['total_age'] += user.age

        # 计算平均值
        for group in age_groups:
            data = age_groups[group]
            data['avg_age'] = data['total_age'] / data['count']

        print("年龄组统计:")
        for group, data in age_groups.items():
            print(f"{group}: {data['count']} 人，平均年龄 {data['avg_age']:.1f}")

        return age_groups
```

## 批量操作

### 1. 批量插入

```python
def batch_insert(engine, num_users=1000):
    """批量插入用户"""
    import uuid
    from datetime import datetime

    users_data = []
    for i in range(num_users):
        users_data.append({
            'id': f'user:batch:{uuid.uuid4()}',
            'name': f'User{i}',
            'age': 20 + (i % 50),  # 20-69 岁
            'email': f'user{i}@example.com',
            'status': 'active' if i % 3 == 0 else 'inactive',
            'created_at': datetime.now().isoformat(),
            'type': 'user'
        })

    import time
    start = time.time()

    with engine.connect() as conn:
        # 批量插入
        conn.execute(text("""
            INSERT INTO users (_id, name, age, email, status, created_at, type)
            VALUES (:id, :name, :age, :email, :status, :created_at, 'user')
        """), users_data)

        conn.commit()

    elapsed = time.time() - start
    throughput = num_users / elapsed

    print(f"批量插入 {num_users} 用户")
    print(f"耗时: {elapsed:.3f}s")
    print(f"吞吐量: {throughput:.1f} docs/s")

    return num_users, elapsed, throughput

# 使用
batch_insert(engine, 5000)
```

### 2. 批量更新

```python
def batch_update(engine, min_age=30):
    """批量更新用户"""
    import time

    # 先查询要更新的用户
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT _id, _rev, age FROM users
            WHERE type = 'user' AND age > :min_age
        """), {'min_age': min_age})

        users_to_update = result.fetchall()

        print(f"找到 {len(users_to_update)} 个用户需要更新")

        # 构建更新文档
        update_docs = []
        for user in users_to_update:
            update_docs.append({
                '_id': user._id,
                '_rev': user._rev,
                'status': 'senior',
                'type': 'user'
            })

    start = time.time()

    # 执行批量更新
    from sqlalchemy_couchdb.client import SyncCouchDBClient
    client = SyncCouchDBClient(
        base_url='http://localhost:5984',
        database='mydb'
    )

    results = client.bulk_docs(update_docs)

    elapsed = time.time() - start
    success_count = sum(1 for r in results if r.get('ok'))

    print(f"批量更新完成")
    print(f"成功: {success_count}/{len(users_to_update)}")
    print(f"耗时: {elapsed:.3f}s")

    return success_count

# 使用
batch_update(engine, min_age=30)
```

### 3. 批量删除

```python
def batch_delete(engine, max_age=25):
    """批量删除用户"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT _id, _rev FROM users
            WHERE type = 'user' AND age < :max_age
        """), {'max_age': max_age})

        users_to_delete = result.fetchall()

        print(f"找到 {len(users_to_delete)} 个用户需要删除")

        # 批量删除
        from sqlalchemy_couchdb.client import SyncCouchDBClient
        client = SyncCouchDBClient(
            base_url='http://localhost:5984',
            database='mydb'
        )

        delete_docs = []
        for user in users_to_delete:
            delete_docs.append({
                '_id': user._id,
                '_rev': user._rev,
                '_deleted': True
            })

        results = client.bulk_docs(delete_docs)

        success_count = sum(1 for r in results if r.get('ok'))

        print(f"批量删除完成")
        print(f"成功: {success_count}/{len(users_to_delete)}")

        return success_count

# 使用
batch_delete(engine, max_age=20)
```

## 事务管理

### 1. 简单事务

```python
def simple_transaction(engine):
    """简单事务"""
    with engine.connect() as conn:
        try:
            # 开始事务（在 CouchDB 中是 no-op）
            conn.execute(text("""
                INSERT INTO users (_id, name, age, type)
                VALUES (:id1, :name1, :age1, 'user')
            """), {
                'id1': 'user:tx:1',
                'name1': 'Alice',
                'age1': 30
            })

            # 插入相关订单
            conn.execute(text("""
                INSERT INTO orders (_id, user_id, amount, type)
                VALUES (:id2, :user_id, :amount, 'order')
            """), {
                'id2': 'order:tx:1',
                'user_id': 'user:tx:1',
                'amount': 99.99
            })

            # 提交事务
            conn.commit()
            print("✅ 事务提交成功")

        except Exception as e:
            # 回滚事务
            conn.rollback()
            print(f"❌ 事务回滚: {e}")

# 使用
simple_transaction(engine)
```

### 2. 长事务

```python
def long_transaction(engine):
    """长事务（分批处理）"""
    with engine.connect() as conn:
        try:
            batch_size = 100
            total_users = 1000

            for i in range(0, total_users, batch_size):
                batch = [
                    {
                        'id': f'user:long:tx:{j}',
                        'name': f'User{j}',
                        'age': 20 + (j % 50),
                        'type': 'user'
                    }
                    for j in range(i, min(i + batch_size, total_users))
                ]

                # 批量插入
                conn.execute(text("""
                    INSERT INTO users (_id, name, age, type)
                    VALUES (:id, :name, :age, 'user')
                """), batch)

                print(f"已处理 {min(i + batch_size, total_users)}/{total_users} 用户")

            # 提交所有批次
            conn.commit()
            print("✅ 长事务提交成功")

        except Exception as e:
            conn.rollback()
            print(f"❌ 长事务回滚: {e}")
            # 注意：CouchDB 文档级原子性，无法回滚单个文档
            # 实际生产中应使用补偿事务

# 使用
long_transaction(engine)
```

## 错误处理

### 1. 乐观锁处理

```python
def optimistic_lock_retry(engine, user_id, new_age, max_retries=3):
    """带重试的乐观锁更新"""
    import time

    for attempt in range(max_retries):
        with engine.connect() as conn:
            try:
                # 查询当前文档
                result = conn.execute(text("""
                    SELECT * FROM users
                    WHERE _id = :id AND type = 'user'
                """), {'id': user_id})

                if result.rowcount == 0:
                    print(f"用户 {user_id} 不存在")
                    return None

                user = result.fetchone()
                current_rev = user._rev

                # 尝试更新
                update_result = conn.execute(text("""
                    UPDATE users
                    SET age = :age
                    WHERE _id = :id AND type = 'user'
                    RETURNING *
                """), {
                    'id': user_id,
                    'age': new_age
                })

                if update_result.rowcount > 0:
                    # 更新成功
                    conn.commit()
                    updated_user = update_result.fetchone()
                    print(f"✅ 更新成功 (尝试 {attempt + 1})")
                    print(f"  新版本: {updated_user._rev}")
                    return updated_user
                else:
                    # 可能是版本冲突
                    raise Exception("文档版本冲突")

            except Exception as e:
                conn.rollback()

                if attempt == max_retries - 1:
                    print(f"❌ 更新失败，已重试 {max_retries} 次: {e}")
                    raise

                print(f"⚠️ 尝试 {attempt + 1} 失败: {e}，重试中...")
                time.sleep(0.1)  # 短暂等待

# 使用
user = optimistic_lock_retry(engine, 'user:retry:1', 35)
```

### 2. 完整错误处理

```python
def robust_operation(engine, user_id, data):
    """健壮的操作（多种错误处理）"""
    from sqlalchemy_couchdb.exceptions import (
        CouchDBError,
        NotFoundError,
        DocumentConflictError,
        ConnectionError
    )

    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                UPDATE users
                SET age = :age, name = :name
                WHERE _id = :id AND type = 'user'
                RETURNING *
            """), {
                'id': user_id,
                'age': data.get('age'),
                'name': data.get('name')
            })

            if result.rowcount == 0:
                # 文档不存在
                raise NotFoundError(f"用户 {user_id} 不存在")

            updated_user = result.fetchone()
            conn.commit()

            print(f"✅ 更新成功: {updated_user.name}")
            return updated_user

    except NotFoundError as e:
        print(f"❌ {e}")
        # 用户不存在，创建新用户
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO users (_id, name, age, type)
                VALUES (:id, :name, :age, 'user')
            """), {
                'id': user_id,
                'name': data.get('name'),
                'age': data.get('age')
            })
            conn.commit()
            print(f"✅ 创建新用户: {data.get('name')}")

    except DocumentConflictError as e:
        print(f"❌ 文档版本冲突: {e}")
        # 重新获取最新版本并重试
        latest_data = {**data, '_rev': None}
        return robust_operation(engine, user_id, latest_data)

    except ConnectionError as e:
        print(f"❌ 连接错误: {e}")
        # 记录错误，等待手动处理
        with open('error_log.txt', 'a') as f:
            f.write(f"{user_id}: {data}\n")
        return None

    except CouchDBError as e:
        print(f"❌ CouchDB 错误: {e}")
        raise

    except Exception as e:
        print(f"❌ 未知错误: {e}")
        raise

# 使用
robust_operation(engine, 'user:error:1', {'name': 'Alice', 'age': 31})
```

## 性能优化

### 1. 连接池优化

```python
def optimized_connection_pool():
    """优化的连接池配置"""
    from sqlalchemy import create_engine

    # 高并发配置
    engine = create_engine(
        'couchdb://admin:password@localhost:5984/mydb',
        pool_size=20,              # 池大小
        max_overflow=30,           # 最大溢出
        pool_recycle=1800,         # 30分钟回收
        pool_timeout=60,           # 超时时间
        pool_pre_ping=True,        # 预检查
    )

    print(f"连接池配置:")
    print(f"  池大小: {engine.pool.size()}")
    print(f"  最大溢出: {engine.pool.overflow()}")

    return engine

# 使用
engine = optimized_connection_pool()
```

### 2. 查询优化

```python
def optimized_queries(engine):
    """优化的查询"""
    import time

    # 只查询必要字段
    start = time.time()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT _id, name, age FROM users
            WHERE type = 'user' AND age > 25
            ORDER BY age DESC
            LIMIT 100
        """))
        users = result.fetchall()
    elapsed = time.time() - start

    print(f"✅ 优化查询 1: {elapsed:.3f}s ({len(users)} 结果)")

    # 使用 LIMIT
    start = time.time()
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM users
            WHERE type = 'user'
            LIMIT 1000
        """))
        users = result.fetchall()
    elapsed = time.time() - start

    print(f"✅ 优化查询 2: {elapsed:.3f}s ({len(users)} 结果)")

# 使用
optimized_queries(engine)
```

## 自定义类型

### 1. 邮箱类型

```python
from sqlalchemy import types
from sqlalchemy_couchdb.types import CouchDBString

class CouchDBEmail(CouchDBString):
    """邮箱类型"""

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None

            email = str(value)

            # 简单邮箱验证
            if '@' not in email:
                raise ValueError(f"无效的邮箱格式: {email}")

            return email

        return process

# 使用自定义类型
from sqlalchemy import Table, Column, MetaData

metadata = MetaData()
users = Table('users', metadata,
    Column('_id', CouchDBString, primary_key=True),
    Column('email', CouchDBEmail()),  # 使用自定义邮箱类型
    Column('type', CouchDBString)
)

# 创建表
metadata.create_all(engine)

# 插入数据（会自动验证邮箱）
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (_id, email, type)
        VALUES (:id, :email, 'user')
    """), {
        'id': 'user:email:1',
        'email': 'alice@example.com'  # 有效邮箱
    })
    conn.commit()

    # 无效邮箱会抛出异常
    try:
        conn.execute(text("""
            INSERT INTO users (_id, email, type)
            VALUES (:id, :email, 'user')
        """), {
            'id': 'user:email:2',
            'email': 'not-an-email'  # 无效邮箱
        })
        conn.commit()
    except ValueError as e:
        print(f"❌ 邮箱验证失败: {e}")
```

### 2. 枚举类型

```python
from sqlalchemy import Enum
from sqlalchemy_couchdb.types import CouchDBString

class StatusEnum:
    """状态枚举"""
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    PENDING = 'pending'

    @classmethod
    def values(cls):
        return [cls.ACTIVE, cls.INACTIVE, cls.PENDING]

# 创建状态表
users = Table('users', metadata,
    Column('_id', CouchDBString, primary_key=True),
    Column('status', Enum(*StatusEnum.values(), name='status_enum')),  # 枚举类型
    Column('type', CouchDBString)
)

# 使用
with engine.connect() as conn:
    # 插入有效状态
    conn.execute(text("""
        INSERT INTO users (_id, status, type)
        VALUES (:id, :status, 'user')
    """), {
        'id': 'user:enum:1',
        'status': StatusEnum.ACTIVE
    })
    conn.commit()

    # 查询状态
    result = conn.execute(text("""
        SELECT * FROM users WHERE status = :status
    """), {'status': StatusEnum.ACTIVE})

    for user in result:
        print(f"用户 {user._id} 状态: {user.status}")
```

## 并发操作

### 1. 同步并发

```python
import concurrent.futures
import threading

def concurrent_queries(engine, query_count=10):
    """并发查询"""
    import time

    results = []
    errors = []

    start = time.time()

    # 使用线程池执行并发查询
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = []

        for i in range(query_count):
            future = executor.submit(
                query_users,
                engine,
                {'min_age': 20 + i}
            )
            futures.append(future)

        # 等待所有查询完成
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                errors.append(str(e))

    elapsed = time.time() - start

    print(f"并发查询完成")
    print(f"总查询: {query_count}")
    print(f"成功: {len(results)}")
    print(f"失败: {len(errors)}")
    print(f"总耗时: {elapsed:.3f}s")
    print(f"平均每个查询: {elapsed/query_count:.3f}s")

    return results, errors

def query_users(engine, params):
    """查询用户的函数"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) as count FROM users
            WHERE type = 'user' AND age > :min_age
        """), params)

        return result.fetchone().count

# 使用
concurrent_queries(engine, query_count=50)
```

### 2. 异步并发

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def async_concurrent_queries(async_engine, query_count=10):
    """异步并发查询"""
    results = []

    async with async_engine.connect() as conn:
        # 创建并发任务
        tasks = []
        for i in range(query_count):
            task = async_query_users(
                conn,
                {'min_age': 20 + i}
            )
            tasks.append(task)

        # 等待所有任务完成
        results = await asyncio.gather(*tasks)

    print(f"异步并发查询完成: {len(results)} 查询")
    return results

async def async_query_users(async_conn, params):
    """异步查询用户"""
    result = await async_conn.execute(text("""
        SELECT COUNT(*) as count FROM users
        WHERE type = 'user' AND age > :min_age
    """), params)

    return result.fetchone().count

# 使用
async_engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')
results = asyncio.run(async_concurrent_queries(async_engine, query_count=50))
```

## 监控和日志

### 1. 查询监控

```python
import time
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('couchdb_monitor')

class QueryMonitor:
    """查询监控器"""

    def __init__(self):
        self.query_count = 0
        self.total_time = 0
        self.slow_queries = []

    def execute_query(self, conn, query, params=None, slow_threshold=0.1):
        """执行查询并监控"""
        self.query_count += 1
        start = time.time()

        try:
            result = conn.execute(text(query), params or {})
            elapsed = time.time() - start
            self.total_time += elapsed

            # 记录慢查询
            if elapsed > slow_threshold:
                self.slow_queries.append({
                    'query': query[:100],
                    'elapsed': elapsed,
                    'params': params
                })
                logger.warning(f"慢查询: {elapsed:.3f}s - {query[:100]}")

            logger.info(f"查询 {self.query_count}: {elapsed:.3f}s")

            return result

        except Exception as e:
            elapsed = time.time() - start
            logger.error(f"查询失败: {elapsed:.3f}s - {e}")
            raise

    def get_stats(self):
        """获取统计信息"""
        avg_time = self.total_time / self.query_count if self.query_count > 0 else 0

        return {
            'total_queries': self.query_count,
            'total_time': self.total_time,
            'avg_time': avg_time,
            'slow_query_count': len(self.slow_queries)
        }

    def print_report(self):
        """打印报告"""
        stats = self.get_stats()
        print(f"\n{'='*50}")
        print(f"查询监控报告")
        print(f"{'='*50}")
        print(f"总查询数: {stats['total_queries']}")
        print(f"总耗时: {stats['total_time']:.3f}s")
        print(f"平均耗时: {stats['avg_time']:.3f}s")
        print(f"慢查询数: {stats['slow_query_count']}")

        if self.slow_queries:
            print(f"\n慢查询列表:")
            for i, query in enumerate(self.slow_queries[:10], 1):
                print(f"{i}. {query['elapsed']:.3f}s - {query['query']}")

# 使用
monitor = QueryMonitor()

with engine.connect() as conn:
    # 执行查询
    monitor.execute_query(conn, """
        SELECT * FROM users WHERE type = 'user' LIMIT 100
    """)

    monitor.execute_query(conn, """
        SELECT * FROM users WHERE age > 30
    """)

# 打印报告
monitor.print_report()
```

## 总结

这些高级特性示例展示了：

1. **复杂查询** - 多条件、分页、聚合
2. **批量操作** - 高效插入、更新、删除
3. **事务管理** - 简单事务、长事务
4. **错误处理** - 乐观锁、完整错误处理
5. **性能优化** - 连接池、查询优化
6. **自定义类型** - 邮箱类型、枚举类型
7. **并发操作** - 同步并发、异步并发
8. **监控日志** - 查询监控、慢查询检测

这些示例可以帮助您更好地理解和使用 SQLAlchemy CouchDB 方言的高级功能。

## 下一步

- [API 参考](../api/compiler.md)
- [性能优化指南](../dev/performance.md)
- [测试指南](../dev/testing.md)

# 性能优化指南

## 概述

SQLAlchemy CouchDB 方言的性能优化涉及多个层面：连接管理、查询优化、索引设计、批量操作等。

## 基准性能

### Phase 1 性能指标

| 操作 | 延迟 | 吞吐量 | 说明 |
|------|------|--------|------|
| 简单 SELECT | < 50ms | ~200 qps | 单表，无 JOIN |
| INSERT (单条) | < 30ms | ~300 qps | 单文档 |
| INSERT (批量 100) | < 100ms | ~1000 docs/s | 使用 bulk_docs |
| UPDATE | < 40ms | ~250 qps | 包含乐观锁检查 |
| DELETE | < 30ms | ~300 qps | 标记删除 |

### Phase 2 混合模式性能

| 操作 | 延迟 | 说明 |
|------|------|------|
| 简单查询（CouchDB） | < 50ms | 性能不下降 |
| 复杂查询（PostgreSQL） | 取决于 PG | JOIN 等操作优异 |
| 双写（INSERT） | < 100ms | 可接受的额外开销 |
| 一致性检查（1000 docs） | < 10s | 后台异步执行 |

## 连接优化

### 连接池配置

```python
from sqlalchemy import create_engine

# 推荐配置
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    pool_size=10,              # 基础连接数
    max_overflow=20,           # 最大溢出连接
    pool_recycle=3600,         # 连接回收时间（1小时）
    pool_timeout=30,           # 获取连接超时
    pool_pre_ping=True,        # 预检查连接
)

# 高并发配置
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    pool_size=20,              # 增加池大小
    max_overflow=50,           # 支持更多并发
    pool_recycle=1800,         # 更频繁回收
    pool_pre_ping=True,        # 启用预检查
)
```

### 监控连接池

```python
def check_pool_performance(engine):
    """检查连接池性能"""
    pool = engine.pool

    print(f"池大小: {pool.size()}")
    print("已借出连接:", pool.checkedout())
    print("已返回连接:", pool.returned())
    print("溢出连接:", pool.overflow())

    # 检查是否接近满载
    if pool.checkedout() > pool.size() * 0.8:
        print("⚠️  连接池使用率超过 80%，建议增加 pool_size")

check_pool_performance(engine)
```

### 连接重用

```python
# ✅ 推荐：重用连接
def process_batch(items):
    with engine.connect() as conn:
        for item in items:
            result = conn.execute(text("SELECT * FROM users WHERE _id = :id"), {'id': item})
            process_result(result)

# ❌ 避免：频繁创建连接
def process_batch_inefficient(items):
    for item in items:
        with engine.connect() as conn:  # 每次创建新连接
            result = conn.execute(text("SELECT * FROM users WHERE _id = :id"), {'id': item})
            process_result(result)
```

## 查询优化

### 1. 只查询必要字段

```python
# ✅ 高效：只查询需要的字段
result = conn.execute(text("""
    SELECT _id, name, age
    FROM users
    WHERE type = 'user'
"""))

# ❌ 低效：查询所有字段
result = conn.execute(text("""
    SELECT *
    FROM users
    WHERE type = 'user'
"""))
```

### 2. 使用 LIMIT

```python
# ✅ 总是限制结果集大小
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
    LIMIT 100  -- 限制返回数量
"""))

# ❌ 无限制查询
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
"""))
```

### 3. 使用索引字段

```python
# ✅ 高效：ORDER BY 字段有索引
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
    ORDER BY age DESC  -- age 字段有索引
    LIMIT 100
"""))

# ❌ 低效：ORDER BY 无索引字段
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
    ORDER BY name ASC  -- name 字段无索引
    LIMIT 100
"""))
```

### 4. 精确的 WHERE 条件

```python
# ✅ 高效：精确筛选
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user' AND age > 25 AND age < 35
"""))

# ❌ 低效：宽泛筛选
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
"""))
```

## 索引优化

### 自动索引创建

```python
# ORDER BY 会自动创建索引
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
    ORDER BY age DESC, name ASC  -- 自动创建复合索引
"""))

# 手动创建常用索引
from sqlalchemy_couchdb.client import SyncCouchDBClient

client = SyncCouchDBClient(
    base_url='http://localhost:5984',
    database='mydb'
)

# 单字段索引
client.ensure_index('age', name='age-index')

# 复合索引（常用查询组合）
client.ensure_index(['type', 'age'], name='type-age-index')

# 部分索引（CouchDB 高级特性）
# 需要手动创建设计文档
```

### 索引策略

```python
# ✅ 高频查询字段
for field in ['type', 'age', 'created_at', 'status']:
    client.ensure_index(field)

# ✅ 常用排序字段
client.ensure_index('age')
client.ensure_index('created_at')

# ✅ 复合查询字段
client.ensure_index(['type', 'age'])
client.ensure_index(['status', 'created_at'])
```

### 索引性能测试

```python
def benchmark_index_performance(client):
    """测试索引性能"""
    import time

    # 测试无索引查询
    start = time.time()
    client.find({"type": {"$eq": "user"}}, limit=1000)
    no_index_time = time.time() - start

    # 创建索引
    client.ensure_index('type')

    # 测试有索引查询
    start = time.time()
    client.find({"type": {"$eq": "user"}}, limit=1000)
    with_index_time = time.time() - start

    print(f"无索引查询: {no_index_time:.3f}s")
    print(f"有索引查询: {with_index_time:.3f}s")
    print(f"性能提升: {(no_index_time / with_index_time):.2f}x")

benchmark_index_performance(client)
```

## 批量操作优化

### 批量插入

```python
# ✅ 高效：批量插入
users_data = [
    {'id': f'user:{i}', 'name': f'User{i}', 'age': i, 'type': 'user'}
    for i in range(1000)
]

with engine.connect() as conn:
    # 一次调用插入所有数据
    conn.execute(text("""
        INSERT INTO users (_id, name, age, type)
        VALUES (:id, :name, :age, 'user')
    """), users_data)
    conn.commit()
    print(f"✅ 批量插入 {len(users_data)} 条记录")

# ❌ 低效：循环插入
with engine.connect() as conn:
    for data in users_data:
        conn.execute(text("""
            INSERT INTO users (_id, name, age, type)
            VALUES (:id, :name, :age, 'user')
        """), data)
    conn.commit()
```

### 分批处理大数据集

```python
def insert_large_dataset(engine, data, batch_size=1000):
    """分批插入大数据集"""
    with engine.connect() as conn:
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            conn.execute(text("INSERT INTO ..."), batch)
            conn.commit()  # 每批提交一次
            print(f"已插入 {i + len(batch)} / {len(data)} 条记录")

# 使用
insert_large_dataset(engine, all_data, batch_size=500)
```

### 批量更新

```python
# 获取所有要更新的文档
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT _id, _rev FROM users
        WHERE type = 'user' AND status = 'pending'
    """))
    docs_to_update = result.fetchall()

# 批量更新
for i in range(0, len(docs_to_update), 100):
    batch = docs_to_update[i:i + 100]

    # 更新每个文档
    updated_docs = []
    for doc in batch:
        updated_doc = {
            '_id': doc._id,
            '_rev': doc._rev,
            'status': 'processed',
            'type': 'user'
        }
        updated_docs.append(updated_doc)

    # 批量提交
    client.bulk_docs(updated_docs)
```

## 内存优化

### 流式处理大结果集

```python
# ✅ 内存友好：流式处理
def process_large_result_set(engine):
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT * FROM large_table
            WHERE type = 'data'
        """))

        while True:
            # 分批获取
            batch = result.fetchmany(1000)
            if not batch:
                break

            # 处理批次
            for row in batch:
                process_row(row)

# ❌ 内存占用高：一次性加载
def process_large_result_set_inefficient(engine):
    with engine.connect() as conn:
        result = conn.execute(text("SELECT * FROM large_table"))
        all_rows = result.fetchall()  # 全部加载到内存

        for row in all_rows:
            process_row(row)
```

### 异步并发控制

```python
import asyncio
from asyncio import Semaphore

# 限制并发数
MAX_CONCURRENT = 10
semaphore = Semaphore(MAX_CONCURRENT)

async def concurrent_query(query):
    """并发查询（限制并发数）"""
    async with semaphore:
        # 执行查询
        async with engine.connect() as conn:
            result = await conn.execute(query)
            return result.fetchall()

async def run_concurrent_queries(queries):
    """运行并发查询"""
    tasks = [concurrent_query(q) for q in queries]
    results = await asyncio.gather(*tasks)
    return results

# 使用
queries = [text("SELECT * FROM users WHERE age > :age") for age in range(20, 30)]
results = asyncio.run(run_concurrent_queries(queries))
```

## 缓存优化

### 查询缓存

```python
from functools import lru_cache
from datetime import datetime, timedelta

class QueryCache:
    """简单的查询缓存"""
    def __init__(self, ttl=300):  # 5分钟 TTL
        self.cache = {}
        self.ttl = ttl

    def get(self, key):
        if key in self.cache:
            value, timestamp = self.cache[key]
            if datetime.now() - timestamp < timedelta(seconds=self.ttl):
                return value
            else:
                del self.cache[key]
        return None

    def set(self, key, value):
        self.cache[key] = (value, datetime.now())

    def clear(self):
        self.cache.clear()

# 使用缓存
cache = QueryCache(ttl=300)

def get_users(conn, min_age):
    cache_key = f"users_age_{min_age}"
    result = cache.get(cache_key)

    if result is None:
        result = conn.execute(
            text("SELECT * FROM users WHERE age > :age"),
            {'age': min_age}
        ).fetchall()
        cache.set(cache_key, result)

    return result
```

### Redis 缓存（生产环境）

```python
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def cached_query(conn, key, query, params):
    """使用 Redis 缓存查询"""
    # 先从缓存获取
    cached_result = redis_client.get(key)
    if cached_result:
        return json.loads(cached_result)

    # 缓存未命中，查询数据库
    result = conn.execute(query, params).fetchall()

    # 转换为可序列化格式
    serialized_result = [dict(row) for row in result]

    # 存入缓存（TTL: 5分钟）
    redis_client.setex(key, 300, json.dumps(serialized_result))

    return serialized_result

# 使用
result = cached_query(
    conn,
    "users_over_25",
    text("SELECT * FROM users WHERE age > :age"),
    {'age': 25}
)
```

## 异步性能优化

### 批量异步操作

```python
async def batch_async_insert(engine, data):
    """批量异步插入"""
    async with engine.connect() as conn:
        # 并发插入（限制并发数）
        semaphore = asyncio.Semaphore(10)
        tasks = []

        for item in data:
            task = insert_single_item(conn, item, semaphore)
            tasks.append(task)

        await asyncio.gather(*tasks)
        await conn.commit()

async def insert_single_item(conn, item, semaphore):
    """插入单个项目"""
    async with semaphore:
        await conn.execute(text("""
            INSERT INTO users (_id, name, type)
            VALUES (:id, :name, 'user')
        """), item)
```

### 异步连接池

```python
from sqlalchemy.ext.asyncio import create_async_engine

# 优化异步连接池
async_engine = create_async_engine(
    'couchdb+async://admin:password@localhost:5984/mydb',
    pool_size=20,              # 增加池大小
    max_overflow=30,           # 允许更多溢出
    pool_recycle=1800,         # 30分钟回收
    pool_pre_ping=True,        # 预检查
)
```

## 性能监控

### 监控指标

```python
import time
from contextlib import contextmanager

@contextmanager
def timer(name):
    """计时器上下文管理器"""
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"{name}: {elapsed:.3f}s")

# 使用
with timer("查询用户"):
    result = conn.execute(text("SELECT * FROM users"))

with timer("批量插入"):
    conn.execute(text("INSERT INTO ..."), data)
    conn.commit()
```

### 性能分析

```python
import cProfile
import pstats

def profile_query():
    """分析查询性能"""
    profiler = cProfile.Profile()
    profiler.enable()

    # 执行查询
    result = conn.execute(text("SELECT * FROM users WHERE age > 25"))

    profiler.disable()
    stats = pstats.Stats(profiler)
    stats.sort_stats('cumulative')
    stats.print_stats(10)  # 显示前 10 个最耗时的函数

profile_query()
```

## 慢查询优化

### 识别慢查询

```python
import logging

# 启用慢查询日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('slow_queries')

def log_slow_query(query, execution_time):
    """记录慢查询"""
    if execution_time > 0.1:  # 超过 100ms
        logger.warning(
            "慢查询检测: %s (耗时: %.3fs)",
            str(query), execution_time
        )

def execute_with_monitoring(conn, query, params=None):
    """带监控的执行"""
    start = time.time()
    try:
        result = conn.execute(query, params or {})
        execution_time = time.time() - start
        log_slow_query(query, execution_time)
        return result
    finally:
        pass
```

## 生产环境优化

### 1. 连接池调优

```python
# 生产环境推荐配置
PRODUCTION_ENGINE = create_engine(
    'couchdb://admin:password@localhost:5984/production',
    pool_size=20,              # 基于 CPU 核心数
    max_overflow=50,           # 处理突发负载
    pool_recycle=1800,         # 30分钟回收
    pool_timeout=60,           # 增加超时时间
    pool_pre_ping=True,        # 确保连接有效
    max_identifier_length=256,  # 支持长标识符
)
```

### 2. HTTP 客户端优化

```python
from sqlalchemy_couchdb.client import SyncCouchDBClient
import httpx

# 优化的 HTTP 客户端配置
client = SyncCouchDBClient(
    base_url='http://localhost:5984',
    database='mydb',
    timeout=httpx.Timeout(60.0, connect=10.0),
    limits=httpx.Limits(
        max_keepalive_connections=20,
        max_connections=100,
        keepalive_expiry=30
    )
)
```

### 3. 监控和告警

```python
from prometheus_client import Counter, Histogram

# 性能指标
query_counter = Counter('couchdb_queries_total', 'Total queries', ['operation'])
query_duration = Histogram('couchdb_query_duration_seconds', 'Query duration')

def execute_with_metrics(operation):
    """执行查询并记录指标"""
    query_counter.labels(operation=operation).inc()

    with query_duration.time():
        result = conn.execute(text(operation))

    return result

# 使用
result = execute_with_metrics("SELECT * FROM users")
```

## 常见性能陷阱

### 1. N+1 查询

```python
# ❌ 陷阱：N+1 查询
users = conn.execute(text("SELECT * FROM users")).fetchall()
for user in users:
    # 每次循环都执行新查询
    orders = conn.execute(
        text("SELECT * FROM orders WHERE user_id = :id"),
        {'id': user._id}
    ).fetchall()
    print(f"{user.name}: {len(orders)} 订单")

# ✅ 解决：预查询或 JOIN
orders = conn.execute(text("""
    SELECT u.name, o.*
    FROM users u
    LEFT JOIN orders o ON u._id = o.user_id
""")).fetchall()
```

### 2. 过度正则查询

```python
# ❌ 陷阱：LIKE 查询（使用正则，性能差）
result = conn.execute(text("""
    SELECT * FROM users
    WHERE name LIKE '%Alice%'
"""))

# ✅ 解决：前缀匹配
result = conn.execute(text("""
    SELECT * FROM users
    WHERE name LIKE 'Alice%'
"""))

# ✅ 解决：精确匹配或使用全文搜索
result = conn.execute(text("""
    SELECT * FROM users
    WHERE name = 'Alice'
"""))
```

### 3. 过多嵌套 JSON

```python
# ❌ 陷阱：深度嵌套 JSON（难以查询）
user = {
    "profile": {
        "personal": {
            "name": "Alice",
            "age": 30
        },
        "contact": {
            "email": "alice@example.com"
        }
    }
}

# ✅ 解决：扁平化
user = {
    "name": "Alice",
    "age": 30,
    "email": "alice@example.com"
}
```

## 性能测试

### 基准测试脚本

```python
def benchmark_crud_operations(engine):
    """CRUD 操作基准测试"""
    import time

    # INSERT 基准测试
    start = time.time()
    with engine.connect() as conn:
        data = [{'id': f'bench:{i}', 'name': f'User{i}', 'type': 'user'}
                for i in range(1000)]
        conn.execute(text("""
            INSERT INTO users (_id, name, type)
            VALUES (:id, :name, 'user')
        """), data)
        conn.commit()
    insert_time = time.time() - start
    print(f"INSERT 1000 条: {insert_time:.3f}s ({1000/insert_time:.1f} ops/s)")

    # SELECT 基准测试
    start = time.time()
    with engine.connect() as conn:
        for i in range(100):
            result = conn.execute(text("""
                SELECT * FROM users
                WHERE _id = :id
            """), {'id': f'bench:{i}'})
    select_time = time.time() - start
    print(f"SELECT 100 次: {select_time:.3f}s ({100/select_time:.1f} ops/s)")

# 运行基准测试
benchmark_crud_operations(engine)
```

## 总结

### 优化优先级

1. **高优先级**：
   - 正确配置连接池
   - 只查询必要字段
   - 使用索引
   - 批量操作

2. **中优先级**：
   - 实现缓存
   - 流式处理大数据集
   - 限制并发数
   - 优化异步操作

3. **低优先级**：
   - 内存优化
   - 性能监控
   - 慢查询日志
   - 基准测试

### 关键原则

- **测量优于猜测**：使用性能分析工具
- **缓存为王**：合理使用缓存提升性能
- **批量优于单条**：减少网络往返
- **索引必备**：合理设计索引
- **连接复用**：避免连接开销

## 下一步

- [测试指南](testing.md)
- [代码规范](coding-standards.md)
- [API 参考](../api/compiler.md)

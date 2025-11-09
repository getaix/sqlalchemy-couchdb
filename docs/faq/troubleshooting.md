# 故障排查指南

本文档提供常见问题的解决方案和调试技巧。

## 目录

- [连接问题](#连接问题)
- [查询问题](#查询问题)
- [异步问题](#异步问题)
- [混合架构问题](#混合架构问题)
- [性能问题](#性能问题)
- [测试问题](#测试问题)
- [调试技巧](#调试技巧)

---

## 连接问题

### CouchDB 连接失败

**症状**:
```python
httpx.ConnectError: [Errno 61] Connection refused
```

**可能原因**:
1. CouchDB 服务未启动
2. 端口号错误（默认 5984）
3. 防火墙阻止连接

**解决方案**:
```bash
# 1. 检查 CouchDB 是否运行
curl http://localhost:5984/
# 应该返回: {"couchdb":"Welcome",...}

# 2. 检查端口
lsof -i :5984
netstat -an | grep 5984

# 3. 启动 CouchDB
# Docker
docker run -d -p 5984:5984 -e COUCHDB_USER=admin -e COUCHDB_PASSWORD=password couchdb:3

# 系统服务
sudo systemctl start couchdb
```

### 认证错误

**症状**:
```python
sqlalchemy_couchdb.exceptions.OperationalError: HTTP 401: Unauthorized
```

**可能原因**:
1. 用户名或密码错误
2. 数据库访问权限不足
3. URL 格式错误

**解决方案**:
```python
# ✅ 正确的 URL 格式
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

# ❌ 常见错误
engine = create_engine('couchdb://localhost:5984/mydb')  # 缺少凭证
engine = create_engine('couchdb://admin@localhost:5984/mydb')  # 缺少密码

# 使用环境变量（推荐）
import os
url = f"couchdb://{os.getenv('COUCHDB_USER')}:{os.getenv('COUCHDB_PASSWORD')}@localhost:5984/mydb"
engine = create_engine(url)
```

**验证凭证**:
```bash
curl -X GET http://admin:password@localhost:5984/_session
```

### 超时问题

**症状**:
```python
httpx.ReadTimeout: Read timeout
```

**解决方案**:
```python
# 增加超时时间
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    connect_args={
        'timeout': 30.0,  # 30秒超时
    }
)

# 或者在客户端级别设置
from sqlalchemy_couchdb.client import SyncCouchDBClient

client = SyncCouchDBClient(
    'http://admin:password@localhost:5984',
    timeout=30.0
)
```

### 数据库不存在

**症状**:
```python
sqlalchemy_couchdb.exceptions.OperationalError: HTTP 404: Database does not exist
```

**解决方案**:
```bash
# 创建数据库
curl -X PUT http://admin:password@localhost:5984/mydb

# 或在 Python 中
from sqlalchemy_couchdb.client import SyncCouchDBClient

client = SyncCouchDBClient('http://admin:password@localhost:5984')
client.create_database('mydb')
```

---

## 查询问题

### 慢查询优化

**症状**: 查询执行时间过长

**诊断**:
```python
import logging
import time

# 开启日志
logging.basicConfig(level=logging.INFO)

# 测量查询时间
start = time.time()
result = conn.execute(text("SELECT * FROM users WHERE age > :age"), {"age": 25})
rows = list(result)
print(f"查询耗时: {time.time() - start:.2f}秒")
print(f"返回行数: {len(rows)}")
```

**解决方案**:

1. **创建索引**:
```python
from sqlalchemy_couchdb.management import IndexManager

index_manager = IndexManager(client)

# 为经常查询的字段创建索引
index_manager.create_index(
    'mydb',
    fields=['age', 'name'],
    index_name='idx_age_name'
)
```

2. **使用字段选择**:
```python
# ❌ 查询所有字段（慢）
result = conn.execute(text("SELECT * FROM users WHERE age > 25"))

# ✅ 只查询需要的字段（快）
result = conn.execute(text("SELECT name, email FROM users WHERE age > 25"))
```

3. **启用查询缓存**:
```python
from sqlalchemy_couchdb.cache import QueryCache

# 创建缓存
cache = QueryCache(max_size=1000, ttl=300)  # 5分钟 TTL

# 在查询前检查缓存
cache_key = (query_string, params)
if cache_key in cache:
    return cache[cache_key]

# 执行查询并缓存结果
result = conn.execute(query)
rows = list(result)
cache[cache_key] = rows
```

### 索引缺失警告

**症状**:
```
WARNING: No index found for query, using sequential scan
```

**解决方案**:
```python
# 查看现有索引
index_manager.list_indexes('mydb')

# 创建缺失的索引
index_manager.create_index(
    'mydb',
    fields=['age'],
    index_name='idx_age'
)
```

### Mango Query 限制

**不支持的 SQL 功能**:
- JOIN 操作（Phase 1）
- 子查询
- UNION/INTERSECT
- 窗口函数
- 复杂的聚合（需要视图）

**解决方案**:

1. **使用混合架构** (Phase 2):
```python
# 复杂查询会自动路由到 RDBMS
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost/postgres_db'
)
```

2. **客户端处理**:
```python
from sqlalchemy_couchdb.advanced import QueryProcessor

# 获取原始数据
result = conn.execute(text("SELECT * FROM users"))
rows = list(result)

# 客户端聚合
processor = QueryProcessor(rows)
agg_result = processor.group_by(['department'], {'salary': 'avg'})
```

---

## 异步问题

### greenlet 错误

**症状**:
```python
greenlet.error: cannot switch to a different thread
```

**原因**: 异步操作在错误的事件循环中执行

**解决方案**:
```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    # ✅ 使用 async 引擎
    engine = create_async_engine(
        'couchdb+async://admin:password@localhost:5984/mydb'
    )

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT * FROM users"))
        # ✅ 不要使用 async for（异步引擎不支持）
        rows = result.fetchall()  # ✅ 同步迭代

    await engine.dispose()

# ✅ 运行
asyncio.run(main())
```

### 事件循环问题

**症状**:
```python
RuntimeError: This event loop is already running
```

**解决方案**:
```python
# ❌ 不要在已运行的事件循环中使用 asyncio.run()
import asyncio

async def query_data():
    engine = create_async_engine('couchdb+async://...')
    # ...

# ❌ 在 Jupyter Notebook 中
asyncio.run(query_data())  # 错误！

# ✅ 使用 await
await query_data()  # Jupyter 中正确

# ✅ 或使用 nest_asyncio
import nest_asyncio
nest_asyncio.apply()
asyncio.run(query_data())  # 现在可以了
```

### 并发限制

**症状**: 大量并发请求导致性能下降

**解决方案**:
```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine(
        'couchdb+async://admin:password@localhost:5984/mydb',
        pool_size=20,  # 限制连接池大小
        max_overflow=10
    )

    # ✅ 使用 Semaphore 限制并发
    semaphore = asyncio.Semaphore(10)  # 最多 10 个并发

    async def query_with_limit(query):
        async with semaphore:
            async with engine.connect() as conn:
                return await conn.execute(query)

    # 批量查询
    tasks = [query_with_limit(q) for q in queries]
    results = await asyncio.gather(*tasks)

asyncio.run(main())
```

---

## 混合架构问题

### 数据同步失败

**症状**:
```python
DualWriteError: Failed to write to secondary database
```

**诊断**:
```python
from sqlalchemy_couchdb.hybrid import DualWriteManager

manager = DualWriteManager(couchdb_engine, rdbms_engine)

# 检查同步状态
result = manager.write(data)
if not result.success:
    print(f"失败原因: {result.errors}")
    print(f"CouchDB 状态: {result.couchdb_success}")
    print(f"RDBMS 状态: {result.rdbms_success}")
```

**解决方案**:
```python
# 1. 启用重试
manager = DualWriteManager(
    couchdb_engine,
    rdbms_engine,
    retry_config=RetryConfig(max_retries=3)
)

# 2. 使用异步模式
manager = DualWriteManager(
    couchdb_engine,
    rdbms_engine,
    mode=WriteMode.ASYNC  # 异步写入
)

# 3. 检查失败的写入
failed_writes = manager.get_failed_writes()
for write in failed_writes:
    print(f"失败记录: {write}")
    # 手动重试
    manager.retry_failed_write(write)
```

### 路由决策错误

**症状**: 查询被路由到错误的数据库

**诊断**:
```python
from sqlalchemy_couchdb.hybrid import QueryRouter

router = QueryRouter()
analysis = router.analyze_query(query)

print(f"查询复杂度: {analysis.complexity}")
print(f"路由到: {analysis.target_database}")
print(f"原因: {analysis.reason}")
print(f"置信度: {analysis.confidence}")
```

**解决方案**:
```python
# 自定义路由规则
router = QueryRouter(
    complexity_threshold=5,  # 调整复杂度阈值
    prefer_couchdb=True  # 优先使用 CouchDB
)

# 或手动指定路由
with engine.connect() as conn:
    # 强制使用 CouchDB
    result = conn.execute(
        query,
        execution_options={'force_couchdb': True}
    )
```

### 字段映射冲突

**症状**:
```python
FieldMappingError: Conflict in field '_id'
```

**解决方案**:
```python
from sqlalchemy_couchdb.hybrid import FieldMapper

# 自定义字段映射
mapper = FieldMapper(
    id_mapping={'_id': 'document_id', 'id': 'record_id'},
    rev_mapping={'_rev': 'version'}
)

# 应用映射
couchdb_doc = mapper.to_couchdb(rdbms_record)
rdbms_record = mapper.to_rdbms(couchdb_doc)
```

---

## 性能问题

### 批量操作优化

**症状**: 插入大量数据很慢

**解决方案**:
```python
from sqlalchemy import insert

# ❌ 逐条插入（慢）
for user in users:
    conn.execute(insert(users_table).values(user))

# ✅ 批量插入（快 3-10x）
conn.execute(insert(users_table), users)

# ✅ 控制批次大小
def bulk_insert(data, batch_size=100):
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        conn.execute(insert(users_table), batch)
```

### 缓存配置

**症状**: 重复查询性能差

**解决方案**:
```python
from sqlalchemy_couchdb.cache import QueryCache

# 全局缓存
cache = QueryCache(
    max_size=1000,  # 最多缓存 1000 个查询
    ttl=300,  # 5 分钟过期
    strategy='lru'  # LRU 淘汰策略
)

# 查询时使用缓存
def cached_query(query, params):
    key = (query, tuple(sorted(params.items())))

    if key in cache:
        cache_stats = cache.get_stats()
        print(f"缓存命中率: {cache_stats['hit_rate']:.1%}")
        return cache[key]

    result = conn.execute(text(query), params)
    rows = list(result)
    cache[key] = rows
    return rows
```

### 连接池调优

**解决方案**:
```python
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    pool_size=20,  # 连接池大小
    max_overflow=10,  # 最大溢出连接
    pool_timeout=30,  # 获取连接超时
    pool_pre_ping=True,  # 使用前测试连接
    pool_recycle=3600  # 1小时回收连接
)

# 监控连接池
pool = engine.pool
print(f"连接池大小: {pool.size()}")
print(f"活跃连接: {pool.checked_out()}")
```

---

## 测试问题

### 测试环境设置

**Docker Compose 配置**:
```yaml
# docker-compose.test.yml
version: '3'
services:
  couchdb:
    image: couchdb:3
    ports:
      - "5984:5984"
    environment:
      - COUCHDB_USER=admin
      - COUCHDB_PASSWORD=password
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5984/_up"]
      interval: 5s
      timeout: 3s
      retries: 5
```

**运行测试**:
```bash
# 启动测试环境
docker-compose -f docker-compose.test.yml up -d

# 等待 CouchDB 启动
sleep 10

# 运行测试
pytest tests/ -v --cov=sqlalchemy_couchdb

# 清理
docker-compose -f docker-compose.test.yml down
```

---

## 调试技巧

### 开启日志

```python
import logging

# 详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# 只看 SQLAlchemy 日志
logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)
logging.getLogger('sqlalchemy_couchdb').setLevel(logging.DEBUG)
```

### 查看生成的 Mango Query

```python
from sqlalchemy import text
from sqlalchemy_couchdb.compiler import CouchDBCompiler

# 编译查询
stmt = text("SELECT * FROM users WHERE age > :age")
compiler = CouchDBCompiler(dialect, stmt)
mango_query = compiler.process(stmt)

print("生成的 Mango Query:")
import json
print(json.dumps(mango_query, indent=2))
```

### 性能分析

```python
import cProfile
import pstats

# 性能分析
with cProfile.Profile() as pr:
    # 执行查询
    result = conn.execute(query)
    rows = list(result)

# 查看统计
stats = pstats.Stats(pr)
stats.sort_stats('cumulative')
stats.print_stats(10)  # 前 10 个最慢的函数
```

### 检查 CouchDB 状态

```bash
# 服务器信息
curl http://admin:password@localhost:5984/

# 数据库列表
curl http://admin:password@localhost:5984/_all_dbs

# 数据库信息
curl http://admin:password@localhost:5984/mydb

# 查看索引
curl http://admin:password@localhost:5984/mydb/_index

# 查看活动任务
curl http://admin:password@localhost:5984/_active_tasks
```

---

## 常见错误代码

### HTTP 错误码

| 错误码 | 含义 | 常见原因 |
|--------|------|----------|
| 400 | Bad Request | 请求格式错误，JSON 无效 |
| 401 | Unauthorized | 认证失败，用户名/密码错误 |
| 403 | Forbidden | 权限不足 |
| 404 | Not Found | 数据库或文档不存在 |
| 409 | Conflict | 文档冲突，`_rev` 不匹配 |
| 412 | Precondition Failed | 条件不满足 |
| 500 | Internal Server Error | CouchDB 内部错误 |

### SQLAlchemy 异常

| 异常 | 含义 | 解决方案 |
|------|------|----------|
| `OperationalError` | 操作错误 | 检查连接、网络、权限 |
| `ProgrammingError` | 编程错误 | 检查 SQL 语法 |
| `IntegrityError` | 完整性错误 | 检查约束、唯一性 |
| `DataError` | 数据错误 | 检查数据类型、格式 |

---

## 获取帮助

如果以上方法都无法解决问题，请：

1. **查看文档**: https://getaix.github.io/sqlalchemy-couchdb
2. **搜索 Issues**: https://github.com/getaix/sqlalchemy-couchdb/issues
3. **提交 Bug 报告**: 使用 [Bug 报告模板](https://github.com/getaix/sqlalchemy-couchdb/issues/new?template=bug_report.md)
4. **提问**: 使用 [问题模板](https://github.com/getaix/sqlalchemy-couchdb/issues/new?template=question.md)

---

**提示**: 在提问时，请提供：
- 完整的错误堆栈信息
- 最小可复现代码
- 环境信息（Python、CouchDB、包版本）
- 日志输出

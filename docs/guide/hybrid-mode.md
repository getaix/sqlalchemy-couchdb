# 混合数据库模式 (Phase 2)

## 概述

混合数据库模式是 SQLAlchemy CouchDB 方言 Phase 2 的核心特性，结合 CouchDB 的高性能和关系型数据库的强功能。

## 核心思想

### 智能查询路由

- **简单查询** → CouchDB（高性能）
- **复杂查询** → 关系型数据库（功能丰富）
- **写入操作** → 双写（最终一致性）

### 数据同步

- **主数据库**: CouchDB（文档存储）
- **辅助数据库**: 关系型数据库（复杂查询）
- **字段映射**: `_id` → `id`, `_rev` → `rev`, `type` → 隐式

## 配置

### URL 格式

```
couchdb+hybrid://username:password@host:port/database?secondary_db=<RDBMS_URL>
```

### 示例配置

```python
from sqlalchemy import create_engine

# CouchDB + PostgreSQL
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost:5432/mydb'
)

# CouchDB + MySQL
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=mysql+pymysql://user:pass@localhost:3306/mydb'
)

# CouchDB + SQLite
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=sqlite:///mydb.sqlite'
)
```

### URL 参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `secondary_db` | 辅助数据库 URL | `postgresql://...` |
| `routing_strategy` | 路由策略 | `simple`, `hybrid`, `all` |
| `write_mode` | 写操作模式 | `couchdb_only`, `dual_write`, `rdbms_only` |
| `consistency_check` | 一致性检查 | `true`, `false` |
| `check_interval` | 检查间隔（秒） | `60` |

## 查询路由

### 简单查询 → CouchDB

```python
with engine.connect() as conn:
    # 路由到 CouchDB
    result = conn.execute(text("""
        SELECT * FROM users
        WHERE type = 'user' AND age > 25
        ORDER BY age DESC
        LIMIT 10
    """))
```

**特征**:
- 单表查询
- 无 JOIN
- 无 GROUP BY
- 无子查询
- 简单 WHERE 条件

**优点**:
- 高性能（< 50ms）
- 可扩展性好
- 适合大量数据

### 复杂查询 → 关系型数据库

```python
with engine.connect() as conn:
    # 路由到 PostgreSQL
    result = conn.execute(text("""
        SELECT u.name, COUNT(o.id) as order_count
        FROM users u
        JOIN orders o ON u.id = o.user_id
        WHERE u.age > 25
        GROUP BY u.name
        HAVING COUNT(o.id) > 5
        ORDER BY order_count DESC
    """))
```

**特征**:
- 多表 JOIN
- GROUP BY + HAVING
- 子查询
- 复杂聚合
- 窗口函数

**优点**:
- 功能强大
- 成熟优化
- 兼容性好

### 路由决策

```mermaid
graph TD
    A[SQL 查询] --> B{分析查询复杂度}
    B --> C{单表?}<br>简单 WHERE?<br>无 JOIN?
    C -->|是| D[CouchDB]
    C -->|否| E{RDBMS 兼容?}
    E -->|是| F[关系型数据库]
    E -->|否| G[抛出异常]
```

## 字段映射

### CouchDB → 关系型数据库

| CouchDB 字段 | 关系型数据库 | 说明 |
|-------------|-------------|------|
| `_id` | `id` (VARCHAR PRIMARY KEY) | 主键 |
| `_rev` | `rev` (VARCHAR) | 版本号 |
| `type` | (不存储) | 通过表名隐式表达 |
| 其他字段 | 直接映射 | 保持名称和类型 |

### 示例映射

**CouchDB 文档**:
```json
{
  "_id": "user:123",
  "_rev": "1-abc123",
  "type": "users",
  "name": "Alice",
  "age": 30,
  "email": "alice@example.com"
}
```

**PostgreSQL 表**:
```sql
CREATE TABLE users (
    id VARCHAR PRIMARY KEY,
    rev VARCHAR,
    name VARCHAR,
    age INTEGER,
    email VARCHAR
);
```

**字段映射**:
```python
# 输入文档
couchdb_doc = {
    "_id": "user:123",
    "_rev": "1-abc123",
    "type": "users",
    "name": "Alice",
    "age": 30,
    "email": "alice@example.com"
}

# 映射到 RDBMS
rdbms_row = {
    "id": "user:123",
    "rev": "1-abc123",
    "name": "Alice",
    "age": 30,
    "email": "alice@example.com"
}

# 注意：type 字段不存储，通过表名隐式表达
```

## 写入操作

### 双写模式 (推荐)

```python
from sqlalchemy import text

with engine.connect() as conn:
    # 同时写入 CouchDB 和 PostgreSQL
    conn.execute(text("""
        INSERT INTO users (_id, name, age, email, type)
        VALUES (:id, :name, :age, :email, 'user')
    """), {
        'id': 'user:hybrid-1',
        'name': 'Hybrid User',
        'age': 28,
        'email': 'hybrid@example.com'
    })
    conn.commit()

    print("✅ 双写成功")
```

**流程**:
1. 写入 CouchDB
2. 写入 PostgreSQL
3. 验证写入（可选）
4. 提交事务

**优点**:
- 数据完整性
- 查询灵活性
- 最终一致性

**注意**:
- 可能短暂不一致（后台自动修复）
- 写入延迟增加 30-50ms

### 仅 CouchDB 模式

```python
# 使用 QueryRouter 控制路由
from sqlalchemy_couchdb.hybrid import QueryRouter

router = QueryRouter(engine)
router.set_write_mode('couchdb_only')

# 所有写入仅到 CouchDB
with engine.connect() as conn:
    conn.execute(text("INSERT INTO users ..."))
```

### 仅 RDBMS 模式

```python
router.set_write_mode('rdbms_only')

# 所有写入仅到关系型数据库
with engine.connect() as conn:
    conn.execute(text("INSERT INTO users ..."))
```

## 一致性管理

### 最终一致性

混合模式使用最终一致性模型：

1. **写入阶段**: 立即写入 CouchDB（主数据库）
2. **异步同步**: 后台进程写入关系型数据库
3. **一致性检查**: 定期检查数据差异
4. **自动修复**: 自动同步差异数据

### 一致性检查

```python
from sqlalchemy_couchdb.hybrid import ConsistencyChecker

checker = ConsistencyChecker(engine)

# 手动触发一致性检查
result = checker.check_consistency('users')
print(f"检查结果: {result}")

# 修复差异
checker.repair_consistency('users')
```

### 监控

```python
from sqlalchemy_couchdb.hybrid import Monitor

monitor = Monitor(engine)

# 获取统计信息
stats = monitor.get_stats()
print(f"一致性统计: {stats}")

# 监控状态
status = monitor.get_status()
print(f"监控状态: {status}")
```

## 性能优化

### 1. 索引策略

```python
# CouchDB 索引（自动创建）
# ORDER BY 字段自动创建索引

# PostgreSQL 索引（手动创建）
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("""
        CREATE INDEX idx_users_age ON users(age);
        CREATE INDEX idx_orders_user_id ON orders(user_id);
    """))
```

### 2. 分区策略

```python
# PostgreSQL 表分区
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE users_2025 PARTITION OF users
        FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
    """))
```

### 3. 缓存

```python
from sqlalchemy_couchdb.cache import QueryCache

cache = QueryCache(engine, ttl=300)  # 5分钟缓存

# 启用查询缓存
with engine.connect() as conn:
    result = cache.get("users_over_25")
    if result is None:
        result = conn.execute(text("SELECT * FROM users WHERE age > 25"))
        cache.set("users_over_25", result)
```

## 最佳实践

### 1. 数据建模

```python
# ✅ 推荐：扁平化文档
user = {
    "_id": "user:123",
    "type": "users",
    "name": "Alice",
    "age": 30,
    "email": "alice@example.com"
}

# ❌ 避免：过度嵌套
user = {
    "_id": "user:123",
    "type": "users",
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
```

### 2. 查询策略

```python
# ✅ 推荐：简单查询用 CouchDB
users = conn.execute(text("""
    SELECT * FROM users WHERE age > 25
""")).fetchall()

# ✅ 推荐：复杂查询用 PostgreSQL
stats = conn.execute(text("""
    SELECT age_group, COUNT(*) as count
    FROM (
        SELECT CASE
            WHEN age < 20 THEN 'teen'
            WHEN age < 40 THEN 'adult'
            ELSE 'senior'
        END as age_group
        FROM users
    ) age_groups
    GROUP BY age_group
""")).fetchall()
```

### 3. 事务管理

```python
# 注意：双写使用最终一致性
with engine.connect() as conn:
    try:
        conn.execute(text("INSERT INTO users ..."))
        conn.commit()
        print("✅ 写入成功")
    except Exception as e:
        conn.rollback()
        print(f"❌ 写入失败: {e}")
        # 记录失败，等待重试
```

### 4. 错误处理

```python
from sqlalchemy_couchdb.exceptions import ConsistencyError

try:
    result = conn.execute(text("SELECT * FROM users WHERE age > 25"))
except ConsistencyError as e:
    # 数据不一致
    print(f"数据不一致: {e}")
    # 触发一致性检查
    checker.check_consistency('users')
```

## 限制说明

### Phase 2 当前限制

1. **最终一致性**: 写入后可能短暂不一致
2. **索引依赖**: 复杂查询需要额外的 PostgreSQL 索引
3. **双写开销**: 写入延迟增加
4. **模式管理**: 需要在 PostgreSQL 中手动创建表
5. **数据冲突**: 需要解决数据不一致问题

### 不支持的特性

- 跨数据库事务
- 实时一致性保证
- 自动模式迁移
- 智能分片

## 监控和管理

### 1. 连接池监控

```python
def monitor_connections(engine):
    """监控连接池"""
    couchdb_pool = engine.pool  # CouchDB 连接池
    rdbms_pool = engine.get_pool('rdbms')  # RDBMS 连接池

    print(f"CouchDB 池大小: {couchdb_pool.size()}")
    print(f"CouchDB 已借出: {couchdb_pool.checkedout()}")
    print(f"RDBMS 池大小: {rdbms_pool.size()}")
    print(f"RDBMS 已借出: {rdbms_pool.checkedout()}")

monitor_connections(engine)
```

### 2. 性能指标

```python
from sqlalchemy_couchdb.hybrid import PerformanceMonitor

monitor = PerformanceMonitor(engine)

# 获取查询延迟
latency = monitor.get_query_latency()
print(f"查询延迟: {latency}")

# 获取写入吞吐量
throughput = monitor.get_write_throughput()
print(f"写入吞吐量: {throughput}")
```

### 3. 健康检查

```python
def health_check(engine):
    """健康检查"""
    try:
        # 检查 CouchDB
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ CouchDB 正常")
    except Exception as e:
        print(f"❌ CouchDB 异常: {e}")

    try:
        # 检查 RDBMS
        rdbms_engine = engine.get_rdbms_engine()
        with rdbms_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ RDBMS 正常")
    except Exception as e:
        print(f"❌ RDBMS 异常: {e}")

health_check(engine)
```

## 故障恢复

### 数据不一致恢复

```python
from sqlalchemy_couchdb.hybrid import DataRecovery

recovery = DataRecovery(engine)

# 修复特定用户
recovery.repair_user('user:123')

# 修复所有用户
recovery.repair_table('users')

# 完整修复
recovery.full_repair()
```

### 双写故障恢复

```python
from sqlalchemy_couchdb.hybrid import WriteFailureHandler

handler = WriteFailureHandler(engine)

# 处理写入失败
def handle_write_failure(operation, data, error):
    """处理写入失败"""
    # 记录失败
    logger.error(f"写入失败: {operation}, {data}, {error}")

    # 重新尝试
    handler.retry_write(operation, data)

    # 或记录到队列，等待后续处理
    handler.queue_write(operation, data)

handler.on_failure(handle_write_failure)
```

## 迁移指南

### 从 Phase 1 迁移到 Phase 2

1. **安装可选依赖**:
```bash
pip install sqlalchemy-couchdb[all]
```

2. **更新连接 URL**:
```python
# Phase 1
engine = create_engine('couchdb://localhost:5984/mydb')

# Phase 2
engine = create_engine(
    'couchdb+hybrid://localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost:5432/mydb'
)
```

3. **在 PostgreSQL 中创建表**:
```python
from sqlalchemy import text

with engine.connect() as conn:
    conn.execute(text("""
        CREATE TABLE users (
            id VARCHAR PRIMARY KEY,
            rev VARCHAR,
            name VARCHAR,
            age INTEGER,
            email VARCHAR
        );
    """))
```

4. **启用监控**:
```python
from sqlalchemy_couchdb.hybrid import Monitor

monitor = Monitor(engine)
monitor.start()
```

## 下一步

- [性能优化](../dev/performance.md)
- [API 参考](../api/dialect.md)
- [常见问题](../faq.md)

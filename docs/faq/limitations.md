# 限制和注意事项

本文档说明 SQLAlchemy CouchDB Dialect 的当前限制和注意事项。

## SQL 功能限制

### Phase 1 不支持的功能

Phase 1（纯 CouchDB 模式）目前不支持以下 SQL 功能：

#### 1. JOIN 操作

**限制**: CouchDB 不支持多表联接。

**替代方案**:

```python
# ❌ 不支持
SELECT u.name, o.total
FROM users u
JOIN orders o ON u.id = o.user_id

# ✅ 方案 1: 客户端联接
users = conn.execute("SELECT * FROM users").fetchall()
orders = conn.execute("SELECT * FROM orders").fetchall()

# 在 Python 中进行联接
for user in users:
    user_orders = [o for o in orders if o.user_id == user.id]
    # 处理结果

# ✅ 方案 2: 文档嵌套（推荐）
# 将订单嵌入用户文档
user_doc = {
    "_id": "user:1",
    "name": "Alice",
    "orders": [
        {"id": "order:1", "total": 100},
        {"id": "order:2", "total": 200}
    ]
}

# ✅ 方案 3: Phase 2 混合架构
# 复杂查询自动路由到 RDBMS
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost/pgdb'
)
```

#### 2. 子查询

**限制**: 不支持嵌套 SELECT。

**替代方案**:

```python
# ❌ 不支持
SELECT * FROM users WHERE age > (
    SELECT AVG(age) FROM users
)

# ✅ 分步查询
avg_age_result = conn.execute("SELECT age FROM users").fetchall()
avg_age = sum(r.age for r in avg_age_result) / len(avg_age_result)

users = conn.execute(
    "SELECT * FROM users WHERE age > :avg",
    {"avg": avg_age}
).fetchall()

# ✅ 使用 CouchDB 视图（高级）
from sqlalchemy_couchdb.management import ViewManager

view_manager = ViewManager(client)
view_manager.create_view(
    'mydb',
    'stats',
    'average_age',
    map_function="""function(doc) {
        if (doc.type === 'users') {
            emit(null, doc.age);
        }
    }""",
    reduce_function="_stats"
)
```

#### 3. GROUP BY（部分支持）

**限制**: 基础 GROUP BY 需要客户端处理或 CouchDB 视图。

**支持情况**:
- ✅ 简单聚合（COUNT, SUM, AVG, MIN, MAX）- 使用 `advanced.py`
- ✅ 单字段 GROUP BY - 使用 `QueryProcessor`
- ❌ 复杂 GROUP BY（多字段、HAVING）- 需要 Phase 2

**示例**:

```python
from sqlalchemy_couchdb.advanced import QueryProcessor

# 获取原始数据
result = conn.execute("SELECT * FROM orders").fetchall()

# 客户端分组
processor = QueryProcessor(result)
grouped = processor.group_by(
    ['user_id'],
    {'total': 'sum', 'order_id': 'count'}
)

for group in grouped:
    print(f"用户 {group['user_id']}: 总金额 {group['total_sum']}, 订单数 {group['order_id_count']}")
```

#### 4. UNION/INTERSECT/EXCEPT

**限制**: 不支持集合操作。

**替代方案**:

```python
# ❌ 不支持
SELECT id FROM users
UNION
SELECT id FROM customers

# ✅ 客户端合并
users = set(r.id for r in conn.execute("SELECT id FROM users"))
customers = set(r.id for r in conn.execute("SELECT id FROM customers"))

# UNION
all_ids = users.union(customers)

# INTERSECT
common_ids = users.intersection(customers)

# EXCEPT
only_users = users.difference(customers)
```

#### 5. 窗口函数

**限制**: 不支持 `ROW_NUMBER()`, `RANK()`, `LEAD()`, `LAG()` 等。

**替代方案**: 客户端处理或使用 Phase 2。

#### 6. 事务（Transaction）

**限制**: CouchDB 不支持多文档 ACID 事务。

**特点**:
- ✅ 单文档操作是原子的
- ✅ 批量操作（`bulk_docs`）保证全部成功或全部���败
- ❌ 跨文档事务需要应用层处理
- ❌ `ROLLBACK` 是 no-op（无操作）

**最佳实践**:

```python
# ✅ 使用批量操作保证原子性
from sqlalchemy import insert

stmt = insert(users_table)
conn.execute(stmt, [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": 25}
])  # 全部成功或全部失败

# ✅ 单文档操作是原子的
conn.execute(
    "UPDATE users SET balance = balance - 100 WHERE _id = :id",
    {"id": "user:1"}
)

# ❌ 跨文档事务不保证
# 需要应用层实现补偿逻辑
try:
    conn.execute("UPDATE account_a SET balance = balance - 100")
    conn.execute("UPDATE account_b SET balance = balance + 100")
except Exception as e:
    # 需要手动回滚 account_a
    pass
```

---

## CouchDB 特定限制

### 1. _rev 版本控制

**要求**: UPDATE/DELETE 必须提供正确的 `_rev`。

```python
# ✅ 正确的更新流程
# 1. 先查询获取 _rev
result = conn.execute(
    "SELECT _id, _rev, name FROM users WHERE _id = :id",
    {"id": "user:1"}
)
row = result.fetchone()

# 2. 使用 _rev 更新
conn.execute(
    "UPDATE users SET name = :name WHERE _id = :id AND _rev = :rev",
    {"id": row._id, "rev": row._rev, "name": "New Name"}
)

# ❌ 不提供 _rev 会失败
conn.execute(
    "UPDATE users SET name = :name WHERE _id = :id",
    {"id": "user:1", "name": "New Name"}
)  # 错误：需要 _rev
```

**冲突处理**:

```python
from sqlalchemy_couchdb.exceptions import OperationalError

try:
    conn.execute(update_stmt)
except OperationalError as e:
    if "409" in str(e):  # Conflict
        # 重新获取最新的 _rev 并重试
        pass
```

### 2. 索引限制

**Mango Query 索引要求**:
- ORDER BY 字段必须有索引
- 复杂查询可能需要复合索引
- 索引创建是异步的

**自动索引**:

```python
# ✅ ORDER BY 会自动创建索引
conn.execute("SELECT * FROM users ORDER BY age")  # 自动创建 age 索引

# ✅ 手动创建复合索引
from sqlalchemy_couchdb.management import IndexManager

index_mgr = IndexManager(client)
index_mgr.create_index(
    'mydb',
    fields=['age', 'name'],
    index_name='idx_age_name'
)
```

### 3. 查询性能

**限制**:
- 全表扫描性能较差
- 没有索引的查询会很慢
- LIKE 查询性能低于精确匹配

**优化建议**:

```python
# ❌ 慢：全表扫描
SELECT * FROM users WHERE description LIKE '%keyword%'

# ✅ 快：使用索引
SELECT * FROM users WHERE status = 'active' AND age > 25

# ✅ 使用字段选择
SELECT _id, name FROM users  # 只返回需要的字段

# ✅ 使用 LIMIT
SELECT * FROM users ORDER BY created_at DESC LIMIT 100
```

---

## 异步操作限制

### 1. 迭代限制

**限制**: 异步结果不支持 `async for`。

```python
# ❌ 不支持
async for row in result:  # 错误！
    print(row)

# ✅ 使用同步迭代（greenlet 机制）
result = await conn.execute(stmt)
for row in result:  # 正确
    print(row)

# ✅ 或使用 fetch 方法
rows = result.fetchall()
for row in rows:
    print(row)
```

**原因**: SQLAlchemy 2.0 的 greenlet 机制限制。

### 2. 并发限制

**建议**:

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine

async def main():
    engine = create_async_engine(
        'couchdb+async://admin:password@localhost:5984/mydb',
        pool_size=20,  # 控制连接池大小
        max_overflow=10
    )

    # ✅ 使用 Semaphore 限制并发
    sem = asyncio.Semaphore(10)  # 最多 10 个并发

    async def query_with_limit(id):
        async with sem:
            async with engine.connect() as conn:
                return await conn.execute(
                    text("SELECT * FROM users WHERE _id = :id"),
                    {"id": id}
                )

    # 并发查询
    tasks = [query_with_limit(f"user:{i}") for i in range(100)]
    results = await asyncio.gather(*tasks)

asyncio.run(main())
```

---

## 数据类型限制

### 1. CouchDB 原生类型

CouchDB 存储的是 JSON 文档，支持的类型有限：

| 支持 | 不支持 |
|------|--------|
| String | Binary/BLOB |
| Number (int, float) | Decimal（精度） |
| Boolean | Enum |
| Date/DateTime（字符串） | Time |
| Object/Array | 自定义类型 |
| null | - |

**解决方案**:

```python
# ✅ Decimal 转换为字符串存储
from decimal import Decimal
import json

class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)

# ✅ Binary 数据使用附件
from sqlalchemy_couchdb.attachments import AttachmentManager

att_mgr = AttachmentManager(client)
att_mgr.upload_attachment(
    doc_id="user:1",
    filename="avatar.jpg",
    content=image_bytes,
    content_type="image/jpeg"
)
```

### 2. 字段名限制

**保留字段**:
- `_id`: 文档 ID（必需）
- `_rev`: 版本号（自动）
- `type`: 表名映射（推荐）
- `_attachments`: 附件（特殊）
- `_conflicts`: 冲突（特殊）
- `_deleted`: 删除标记（特殊）

**命名建议**:
- 避免以 `_` 开头（保留给 CouchDB）
- 使用 `snake_case`
- 避免特殊字符

---

## Phase 2 规划

以下限制将在 Phase 2（混合架构）中解决：

### 即将支持

- ✅ JOIN 操作（通过 RDBMS）
- ✅ 子查询（通过 RDBMS）
- ✅ 复杂 GROUP BY（通过 RDBMS）
- ✅ 窗口函数（通过 RDBMS）
- ✅ UNION/INTERSECT（通过 RDBMS）
- ✅ 完整的事务支持（通过 RDBMS）

### 混合架构工作原理

```python
# 自动路由
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost/pgdb'
)

# 简单查询 → CouchDB
result = conn.execute("SELECT * FROM users WHERE age > 25")

# 复杂查询 → PostgreSQL
result = conn.execute("""
    SELECT u.name, COUNT(o.id) as order_count
    FROM users u
    JOIN orders o ON u.id = o.user_id
    GROUP BY u.name
    HAVING COUNT(o.id) > 10
""")  # 自动路由到 PostgreSQL
```

---

## 最佳实践

### 1. 选择合适的场景

**适合使用 CouchDB**:
- ✅ 文档存储（用户资料、配置）
- ✅ 键值查询（按 ID 查找）
- ✅ 简单范围查询（年龄、日期）
- ✅ 离线优先应用（复制）
- ✅ 高可用性需求

**不适合使用 CouchDB**:
- ❌ 复杂关系查询
- ❌ 多表联接
- ❌ 复杂聚合统计
- ❌ 强一致性事务
- ❌ 全文搜索（使用 Elasticsearch）

### 2. 文档设计

**推荐**:

```python
# ✅ 嵌入相关数据
user_doc = {
    "_id": "user:1",
    "type": "users",
    "name": "Alice",
    "profile": {
        "bio": "...",
        "avatar_url": "..."
    },
    "recent_orders": [
        {"id": "order:1", "total": 100},
        {"id": "order:2", "total": 200}
    ]
}

# ✅ 使用有意义的 ID
# 格式: {type}:{unique_id}
"user:alice@example.com"
"order:2024-001"
"product:SKU-12345"
```

**避免**:

```python
# ❌ 过度规范化
user_doc = {"_id": "user:1", "name": "Alice"}
profile_doc = {"_id": "profile:1", "user_id": "user:1", ...}
orders_doc = {"_id": "order:1", "user_id": "user:1", ...}
# 这需要多次查询！

# ✅ 合理嵌套
user_doc = {
    "_id": "user:1",
    "name": "Alice",
    "profile": {...},
    "recent_orders": [...]  # 只保留最近的
}
```

### 3. 监控和调试

```python
import logging

# 开启日志
logging.basicConfig(level=logging.DEBUG)
logging.getLogger('sqlalchemy_couchdb').setLevel(logging.DEBUG)

# 查看生成的 Mango Query
from sqlalchemy_couchdb.compiler import CouchDBCompiler

compiler = CouchDBCompiler(...)
mango_query = compiler.process(stmt)
print(json.dumps(mango_query, indent=2))

# 查看 CouchDB 查询统计
curl http://admin:password@localhost:5984/mydb/_index
```

---

## 获取帮助

如果遇到限制相关的问题：

1. **查看文档**: [故障排查指南](troubleshooting.md)
2. **提问**: 使用 [问题模板](https://github.com/getaix/sqlalchemy-couchdb/issues/new?template=question.md)
3. **功能请求**: 使用 [功能请求模板](https://github.com/getaix/sqlalchemy-couchdb/issues/new?template=feature_request.md)

---

**提示**: 许多限制将在 Phase 2 混合架构中解决。敬请期待！

# 常见问题解答 (FAQ)

## 安装问题

### Q: 安装时提示 "No module named 'sqlalchemy_couchdb'"

**A**: 请确保正确安装包：

```bash
# 使用 pip
pip install sqlalchemy-couchdb

# 或从源码安装
git clone https://github.com/getaix/sqlalchemy-couchdb.git
cd sqlalchemy-couchdb
pip install -e .
```

### Q: Python 版本不兼容

**A**: SQLAlchemy CouchDB 需要 Python 3.11+：

```bash
# 检查 Python 版本
python --version

# 如果版本过低，请升级 Python
# 或使用 pyenv
pyenv install 3.11.0
pyenv local 3.11.0
```

### Q: httpx 版本冲突

**A**: 确保安装兼容版本：

```bash
pip install --upgrade httpx>=0.27.0
```

## 连接问题

### Q: 无法连接到 CouchDB

**A**: 检查以下几点：

1. **CouchDB 服务是否运行**:
```bash
curl http://localhost:5984/
```

2. **防火墙设置**:
```bash
# Ubuntu/Debian
sudo ufw allow 5984

# CentOS/RHEL
sudo firewall-cmd --add-port=5984/tcp --permanent
sudo firewall-cmd --reload
```

3. **连接 URL 格式**:
```python
# 正确格式
couchdb://username:password@host:port/database

# 示例
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')
```

### Q: 认证失败

**A**: 检查用户名密码：

```bash
# 测试认证
curl -X GET http://admin:password@localhost:5984/mydb
```

### Q: 数据库不存在

**A**: 先创建数据库：

```bash
curl -X PUT http://admin:password@localhost:5984/mydb
```

## 使用问题

### Q: 异步模式下结果为空

**A**: 异步模式使用同步迭代（结果已缓存）：

```python
# ✅ 正确
result = await conn.execute(text("SELECT * FROM users"))
for row in result:  # 同步迭代
    print(row.name)

# ❌ 错误
async for row in result:  # 不要使用 async for
    print(row.name)
```

### Q: 更新失败 - 文档冲突

**A**: CouchDB 乐观锁机制，需要最新 `_rev`：

```python
# 错误处理
try:
    conn.execute(text("UPDATE users SET age=31 WHERE _id='user:123'"))
    conn.commit()
except Exception:
    # 文档可能被修改，重新获取
    result = conn.execute(text("SELECT * FROM users WHERE _id='user:123'"))
    row = result.fetchone()
    print(f"最新版本: {row._rev}")
```

### Q: ORDER BY 性能差

**A**: ORDER BY 需要索引，自动创建或手动创建：

```python
# 自动创建索引
result = conn.execute(text("""
    SELECT * FROM users
    ORDER BY age DESC  -- 自动创建 age 索引
"""))

# 或手动创建
from sqlalchemy_couchdb.client import SyncCouchDBClient
client = SyncCouchDBClient(...)
client.ensure_index("age", design_doc="age-index")
```

### Q: LIKE 查询性能差

**A**: LIKE 查询使用正则表达式，性能较低：

```python
# 性能较好：前缀匹配
SELECT * FROM users WHERE name LIKE 'Alice%'

# 性能较差：包含匹配
SELECT * FROM users WHERE name LIKE '%lice%'

# 最佳方案：使用精确匹配或索引字段
SELECT * FROM users WHERE name = 'Alice'
```

## 类型问题

### Q: 日期时间格式错误

**A**: 使用正确格式：

```python
from datetime import datetime

# ✅ 正确：使用 datetime 对象
conn.execute(text("..."), {
    'created_at': datetime(2025, 1, 2, 15, 30, 0)
})

# ✅ 正确：ISO 8601 字符串
conn.execute(text("..."), {
    'created_at': '2025-01-02T15:30:00'
})

# ❌ 错误：其他格式
conn.execute(text("..."), {
    'created_at': '2025/01/02 15:30:00'
})
```

### Q: 浮点数精度损失

**A**: 使用 Numeric 类型：

```python
from sqlalchemy_couchdb.types import CouchDBNumeric
from decimal import Decimal

# 货币等高精度数据
Column('amount', CouchDBNumeric(precision=10, scale=2, as_string=True))

# 使用
Decimal('123.456789')
```

### Q: JSON 字段查询问题

**A**: CouchDB 对嵌套 JSON 查询有限制：

```python
# ❌ 不推荐：嵌套查询
SELECT * FROM users WHERE metadata->'preferences'->>'theme' = 'dark'

# ✅ 推荐：使用简单字段
SELECT * FROM users WHERE theme = 'dark'

# 或：存储时扁平化
user = {
    "theme": "dark",
    "notifications": True,
    "metadata": {...}  # 其他数据
}
```

## SQL 特性问题

### Q: 不支持 JOIN

**A**: 文档数据库固有限制：

```python
# ❌ 不支持
SELECT u.name, o.amount
FROM users u
JOIN orders o ON u._id = o.user_id

# ✅ 替代方案：嵌入式文档
order = {
    "_id": "order:1",
    "user": {
        "id": "user:1",
        "name": "Alice"
    },
    "amount": 99.99
}

# 或：多次查询
users = conn.execute(text("SELECT * FROM users")).fetchall()
for user in users:
    orders = conn.execute(
        text("SELECT * FROM orders WHERE user_id = :id"),
        {"id": user._id}
    ).fetchall()
```

### Q: 不支持 GROUP BY

**A**: 需要使用 MapReduce 视图：

```python
# ❌ 不支持
SELECT name, COUNT(*) FROM users GROUP BY name

# ✅ 替代方案：使用视图
# 定义 Map 函数：
# function(doc) {
#     if (doc.type == 'user') {
#         emit(doc.name, 1);
#     }
# }
# Reduce 函数：
# function(keys, values) {
#     return sum(values);
# }
```

### Q: 不支持子查询

**A**: 应用层处理：

```python
# ❌ 不支持
SELECT * FROM users
WHERE age > (SELECT AVG(age) FROM users)

# ✅ 替代方案：两次查询
avg_age = conn.execute(text("SELECT AVG(age) as avg FROM users")).fetchone()
result = conn.execute(
    text("SELECT * FROM users WHERE age > :age"),
    {"age": avg_age.avg}
)
```

## 性能问题

### Q: 查询速度慢

**A**: 优化建议：

1. **使用索引**:
```python
# 为查询字段创建索引
client.ensure_index("age")
client.ensure_index(["age", "name"])  # 复合索引
```

2. **限制返回字段**:
```python
# ✅ 只查询需要的字段
SELECT _id, name FROM users

# ❌ 查询所有字段
SELECT * FROM users
```

3. **使用 LIMIT**:
```python
SELECT * FROM users LIMIT 100
```

### Q: 批量插入慢

**A**: 使用批量 API：

```python
# ✅ 高效：批量插入
data = [{...}, {...}, ...]
conn.execute(text("INSERT INTO ..."), data)

# ❌ 低效：循环插入
for item in data:
    conn.execute(text("INSERT INTO ..."), item)
```

### Q: 内存占用高

**A**: 流式处理：

```python
# ✅ 流式处理大结果集
result = conn.execute(text("SELECT * FROM large_table"))
while True:
    rows = result.fetchmany(1000)  # 分批获取
    if not rows:
        break
    process(rows)

# ❌ 一次性加载所有
all_rows = result.fetchall()  # 占用大量内存
```

## Phase 2 混合模式问题

### Q: 混合模式配置错误

**A**: 检查 URL 格式：

```python
# 正确
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost:5432/mydb'
)

# 检查环境变量
import os
print(os.getenv('SECONDARY_DB_URL'))
```

### Q: 数据不一致

**A**: Phase 2 使用最终一致性：

```python
# 等待一致性
import time
time.sleep(1)  # 等待双写完成

# 或手动检查一致性
result = conn.execute(text("SELECT COUNT(*) FROM users"))
# CouchDB 和 PostgreSQL 可能短暂不一致
```

### Q: 查询路由错误

**A**: 检查路由策略：

```python
# 简单查询 → CouchDB
result = conn.execute(text("SELECT * FROM users WHERE age > 25"))

# 复杂查询 → PostgreSQL
result = conn.execute(text("""
    SELECT u.name, COUNT(o.id) as order_count
    FROM users u JOIN orders o ON u._id = o.user_id
    GROUP BY u.name
"""))
```

## 错误处理

### Q: 捕获异常类型

```python
from sqlalchemy_couchdb.exceptions import CouchDBError

try:
    conn.execute(text("..."))
except CouchDBError as e:
    print(f"CouchDB 错误: {e}")
except Exception as e:
    print(f"通用错误: {e}")
```

### Q: 重试机制

```python
import time
from functools import wraps

def retry(max_attempts=3, delay=0.1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay)
        return wrapper
    return decorator

@retry(max_attempts=3)
def update_user(conn, user_id, data):
    return conn.execute(text("UPDATE ..."), data)
```

## 调试技巧

### Q: 查看生成的 Mango Query

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# 执行查询时会在控制台看到编译过程
result = conn.execute(text("SELECT * FROM users WHERE age > 25"))
```

### Q: 手动测试 Mango Query

```python
import httpx

# 直接使用 HTTP 客户端测试
with httpx.Client() as client:
    response = client.post(
        'http://localhost:5984/mydb/_find',
        json={
            "selector": {"type": {"$eq": "user"}},
            "limit": 10
        }
    )
    print(response.json())
```

### Q: 连接池状态

```python
def check_pool(engine):
    pool = engine.pool
    print(f"池大小: {pool.size()}")
    print("已借出:", pool.checkedout())
    print("已返回:", pool.returned())

check_pool(engine)
```

## 资源

- [完整文档](https://github.com/getaix/sqlalchemy-couchdb)
- [GitHub Issues](https://github.com/getaix/sqlalchemy-couchdb/issues)
- [CouchDB 文档](https://docs.couchdb.org/)
- [SQLAlchemy 文档](https://docs.sqlalchemy.org/)

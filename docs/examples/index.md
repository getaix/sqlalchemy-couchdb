# 示例集合

## 概述

本目录包含 SQLAlchemy CouchDB 方言的完整示例，涵盖从基础用法到高级特性的各种场景。

## 示例列表

### 基础示例

#### 1. 基础同步操作

**文件**: `examples/basic_sync.py`

演示基本的同步 CRUD 操作：

- 连接 CouchDB
- 插入文档
- 查询文档
- 更新文档
- 删除文档

```python
from sqlalchemy import create_engine, text

# 创建引擎
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

# 使用连接
with engine.connect() as conn:
    # 插入
    conn.execute(text("""
        INSERT INTO users (_id, name, age, type)
        VALUES (:id, :name, :age, 'user')
    """), {
        'id': 'user:1',
        'name': 'Alice',
        'age': 30
    })

    # 查询
    result = conn.execute(text("SELECT * FROM users WHERE type = 'user'"))
    for row in result:
        print(f"{row.name}: {row.age}")

    conn.commit()
```

**运行方式**:
```bash
python examples/basic_sync.py
```

#### 2. 基础异步操作

**文件**: `examples/basic_async.py`

演示异步操作：

- 创建异步引擎
- 异步 CRUD 操作
- 并发查询
- 错误处理

```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    # 创建异步引擎
    engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

    async with engine.connect() as conn:
        # 插入
        await conn.execute(text("""
            INSERT INTO users (_id, name, age, type)
            VALUES (:id, :name, :age, 'user')
        """), {
            'id': 'user:async:1',
            'name': 'Bob Async',
            'age': 25
        })

        # 查询
        result = await conn.execute(text("""
            SELECT * FROM users WHERE type = 'user'
        """))

        # 注意：使用同步迭代（结果已缓存）
        for row in result:
            print(f"{row.name}: {row.age}")

        await conn.commit()

    await engine.dispose()

asyncio.run(main())
```

**运行方式**:
```bash
python examples/basic_async.py
```

#### 3. 完整示例

**文件**: `examples/async_example.py`

完整的异步应用示例：

- 复杂查询
- 事务管理
- 错误处理
- 性能优化

### 高级示例

#### 1. 高级特性演示

**文件**: `examples/advanced_features.py`

演示高级特性：

- 复杂查询条件
- 批量操作
- 索引优化
- 性能监控

```python
from sqlalchemy import text
from datetime import datetime

# 复杂查询
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
      AND age > 25
      AND age < 35
      AND name LIKE 'A%'
    ORDER BY age DESC
    LIMIT 10
"""))

# 批量插入
users_data = [
    {'id': f'user:{i}', 'name': f'User{i}', 'age': 20 + i, 'type': 'user'}
    for i in range(100)
]

conn.execute(text("""
    INSERT INTO users (_id, name, age, type)
    VALUES (:id, :name, :age, 'user')
"""), users_data)

conn.commit()
```

#### 2. 性能基准测试

**文件**: `examples/performance_benchmark.py`

性能测试和基准：

- CRUD 操作性能测试
- 批量操作性能
- 并发查询性能
- 内存使用测试

```python
import time
from contextlib import contextmanager

@contextmanager
def timer():
    start = time.time()
    yield
    elapsed = time.time() - start
    print(f"耗时: {elapsed:.3f}s")

# 测试批量插入
with timer():
    conn.execute(text("""
        INSERT INTO users (_id, name, age, type)
        VALUES (:id, :name, :age, 'user')
    """), users_data)
    conn.commit()

print(f"插入 {len(users_data)} 条记录，吞吐量: {len(users_data)/elapsed:.1f} docs/s")
```

### ORM 示例

#### 1. 声明式模型

**文件**: `examples/orm_example.py`

**注意**: ORM 支持将在 Phase 3 中实现

```python
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer
from sqlalchemy_couchdb.types import CouchDBString, CouchDBInteger

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'

    _id = Column(String, primary_key=True)
    name = Column(CouchDBString(255))
    age = Column(CouchDBInteger())
    type = Column(CouchDBString(50))

# 使用 ORM
user = User(_id='user:orm:1', name='ORM User', age=30, type='user')
session.add(user)
session.commit()
```

### Phase 2 混合模式示例

#### 1. 智能查询路由

**文件**: `examples/hybrid_routing.py`

**注意**: 混合模式将在 Phase 2 中实现

```python
from sqlalchemy import create_engine

# 创建混合引擎
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost:5432/mydb'
)

# 简单查询 → CouchDB
result = conn.execute(text("""
    SELECT * FROM users WHERE age > 25
"""))

# 复杂查询 → PostgreSQL
result = conn.execute(text("""
    SELECT u.name, COUNT(o.id) as order_count
    FROM users u
    JOIN orders o ON u.id = o.user_id
    GROUP BY u.name
"""))
```

#### 2. 双写机制

**文件**: `examples/dual_write.py`

演示双写机制：

- 同时写入 CouchDB 和 PostgreSQL
- 一致性检查
- 错误处理

```python
from sqlalchemy import text

# 双写
with engine.connect() as conn:
    try:
        conn.execute(text("""
            INSERT INTO users (_id, name, age, type)
            VALUES (:id, :name, :age, 'user')
        """), {
            'id': 'user:dual:1',
            'name': 'Dual Write User',
            'age': 28
        })

        conn.commit()
        print("✅ 双写成功")

    except Exception as e:
        conn.rollback()
        print(f"❌ 双写失败: {e}")
```

## 示例数据

### 示例数据集

运行示例前，可以加载示例数据：

```bash
python examples/load_sample_data.py
```

这会创建包含以下数据的测试数据库：

- 100 个用户
- 500 个订单
- 1000 个产品

### 清理示例数据

```bash
python examples/cleanup_sample_data.py
```

## 最佳实践示例

### 1. 连接管理

**最佳实践**: 使用上下文管理器

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

### 2. 错误处理

**最佳实践**: 捕获特定异常

```python
from sqlalchemy_couchdb.exceptions import (
    NotFoundError,
    DocumentConflictError,
    CouchDBError
)

try:
    conn.execute(text("UPDATE ..."))
    conn.commit()
except NotFoundError:
    print("文档不存在")
except DocumentConflictError:
    print("文档版本冲突")
except CouchDBError as e:
    print(f"CouchDB 错误: {e}")
```

### 3. 性能优化

**最佳实践**: 批量操作

```python
# ✅ 批量插入
data = [{...}, {...}, ...]
conn.execute(text("INSERT INTO ..."), data)

# ❌ 循环插入
for item in data:
    conn.execute(text("INSERT INTO ..."), item)
```

## 运行示例

### 环境准备

```bash
# 1. 启动 CouchDB
docker run -d -p 5984:5984 \
  -e COUCHDB_USER=admin \
  -e COUCHDB_PASSWORD=password \
  couchdb:3

# 2. 创建数据库
curl -X PUT http://admin:password@localhost:5984/examples

# 3. 安装依赖
pip install -e ".[dev]"

# 4. 运行示例
python examples/basic_sync.py
```

### 完整示例列表

```bash
# 基础示例
python examples/basic_sync.py          # 同步操作
python examples/basic_async.py         # 异步操作
python examples/async_example.py       # 完整异步示例

# 高级示例
python examples/advanced_features.py   # 高级特性
python examples/performance_benchmark.py  # 性能测试

# 数据管理
python examples/load_sample_data.py    # 加载示例数据
python examples/cleanup_sample_data.py # 清理示例数据

# Phase 2 示例（开发中）
python examples/hybrid_routing.py      # 智能路由
python examples/dual_write.py          # 双写机制
```

## 自定义示例

### 创建自己的示例

1. 在 `examples/` 目录下创建新文件
2. 遵循命名规范：`feature_example.py`
3. 添加清晰的注释和文档
4. 包含错误处理
5. 保持代码简洁

### 示例模板

```python
"""
示例: 功能描述

此示例演示...
"""

from sqlalchemy import create_engine, text

def main():
    """主函数"""
    # 连接
    engine = create_engine('couchdb://localhost:5984/examples')

    with engine.connect() as conn:
        try:
            # 操作
            conn.execute(text("..."))
            conn.commit()
            print("✅ 成功")

        except Exception as e:
            conn.rollback()
            print(f"❌ 错误: {e}")

if __name__ == '__main__':
    main()
```

## 贡献示例

欢迎提交示例！

### 提交流程

1. Fork 项目
2. 创建示例文件
3. 运行测试确保示例工作
4. 提交 Pull Request

### 示例要求

- 代码清晰可读
- 包含详细注释
- 有错误处理
- 遵循项目代码规范
- 在文档中引用

## 下一步

- [快速开始](../getting-started/basic-usage.md)
- [同步操作指南](../guide/sync-operations.md)
- [异步操作指南](../guide/async-operations.md)
- [API 参考](../api/compiler.md)

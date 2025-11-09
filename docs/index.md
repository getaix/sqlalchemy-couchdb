# SQLAlchemy CouchDB 方言

<p align="center">
  <img src="https://www.sqlalchemy.org/img/sqla_logo.png" alt="SQLAlchemy Logo" width="400">
</p>

<p align="center">
  <strong>功能强大的 SQLAlchemy 2.0+ CouchDB 驱动</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11+-blue.svg" alt="Python Version"></a>
  <a href="https://www.sqlalchemy.org/"><img src="https://img.shields.io/badge/sqlalchemy-2.0+-green.svg" alt="SQLAlchemy Version"></a>
  <a href="about/license/"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <img src="https://img.shields.io/badge/tests-487%20passed-brightgreen.svg" alt="Tests">
</p>

---

## ✨ 项目特性

### 🎯 Phase 1: 纯 CouchDB 模式 `✅ 已完成`

!!! success "核心功能"
    - ✅ **完整的 SQLAlchemy 支持**: 实现 SQLAlchemy 2.0+ Dialect 接口
    - ✅ **同步 + 异步**: 100%支持同步和异步操作（greenlet机制）
    - ✅ **SQL → Mango Query**: 自动将 SQL 转换为 CouchDB Mango Query
    - ✅ **类型系统**: 完整的 Python ↔ JSON 类型映射
    - ✅ **基于 httpx**: 高性能 HTTP 客户端，支持连接池
    - ✅ **完整测试**: 487项测试通过，80% 代码覆盖率
    - ✅ **自动索引管理**: ORDER BY 操作自动创建所需索引
    - ✅ **参数绑定**: 正确处理 SQLAlchemy 2.0 的 BindParameter 机制
    - ✅ **异步并发**: 支持 asyncio.gather() 并发查询

### 🚧 Phase 2: 混合数据库架构 `⏳ 已实现`

!!! info "混合架构功能"
    - ⏳ **智能查询路由**: 简单查询 → CouchDB，复杂查询 → 关系型数据库
    - ⏳ **双写同步**: 自动同步数据到 CouchDB 和关系型数据库
    - ⏳ **通用数据库支持**: 支持 PostgreSQL, MySQL, SQLite 等
    - ⏳ **字段映射**: 自动处理 CouchDB 特殊字段（`_id`, `_rev`, `type`）
    - ⏳ **最终一致性**: 后台监控和自动修复数据差异

---

## 🚀 快速开始

### 安装

```bash
pip install sqlalchemy-couchdb
```

### 基本使用

=== "同步操作"

    ```python
    from sqlalchemy import create_engine, text

    # 创建引擎
    engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

    # 使用连接
    with engine.connect() as conn:
        # 插入数据
        conn.execute(text("""
            INSERT INTO users (name, age, email)
            VALUES (:name, :age, :email)
        """), {"name": "Alice", "age": 30, "email": "alice@example.com"})

        # 查询数据
        result = conn.execute(text("SELECT * FROM users WHERE age > :age"), {"age": 25})
        for row in result:
            print(f"{row.name}: {row.age}")

        conn.commit()
    ```

=== "异步操作"

    ```python
    import asyncio
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    async def main():
        # 创建异步引擎
        engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')

        async with engine.connect() as conn:
            # 插入数据
            await conn.execute(text("""
                INSERT INTO users (name, age, email)
                VALUES (:name, :age, :email)
            """), {"name": "Bob", "age": 25, "email": "bob@example.com"})

            # 查询数据
            result = await conn.execute(text("SELECT * FROM users WHERE age > :age"), {"age": 20})

            # 注意：使用同步迭代（结果已在 execute 时缓存）
            for row in result:
                print(f"{row.name}: {row.age}")

            await conn.commit()

        await engine.dispose()

    asyncio.run(main())
    ```

---

## 📊 支持的 SQL 特性

### Phase 1 (纯 CouchDB)

| SQL 特性 | 支持情况 | 说明 |
|---------|---------|------|
| `SELECT` | ✅ 部分支持 | 简单查询，无 JOIN |
| `INSERT` | ✅ 完全支持 | 单条和批量插入 |
| `UPDATE` | ✅ 完全支持 | 需要 `_rev` |
| `DELETE` | ✅ 完全支持 | 需要 `_rev` |
| `WHERE` | ✅ 完全支持 | 支持 `=`, `>`, `<`, `IN`, `LIKE`, `AND`, `OR` |
| `LIMIT` / `OFFSET` | ✅ 完全支持 | 分页查询 |
| `ORDER BY` | ✅ 完全支持 | 自动创建索引 |
| `JOIN` | ❌ 不支持 | CouchDB 限制 |
| `GROUP BY` | ⚠️ 部分支持 | 使用客户端聚合 |
| `UNION` | ❌ 不支持 | |
| `子查询` | ❌ 不支持 | |

### Phase 2 (混合模式)

通过智能路由，复杂查询自动转发到关系型数据库：

- ✅ `JOIN`, `GROUP BY`, `HAVING` → 路由到关系型数据库
- ✅ `子查询`, `CTE`, `窗口函数` → 路由到关系型数据库
- ✅ 保留 CouchDB 简单查询的性能优势

---

## 🧪 测试状态

!!! success "测试结果: ✅ 99.8% 通过率 (487/488)"

    | 测试类别 | 通过/总数 | 状态 |
    |---------|----------|------|
    | 编译器测试 | 100% | ✅ |
    | 同步测试 | 100% | ✅ |
    | 异步测试 | 100% | ✅ |
    | 集成测试 | 100% | ✅ |
    | **代码覆盖率** | **80%** | 🎉 |

---

## 📚 文档导航

### 新手入门

- [📦 安装指南](getting-started/installation.md) - 环境配置和安装
- [🎯 基础用法](getting-started/basic-usage.md) - 快速上手教程
- [🔌 连接配置](getting-started/connection.md) - 连接选项详解

### 用户指南

- [⚡ 同步操作](guide/sync-operations.md) - 同步模式完整指南
- [🔄 异步操作](guide/async-operations.md) - 异步模式完整指南
- [🔀 SQL 转 Mango Query](guide/sql-to-mango.md) - 查询转换原理
- [🎨 类型映射](guide/type-mapping.md) - 数据类型转换
- [🔗 混合数据库模式](guide/hybrid-mode.md) - Phase 2 混合架构

### API 参考

- [🔧 Dialect API](api/dialect.md) - SQLAlchemy 方言接口
- [⚙️ Compiler API](api/compiler.md) - SQL 编译器
- [📡 Client API](api/client.md) - CouchDB 客户端
- [🏷️ Types API](api/types.md) - 类型系统
- [⚠️ Exceptions API](api/exceptions.md) - 异常处理

---

## 🎯 特性亮点

### 批量插入优化

```python
from sqlalchemy import insert

# 批量插入（3-10x 性能提升）
users = [
    {"name": "User1", "age": 25},
    {"name": "User2", "age": 30},
    # ... 更多数据
]

with engine.connect() as conn:
    conn.execute(insert(users_table), users)
    conn.commit()
```

### 查询缓存

```python
from sqlalchemy_couchdb.cache import QueryCache

# 启用查询缓存
cache = QueryCache(max_size=1000, ttl=300)

# 缓存会自动处理
result = conn.execute(query)  # 第一次：查询数据库
result = conn.execute(query)  # 第二次：从缓存读取
```

### 智能路由（Phase 2）

```python
# 自动路由
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost/pgdb'
)

# 简单查询 → CouchDB（快）
result = conn.execute("SELECT * FROM users WHERE age > 25")

# 复杂查询 → PostgreSQL（功能完整）
result = conn.execute("""
    SELECT u.name, COUNT(o.id) as order_count
    FROM users u
    JOIN orders o ON u.id = o.user_id
    GROUP BY u.name
""")
```

---

## 🔗 快速链接

- [GitHub 仓库](https://github.com/getaix/sqlalchemy-couchdb)
- [PyPI 包](https://pypi.org/project/sqlalchemy-couchdb/)
- [问题报告](https://github.com/getaix/sqlalchemy-couchdb/issues)
- [贡献指南](about/contributing.md)

---

## 📄 许可证

本项目采用 [MIT 许可证](about/license.md)。

---

<p align="center">
  <strong>⭐ 如果觉得有用，请给我们一个 Star！</strong>
</p>

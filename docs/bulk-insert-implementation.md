# 批量插入实现方案

**创建日期**: 2025-11-02
**状态**: 设计中
**目标**: 使用CouchDB的`_bulk_docs` API实现高性能批量插入

## 📋 当前状态

### 现有实现
- ✅ **Client层**: `bulk_docs()` 方法已实现（同步+异步）
- ⚠️ **DBAPI层**: 使用循环调用单条插入
- ⚠️ **Compiler层**: 仅支持单条INSERT编译
- ❌ **Dialect层**: `supports_multivalues_insert = False`

### 性能现状
```python
# 当前方式：循环插入100条记录
for i in range(100):
    conn.execute(insert(users).values(name=f"User{i}", age=20+i))
conn.commit()
# 耗时：~3-5秒（100次HTTP请求）
```

### 目标性能
```python
# 目标方式：批量插入100条记录
conn.execute(insert(users), [
    {"name": f"User{i}", "age": 20+i} for i in range(100)
])
conn.commit()
# 预期耗时：~0.5秒（1次HTTP请求）
```

## 🎯 SQLAlchemy 2.0 insertmanyvalues 机制

### 核心概念

1. **insertmanyvalues** (SQLAlchemy 2.0.10+)
   - 批量INSERT优化特性
   - 支持INSERT..RETURNING with executemany
   - 自动分页处理大批量数据
   - 默认批次大小：1000行

2. **Dialect属性**
   ```python
   supports_multivalues_insert = True  # 启用多值插入支持
   ```

3. **执行方式**
   ```python
   # executemany - 传统批量插入
   conn.execute(stmt, [{"name": "Alice"}, {"name": "Bob"}])

   # insertmanyvalues - SQLAlchemy 2.0优化方式
   # 自动使用，无需额外配置
   ```

### CouchDB特殊性

CouchDB与关系型数据库的差异：

| 特性 | 关系型数据库 | CouchDB |
|------|------------|---------|
| 批量插入API | `INSERT INTO ... VALUES (...), (...)` | `POST /db/_bulk_docs` |
| RETURNING支持 | 支持 | 不支持（但bulk_docs返回_id/_rev） |
| 绑定参数 | 支持 | 无（直接JSON） |
| 事务支持 | 支持 | 不支持（仅文档级原子性） |

## 🔧 实现方案

### 方案架构

```
User Code (executemany)
    ↓
SQLAlchemy Core
    ↓
CouchDBDialect (启用 supports_multivalues_insert)
    ↓
CouchDBCompiler (编译为批量JSON)
    ↓
DBAPI (do_executemany_returning)
    ↓
CouchDBClient.bulk_docs()
    ↓
CouchDB _bulk_docs API
```

### 实现步骤

#### 1. Dialect层修改

**文件**: `sqlalchemy_couchdb/dialect.py`

```python
class CouchDBDialect(default.DefaultDialect):
    # 启用多值插入支持
    supports_multivalues_insert = True

    # 配置批次大小（CouchDB推荐<1000）
    insert_executemany_returning = True
    insertmanyvalues_page_size = 500  # 保守设置

    def do_executemany(self, cursor, statement, parameters, context=None):
        """执行批量操作"""
        # 将parameters合并到statement的JSON中
        # 调用cursor.executemany()
        pass
```

#### 2. Compiler层修改

**文件**: `sqlalchemy_couchdb/compiler.py`

当前的`visit_insert()`只处理单条：
```python
def visit_insert(self, insert_stmt, **kwargs):
    document = {"type": table_name}
    for col_name, value in insert_stmt._values.items():
        document[col_name] = self._extract_value(value)

    query = {
        "type": "insert",
        "table": table_name,
        "document": document
    }
    return json.dumps(query)
```

需要修改为支持批量：
```python
def visit_insert(self, insert_stmt, **kwargs):
    """
    编译INSERT语句（支持单条和批量）

    单条：
        {"type": "insert", "table": "users", "document": {...}}

    批量（带executemany标记）：
        {"type": "insert_many", "table": "users", "documents": [...]}
    """
    table_name = self._get_table_name(insert_stmt)

    # 检查是否是批量插入
    if self._is_bulk_insert(insert_stmt):
        # 编译为批量格式
        query = {
            "type": "insert_many",
            "table": table_name,
            "documents": []  # 占位符，DBAPI层填充
        }
    else:
        # 单条插入（保持兼容）
        document = self._build_document(insert_stmt, table_name)
        query = {
            "type": "insert",
            "table": table_name,
            "document": document
        }

    return json.dumps(query)

def _is_bulk_insert(self, insert_stmt):
    """检查是否是批量插入"""
    # SQLAlchemy会在context中设置executemany标记
    # 或者通过insert_stmt的属性判断
    return getattr(insert_stmt, '_is_bulk', False)

def _build_document(self, insert_stmt, table_name):
    """构建单个文档"""
    document = {"type": table_name}
    if hasattr(insert_stmt, '_values') and insert_stmt._values:
        for col_name, value in insert_stmt._values.items():
            if col_name not in ("_id", "_rev"):
                document[col_name] = self._extract_value(value)
    return document
```

#### 3. DBAPI层修改

**文件**: `sqlalchemy_couchdb/dbapi/sync.py` 和 `async_.py`

添加批量执行支持：

```python
class SyncCursor:
    def executemany(self, operation, seq_of_parameters):
        """
        执行批量操作

        参数:
            operation: JSON编译后的查询（包含insert_many类型）
            seq_of_parameters: 参数列表 [{"name": "Alice", ...}, ...]
        """
        query = json.loads(operation)

        if query.get("type") != "insert_many":
            # 不支持其他批量操作，回退到循环
            for params in seq_of_parameters:
                self.execute(operation, params)
            return

        # 构建批量文档
        table_name = query["table"]
        documents = []

        for params in seq_of_parameters:
            doc = {"type": table_name}
            doc.update(params)
            documents.append(doc)

        # 调用bulk_docs API
        try:
            result = self.connection.client.bulk_docs(documents)

            # 处理结果
            self.rowcount = len([r for r in result if not r.get('error')])
            self._last_result = result

            # 设置description（兼容性）
            self.description = [("_id",), ("_rev",)]

        except Exception as e:
            raise exception_from_response(None, str(e))

    def fetchall(self):
        """返回批量插入的结果"""
        if hasattr(self, '_last_result'):
            # 格式化为标准行格式
            rows = []
            for item in self._last_result:
                if not item.get('error'):
                    rows.append((item.get('id'), item.get('rev')))
            return rows
        return []
```

异步版本类似：
```python
class AsyncCursor:
    async def executemany(self, operation, seq_of_parameters):
        """异步批量执行"""
        # 实现与同步版本类似，但使用await
        await self.connection.client.bulk_docs(documents)
```

#### 4. 错误处理

批量操作可能部分成功：

```python
# CouchDB bulk_docs响应示例
[
    {"ok": true, "id": "doc1", "rev": "1-abc"},
    {"error": "conflict", "id": "doc2", "reason": "Document update conflict"},
    {"ok": true, "id": "doc3", "rev": "1-def"}
]
```

需要处理策略：
- **全部成功**: 正常返回
- **全部失败**: 抛出IntegrityError
- **部分失败**:
  - 选项1: 抛出异常，包含详细错误信息
  - 选项2: 返回成功的记录数，错误记录单独存储

推荐**选项1**（严格模式）：
```python
if any(r.get('error') for r in result):
    errors = [r for r in result if r.get('error')]
    raise IntegrityError(
        f"批量插入部分失败: {len(errors)}/{len(result)} 失败\n"
        f"详细信息: {errors[:5]}"  # 最多显示5个错误
    )
```

## 📊 性能预期

### 基准测试计划

**测试场景**:
- 插入100条记录
- 插入1000条记录
- 插入5000条记录

**对比指标**:

| 记录数 | 当前方式（循环） | 批量方式（bulk_docs） | 性能提升 |
|--------|----------------|---------------------|----------|
| 100    | ~3秒 (100请求)  | ~0.5秒 (1请求)       | 6x ⚡    |
| 1000   | ~30秒 (1000请求)| ~2秒 (2请求)         | 15x ⚡   |
| 5000   | ~150秒 (5000请求)| ~10秒 (10请求)      | 15x ⚡   |

**注意事项**:
- 批次大小限制：500条/批（可配置）
- 大于500条自动分批
- 网络延迟影响减少95%+

## 🧪 测试计划

### 单元测试

**文件**: `tests/test_bulk_insert.py`

```python
def test_bulk_insert_100_records():
    """测试批量插入100条记录"""
    users = [
        {"name": f"User{i}", "age": 20 + i}
        for i in range(100)
    ]

    conn.execute(insert(users_table), users)

    result = conn.execute(select(users_table)).fetchall()
    assert len(result) == 100

def test_bulk_insert_partial_failure():
    """测试批量插入部分失败的处理"""
    # 包含重复ID的记录
    users = [
        {"_id": "user1", "name": "Alice"},
        {"_id": "user1", "name": "Bob"},  # 重复ID
    ]

    with pytest.raises(IntegrityError):
        conn.execute(insert(users_table), users)

async def test_async_bulk_insert():
    """测试异步批量插入"""
    async with engine.connect() as conn:
        users = [{"name": f"User{i}"} for i in range(100)]
        await conn.execute(insert(users_table), users)

        result = await conn.execute(select(users_table))
        rows = result.fetchall()
        assert len(rows) == 100
```

### 性能测试

**文件**: `tests/test_bulk_performance.py`

```python
def test_bulk_insert_performance():
    """对比批量插入与循环插入的性能"""
    import time

    # 循环方式
    start = time.perf_counter()
    for i in range(100):
        conn.execute(insert(users_table).values(name=f"User{i}"))
    conn.commit()
    loop_time = time.perf_counter() - start

    cleanup()

    # 批量方式
    start = time.perf_counter()
    users = [{"name": f"User{i}"} for i in range(100)]
    conn.execute(insert(users_table), users)
    conn.commit()
    bulk_time = time.perf_counter() - start

    print(f"循环插入: {loop_time:.3f}秒")
    print(f"批量插入: {bulk_time:.3f}秒")
    print(f"性能提升: {loop_time/bulk_time:.1f}x")

    assert bulk_time < loop_time / 3  # 至少快3倍
```

## ⚠️ 注意事项

### CouchDB限制

1. **请求大小限制**
   - 默认最大请求：4MB
   - 需要配置: `max_document_size` 和 `max_http_request_size`
   - 建议批次大小：500条（保守）

2. **无事务支持**
   - bulk_docs是原子性的文档级操作
   - 部分失败时无法自动回滚
   - 需要应用层处理

3. **_id冲突处理**
   - 如果提供_id，必须唯一
   - 建议让CouchDB自动生成

### SQLAlchemy兼容性

1. **RETURNING模拟**
   - CouchDB不支持RETURNING语法
   - 但bulk_docs返回_id和_rev
   - 可以模拟RETURNING行为

2. **executemany参数格式**
   - SQLAlchemy传递: `[{col: val}, {col: val}]`
   - 需要转换为CouchDB文档格式

## 📝 实施检查清单

- [x] 研究SQLAlchemy 2.0 insertmanyvalues接口
- [ ] 修改`dialect.py`启用批量支持
- [ ] 修改`compiler.py`支持批量编译
- [ ] 修改`dbapi/sync.py`实现executemany
- [ ] 修改`dbapi/async_.py`实现异步executemany
- [ ] 添加错误处理（部分失败场景）
- [ ] 编写单元测试
- [ ] 编写性能测试
- [ ] 更新文档和示例
- [ ] 更新TODO.md和CHANGELOG.md

## 🎓 参考资料

1. **SQLAlchemy官方文档**
   - [Insert, Updates, Deletes](https://docs.sqlalchemy.org/en/20/core/dml.html)
   - [Core Internals](https://docs.sqlalchemy.org/en/20/core/internals.html)

2. **CouchDB文档**
   - [Bulk Document API](https://docs.couchdb.org/en/stable/api/database/bulk-api.html)
   - [POST /{db}/_bulk_docs](https://docs.couchdb.org/en/stable/api/database/bulk-api.html#post--db-_bulk_docs)

3. **实现参考**
   - [psycopg2 fast execution helper](https://github.com/sqlalchemy/sqlalchemy/discussions/12038)
   - BigQuery dialect insertmanyvalues讨论

---

**版本**: v1.0
**最后更新**: 2025-11-02

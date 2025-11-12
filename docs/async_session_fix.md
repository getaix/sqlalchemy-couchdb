# CouchDBAsyncSession NotImplementedError 修复说明

## 问题描述

在使用 `CouchDBAsyncSession` 执行 SELECT 查询时，会遇到 `NotImplementedError` 错误：

```python
NotImplementedError
  File "/opt/homebrew/Caskroom/miniconda/base/lib/python3.12/site-packages/sqlalchemy/engine/result.py", line 156, in _indexes_for_keys
    raise NotImplementedError()
```

这是因为 SQLAlchemy ORM 尝试对查询结果进行完整的 ORM 映射时，CouchDB 方言的 cursor 元数据实现不完整。

## 解决方案

### 1. 修改 `CouchDBAsyncSession` (sqlalchemy-couchdb)

在 `sqlalchemy_couchdb/orm/async_session.py` 中：

- **添加了 `CouchDBResult` 类**：包装原始 Result 对象，提供简化的数据访问接口
- **添加了 `CouchDBScalars` 类**：提供标量结果访问
- **修改了 `execute()` 方法**：
  ```python
  async def execute(self, statement: Any) -> Any:
      from sqlalchemy.sql import Select

      # 对于 SELECT 查询，使用特殊处理避免 ORM 映射
      if isinstance(statement, Select):
          conn = await self._session.connection()
          result = await conn.execute(statement)
          return CouchDBResult(result, statement)
      else:
          # INSERT/UPDATE/DELETE 正常执行
          result = await self._session.execute(statement)
          return result
  ```

### 2. 修改 Repository 层 (应用代码)

在 `app/modules/audit_log/repositories/audit_log.py` 中：

```python
async def lists(self, condition: dict[str, Any] | None, page: int = 1, page_size: int = 20) -> list[AuditLog]:
    stmt = select(AuditLog)
    if condition:
        stmt = stmt.filter_by(**condition)
    stmt = stmt.offset((page - 1) * page_size).limit(page_size).order_by(AuditLog.create_time.desc())
    result = await self.session.execute(stmt)

    # CouchDBAsyncSession 返回的是 tuple，需要手动转换为模型对象
    rows = result.all()
    audit_logs = []
    for row in rows:
        if isinstance(row, tuple):
            audit_log = self._tuple_to_model(row)
            audit_logs.append(audit_log)
        else:
            audit_logs.append(row)

    return audit_logs

def _tuple_to_model(self, row_tuple: tuple) -> AuditLog:
    """将行元组转换为 AuditLog 对象"""
    columns = [col.name for col in AuditLog.__table__.columns]
    kwargs = {}
    for i, col_name in enumerate(columns):
        if i < len(row_tuple):
            kwargs[col_name] = row_tuple[i]
    return AuditLog(**kwargs)
```

## 使用说明

### SELECT 查询

```python
async with SessionFactory() as session:
    stmt = select(AuditLog).where(AuditLog.log_type == "operation").limit(5)
    result = await session.execute(stmt)

    # 方式 1: 获取所有行（元组形式）
    rows = result.all()  # 返回 list[tuple]

    # 方式 2: 获取标量（第一列）
    scalars = result.scalars().all()  # 返回 list[Any]

    # 方式 3: 获取单个标量值
    scalar = result.scalar()  # 返回第一行的第一列
```

### COUNT 查询

```python
async with SessionFactory() as session:
    stmt = select(func.count()).select_from(AuditLog)
    result = await session.execute(stmt)
    count = result.scalar()  # 直接获取计数值
```

### 手动转换为 ORM 对象

```python
rows = result.all()
for row_tuple in rows:
    # 将元组转换为模型对象
    columns = [col.name for col in AuditLog.__table__.columns]
    kwargs = {col_name: row_tuple[i] for i, col_name in enumerate(columns) if i < len(row_tuple)}
    audit_log = AuditLog(**kwargs)
```

## 测试

运行测试脚本验证修复：

```bash
python /opt/data/www/yfb/packages/sqlalchemy-couchdb/test_complete_workflow.py
```

期望输出：
```
======================================================================
测试 CouchDBAsyncSession 完整工作流
======================================================================

【测试 1】SELECT 查询（带过滤）
✅ 查询成功，返回 5 条记录

【测试 2】COUNT 查询
✅ COUNT 查询成功，记录总数: 112

【测试 3】转换为模型对象
✅ 成功转换为 AuditLog 对象

======================================================================
✅ 所有测试通过！
======================================================================
```

## 注意事项

1. **不支持完整的 ORM 功能**：由于跳过了 SQLAlchemy 的 ORM 映射，一些高级 ORM 特性（如关系加载、延迟加载等）不可用。

2. **需要手动转换**：应用层需要手动将元组数据转换为 ORM 对象。建议在 Repository 层封装转换逻辑。

3. **性能考虑**：这种方法实际上性能更好，因为跳过了复杂的 ORM 映射过程。

4. **向后兼容**：对于 INSERT/UPDATE/DELETE 操作，仍使用标准的 SQLAlchemy 流程。

## 未来改进

可以考虑以下改进方向：

1. 在 `CouchDBResult` 中自动检测模型类并进行转换
2. 提供装饰器简化 Repository 层的转换逻辑
3. 改进 CouchDB 方言的元数据支持，彻底解决 `NotImplementedError`

## 相关文件

- `packages/sqlalchemy-couchdb/sqlalchemy_couchdb/orm/async_session.py` - 核心修复
- `depm/backend/app/modules/audit_log/repositories/audit_log.py` - 应用层适配
- `packages/sqlalchemy-couchdb/test_complete_workflow.py` - 测试脚本
- `packages/sqlalchemy-couchdb/docs/accessing_client_from_session.md` - 相关文档

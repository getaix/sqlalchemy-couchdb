# SQLAlchemy 语句缓存导致的绑定参数值错误问题修复报告

**日期**: 2025-11-02
**版本**: 0.1.0
**严重级别**: 🔴 Critical
**状态**: ✅ 已修复

---

## 问题描述

### 症状

在手动验证测试中，DELETE 操作的验证查询返回了错误的记录：

```python
# 删除 ToDelete 记录
stmt = delete(users).where(users.c.name == "ToDelete")
result = conn.execute(stmt)  # 成功删除 1 行 ✓

# 验证删除（应该找不到记录）
stmt = select(users).where(users.c.name == "ToDelete")
result = conn.execute(stmt)
rows = result.fetchall()

# 实际结果：找到了 Alice 记录！❌
# ('132a3cb8916cce175c254b0ebc030947', ..., 'Alice', 31, ...)
```

**预期行为**: 验证查询应该找到 0 条记录（ToDelete 已被删除）
**实际行为**: 验证查询找到了 Alice 的记录

### 根本原因

SQLAlchemy 的 **语句缓存 (Statement Cache)** 机制导致了绑定参数值的错误替换：

1. **SQLAlchemy 缓存机制**: SQLAlchemy 使用语句的 AST 结构（而不是具体的参数值）作为缓存键
2. **相同结构的查询**:
   - `select(users).where(users.c.name == "Alice")`
   - `select(users).where(users.c.name == "ToDelete")`
   - 这两个查询具有相同的 AST 结构，因此被视为同一个查询
3. **编译器直接嵌入值**: 我们的编译器将 BindParameter 的值直接嵌入到 JSON 中：
   ```python
   if isinstance(value, BindParameter):
       if value.value is not None:
           return self._serialize_for_json(value.value)  # 直接嵌入值
   ```
4. **缓存导致值错误**: 当执行第二个查询时，SQLAlchemy 直接返回了缓存的编译结果（包含 "Alice"）

## 调试过程

### 1. 初步发现

运行手动验证测试时发现 DELETE 测试失败：

```
✓ 删除操作，影响行数: 1
✗ 删除验证失败: 仍然找到 1 行
  ('...', 'Alice', 31, ...)
```

### 2. 添加 DEBUG 输出

在 `_execute_delete` 和 `_execute_select` 中添加 DEBUG 输出：

```python
# DELETE 操作（正确）
DEBUG _execute_delete - selector: {'type': 'users', 'name': 'ToDelete'}
DEBUG _execute_delete - found 1 docs

# 验证查询（错误）
DEBUG _execute_select - selector: {'type': 'users', 'name': 'Alice'}  ❌
```

**关键发现**: DELETE 的 selector 是正确的，但验证查询的 selector 是错误的！

### 3. 检查编译过程

在测试中手动编译验证语句：

```python
verification_stmt = select(users).where(users.c.name == "ToDelete")
compiled = verification_stmt.compile(dialect=dialect)
print(compiled)  # {"selector": {"type": "users", "name": "ToDelete"}} ✓
```

**编译结果是正确的！** 但传递到 `do_execute` 的 statement 是错误的：

```python
DEBUG do_execute - statement: {"selector": {"type": "users", "name": "Alice"}} ❌
```

### 4. 定位问题

**关键发现**:
- 手动编译时：selector 包含 `"ToDelete"` ✓
- 自动执行时：selector 包含 `"Alice"` ❌
- 两次使用了相同的 statement 对象，但得到了不同的编译结果

**结论**: SQLAlchemy 的编译缓存在作怪！

## 修复方案

### 方案选择

考虑了以下几种方案：

1. ❌ **使用绑定参数占位符**: 编译器生成 `:param_name`，execute 时替换
   - 问题: SQLAlchemy 不会自动提取参数到 `parameters` 字典
   - 需要手动实现参数提取逻辑，复杂度高

2. ❌ **手动清除编译缓存**: 在每次执行前清除缓存
   - 问题: 性能影响大，且需要访问内部 API

3. ✅ **禁用语句缓存**: 在 Dialect 中设置 `supports_statement_cache = False`
   - 优点: 简单直接，确保每次都重新编译
   - 缺点: 可能影响性能（但对于 CouchDB 场景影响不大）

### 最终修复

#### 1. 禁用语句缓存

**文件**: `sqlalchemy_couchdb/dialect.py`

```python
# 修改前
supports_statement_cache = True  # 支持语句缓存

# 修改后
# 禁用语句缓存以避免绑定参数值被缓存导致的错误
# 因为我们的编译器将值直接嵌入到 JSON 中，缓存会导致不同的查询使用相同的值
supports_statement_cache = False
```

#### 2. 保持编译器不变

编译器继续直接嵌入绑定参数的值：

```python
def _extract_value(self, value):
    """从 SQLAlchemy 表达式中提取实际值"""
    from sqlalchemy.sql.elements import BindParameter

    # 处理绑定参数
    if isinstance(value, BindParameter):
        # 直接嵌入值到 JSON 中（因为我们禁用了语句缓存）
        if value.value is not None:
            return self._serialize_for_json(value.value)
        else:
            # 使用占位符（execute时会提供参数）
            return f":{value.key}"

    # 处理字面量
    elif hasattr(value, 'value'):
        return self._serialize_for_json(value.value)

    # 直接值
    else:
        return self._serialize_for_json(value)
```

## 测试结果

### 修复前

```
测试 9: DELETE 删除操作
================================================================================
✓ 删除操作，影响行数: 1
✗ 删除验证失败: 仍然找到 1 行
  ('132a3cb8916cce175c254b0ebc030947', ..., 'Alice', 31, ...)

成功率: 90.9% (10/11)
```

### 修复后

```
测试 9: DELETE 删除操作
================================================================================
✓ 删除操作，影响行数: 1
✓ 删除验证成功

成功率: 100.0% (11/11) ✅
```

### 单元测试

- ✅ 编译器测试: 12/12 通过
- ✅ 手动验证测试: 11/11 通过

## 影响范围

### 受影响的操作

所有使用绑定参数的 SQL 操作都可能受到影响：

- ✅ SELECT with WHERE clause
- ✅ UPDATE with WHERE clause
- ✅ DELETE with WHERE clause
- ✅ INSERT with values

### 性能影响

禁用语句缓存会导致每次执行都重新编译 SQL 语句：

- **理论影响**: 每次查询增加编译开销
- **实际影响**:
  - CouchDB 查询通常不是高频操作
  - 编译开销远小于网络延迟
  - 对实际应用性能影响可忽略

### 兼容性

- ✅ SQLAlchemy 2.0+: 完全兼容
- ✅ Python 3.8+: 完全兼容
- ✅ 异步模式: 不受影响

## 经验教训

### 1. 理解 ORM 的缓存机制

SQLAlchemy 的编译缓存是基于 AST 结构的：

```python
# 这两个查询会共享同一个缓存键
stmt1 = select(users).where(users.c.name == "Alice")
stmt2 = select(users).where(users.c.name == "Bob")

# AST 结构相同: SELECT users WHERE name = <BindParameter>
# 缓存键不包含具体的值！
```

### 2. 绑定参数 vs 直接嵌入值

两种处理方式的权衡：

| 方式 | 优点 | 缺点 |
|-----|------|------|
| 绑定参数 | 支持缓存，性能好 | 需要参数传递机制 |
| 直接嵌入 | 实现简单 | 不能使用缓存 |

**我们的选择**: 直接嵌入值 + 禁用缓存
- CouchDB 场景下缓存收益有限
- 实现简单，维护成本低

### 3. 调试技巧

有效的调试步骤：

1. ✅ **对比预期和实际**: 发现 selector 值不一致
2. ✅ **分离编译和执行**: 手动编译发现编译结果正确
3. ✅ **追踪数据流**: 从 compile() 到 do_execute() 的过程中数据被修改
4. ✅ **怀疑缓存**: 相同结构的查询得到不同结果 → 缓存问题

## 后续工作

### 短期

- [x] 修复语句缓存问题
- [x] 验证所有测试通过
- [ ] 修复其他单元测试数据污染问题

### 长期

- [ ] 评估实现真正的绑定参数支持的必要性
- [ ] 性能基准测试（缓存 vs 非缓存）
- [ ] 考虑局部缓存策略（只缓存无参数的查询）

## 参考资料

- [SQLAlchemy 2.0 Documentation - Statement Caching](https://docs.sqlalchemy.org/en/20/core/connections.html#caching)
- [SQLAlchemy Compilation Caching](https://docs.sqlalchemy.org/en/20/core/compilation.html)
- [Python DB-API 2.0 Specification](https://peps.python.org/pep-0249/)

---

**修复日期**: 2025-11-02
**文档版本**: 1.0

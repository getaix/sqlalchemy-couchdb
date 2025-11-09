# Dialect API

## 概述

`CouchDBDialect` 是 SQLAlchemy 方言实现，负责将 SQLAlchemy 的连接、游标等概念映射到 CouchDB。

## 类层次

```
CouchDBDialect
├── CouchDBDialect  (基类)
├── AsyncCouchDBDialect (异步方言)
```

## CouchDBDialect

### 类定义

```python
from sqlalchemy.dialects.postgresql.base import PGDialect
from sqlalchemy.engine.interfaces import Dialect

class CouchDBDialect(PGDialect):
    """CouchDB 方言实现"""
```

### 初始化

```python
def __init__(self, **kwargs):
    super().__init__(**kwargs)
    self.client = None  # 将被设置
```

### 主要属性

- **name**: `'couchdb'`
- **driver**: `'couchdb'`
- **default_schema_name**: `'main'`

### 关键方法

#### create_connect_args()

创建连接参数。

**签名**:
```python
def create_connect_args(self, url) -> Tuple[dict, dict]:
    """解析 URL 并返回连接参数"""
```

**返回**:
```python
(
    {  # 位置参数
        'base_url': 'http://localhost:5984',
        'database': 'mydb',
        'username': 'admin',
        'password': 'password'
    },
    {}  # 关键字参数
)
```

**URL 解析规则**:

| URL 格式 | 解析结果 |
|---------|---------|
| `couchdb://localhost/mydb` | 无认证 |
| `couchdb://user:pass@host/db` | 用户名密码认证 |
| `couchdb+async://...` | 异步模式 |

#### get_dbapi_module()

返回 DBAPI 模块。

**签名**:
```python
def get_dbapi_module(self) -> ModuleType:
    """返回 DBAPI 模块"""
```

**返回**:
- 同步模式: `sqlalchemy_couchdb.dbapi.sync`
- 异步模式: `sqlalchemy_couchdb.dbapi.async_`

#### create_client()

创建 CouchDB 客户端。

**签名**:
```python
def create_client(self, **kwargs) -> CouchDBClient:
    """创建 CouchDB 客户端"""
```

#### get_indexes()

获取索引列表。

**签名**:
```python
def get_indexes(self, connection, table_name, schema=None, **kwargs) -> List[dict]:
    """获取表的索引"""
```

#### get_columns()

获取列信息。

**签名**:
```python
def get_columns(self, connection, table_name, schema=None, **kwargs) -> List[dict]:
    """获取表的列信息"""
```

#### get_table_names()

获取表名列表。

**签名**:
```python
def get_table_names(self, connection, schema=None, **kwargs) -> List[str]:
    """获取所有表名"""
```

**注意**: 在 CouchDB 中，"表"通过 `type` 字段模拟。

#### get_view_names()

获取视图名列表。

**签名**:
```python
def get_view_names(self, connection, schema=None, **kwargs) -> List[str]:
    """获取所有视图名"""
```

## AsyncCouchDBDialect

异步方言实现。

```python
class AsyncCouchDBDialect(CouchDBDialect):
    """异步 CouchDB 方言"""
```

### 特殊处理

- 使用 `@await_only` 装饰器包装异步操作
- 通过 greenlet 实现同步到异步的桥接

## 使用示例

### 创建方言

```python
from sqlalchemy import create_engine
from sqlalchemy_couchdb.dialect import CouchDBDialect

# 手动创建方言
dialect = CouchDBDialect()

# 或通过引擎
engine = create_engine('couchdb://localhost:5984/mydb')
dialect = engine.dialect

print(f"方言名称: {dialect.name}")
print(f"驱动: {dialect.driver}")
```

### 自定义方言

```python
from sqlalchemy_couchdb.dialect import CouchDBDialect

class CustomCouchDBDialect(CouchDBDialect):
    """自定义方言"""

    def create_client(self, **kwargs):
        """重写客户端创建"""
        # 自定义逻辑
        return super().create_client(**kwargs)

    def get_table_names(self, connection, schema=None, **kwargs):
        """自定义表名获取"""
        # 自定义逻辑
        return super().get_table_names(connection, schema, **kwargs)

# 使用自定义方言
dialect = CustomCouchDBDialect()
engine = create_engine('couchdb://localhost:5984/mydb', dialect=dialect)
```

## 内部实现

### 连接建立流程

```mermaid
sequenceDiagram
    participant U as User
    participant E as Engine
    participant D as Dialect
    participant C as Client
    participant DB as CouchDB

    U->>E: create_engine()
    E->>D: create_connect_args()
    D->>C: create_client()
    D->>DB: ping() 检查连接
    DB-->>D: OK
    D-->>E: 连接参数
    E-->>U: 引擎创建完成
```

### SQL 编译流程

```mermaid
sequenceDiagram
    participant C as Client
    participant S as SQL
    participant Comp as Compiler
    participant M as Mango Query
    participant DB as CouchDB

    C->>S: execute()
    S->>Comp: visit_select()
    Comp->>Comp: _compile_where()
    Comp->>Comp: _compile_order_by()
    Comp->>M: 生成查询
    M->>DB: POST /_find
    DB-->>M: 结果
    M-->>C: 文档列表
    C-->>S: Result
    S-->>Client: 行数据
```

## 事务支持

### 事务处理

```python
def supports_sane_rowcount(self) -> bool:
    """是否支持行数统计"""
    return False

def supports_sane_multi_rowcount(self) -> bool:
    """是否支持多行统计"""
    return False

def supports_unicode_statements(self) -> bool:
    """是否支持 Unicode SQL"""
    return True
```

### 提交行为

```python
# 在 CouchDB 中，commit() 是 no-op
# 因为 CouchDB 文档级原子性，无多文档事务
def do_commit(self, connection):
    """提交事务 (空实现)"""
    pass

def do_rollback(self, connection):
    """回滚事务 (空实现)"""
    pass
```

## 反射支持

### 表反射

```python
# 查询表结构
from sqlalchemy import inspect

inspector = inspect(engine)
tables = inspector.get_table_names()
columns = inspector.get_columns('users')
indexes = inspector.get_indexes('users')
```

### 反射结果示例

```python
# 表名列表
['users', 'orders', 'products']

# 列信息
[
    {'name': '_id', 'type': VARCHAR(), 'nullable': False},
    {'name': '_rev', 'type': VARCHAR(), 'nullable': True},
    {'name': 'name', 'type': VARCHAR(), 'nullable': True},
    {'name': 'age', 'type': INTEGER(), 'nullable': True},
    {'name': 'type', 'type': VARCHAR(), 'nullable': False},
]

# 索引信息
[
    {
        'name': 'age-index',
        'column_names': ['age'],
        'unique': False
    }
]
```

## 连接池支持

### 连接池类型

```python
# 默认使用 QueuePool
engine = create_engine(
    'couchdb://localhost:5984/mydb',
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
)
```

### 连接预检查

```python
# 启用预检查
engine = create_engine(
    'couchdb://localhost:5984/mydb',
    pool_pre_ping=True,  # 从池中获取连接前测试
)
```

## 错误处理

### 错误转换

```python
def _handle_exception(self, e):
    """将 CouchDB HTTP 错误转换为 DB-API 异常"""
    if e.status_code == 404:
        raise NoSuchTableError(e)
    elif e.status_code == 409:
        raise DocumentConflictError(e)
    elif e.status_code == 500:
        raise CouchDBError(e)
    else:
        raise DatabaseError(e)
```

### 异常映射

| HTTP 状态码 | SQLAlchemy 异常 |
|-------------|----------------|
| 404 | `NoSuchTableError` |
| 409 | `DocumentConflictError` |
| 500 | `DatabaseError` |
| 其他 | `DatabaseError` |

## 性能优化

### 1. 连接池配置

```python
engine = create_engine(
    'couchdb://localhost:5984/mydb',
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
)
```

### 2. 禁用不必要的反射

```python
# 手动指定表结构
users = Table('users', metadata,
    Column('_id', String, primary_key=True),
    Column('name', String),
    Column('type', String),
    schema=None  # 不使用 schema
)

# 或禁用自动反射
metadata = MetaData()
metadata.reflect(bind=engine, views=True)  # 仅在需要时反射
```

## 扩展指南

### 添加自定义类型

```python
from sqlalchemy_couchdb.dialect import CouchDBDialect

class CustomCouchDBDialect(CouchDBDialect):
    """支持自定义类型"""

    @property
    def colspecs(self):
        """返回类型映射"""
        base = super().colspecs or {}
        base.update({
            MyCustomType: MyCustomCouchDBType
        })
        return base
```

### 自定义编译器

```python
from sqlalchemy_couchdb.dialect import CouchDBDialect
from sqlalchemy_couchdb.compiler import CouchDBCompiler

class CustomCouchDBDialect(CouchDBDialect):
    """使用自定义编译器"""

    def create_compiler(self, compiler, **kwargs):
        """创建编译器实例"""
        return CustomCompiler(compiler.dialect, compiler.statement, **kwargs)
```

## 相关资源

- [SQLAlchemy 方言开发指南](https://docs.sqlalchemy.org/en/14/dialects/)
- [Compiler API](compiler.md)
- [Client API](client.md)
- [类型系统](types.md)

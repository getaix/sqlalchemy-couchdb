# 类型系统 API

## 概述

SQLAlchemy CouchDB 类型系统提供 Python ↔ JSON 的双向转换。

## 类型层次

```
BaseType (SQLAlchemy)
├── CouchDBString
├── CouchDBText
├── CouchDBInteger
├── CouchDBFloat
├── CouchDBBoolean
├── CouchDBDateTime
├── CouchDBDate
├── CouchDBJSON
└── CouchDBNumeric
```

## 类型详情

### CouchDBString

字符串类型。

```python
from sqlalchemy_couchdb.types import CouchDBString

Column('name', CouchDBString(255))

# 绑定处理器
processor = column_type.bind_processor(dialect)
result = processor("Alice")  # "Alice"

# 结果处理器
processor = column_type.result_processor(dialect, coltype)
result = processor("Alice")  # "Alice"
```

### CouchDBText

文本类型（长字符串）。

```python
from sqlalchemy_couchdb.types import CouchDBText

Column('description', CouchDBText())

# 与 CouchDBString 相同，但语义上表示长文本
```

### CouchDBInteger

整数类型。

```python
from sqlalchemy_couchdb.types import CouchDBInteger

Column('age', CouchDBInteger())

# Python → JSON
processor = CouchDBInteger().bind_processor(dialect)
result = processor(30)  # 30

# JSON → Python
processor = CouchDBInteger().result_processor(dialect, 'integer')
result = processor(30)  # 30
```

### CouchDBFloat

浮点数类型。

```python
from sqlalchemy_couchdb.types import CouchDBFloat

Column('price', CouchDBFloat())

# Python → JSON
processor = CouchDBFloat().bind_processor(dialect)
result = processor(99.99)  # 99.99

# JSON → Python
processor = CouchDBFloat().result_processor(dialect, 'float')
result = processor(99.99)  # 99.99
```

### CouchDBBoolean

布尔类型。

```python
from sqlalchemy_couchdb.types import CouchDBBoolean

Column('is_active', CouchDBBoolean())

# Python → JSON
processor = CouchDBBoolean().bind_processor(dialect)
result = processor(True)  # True
result = processor(False)  # False
result = processor(None)  # None

# JSON → Python
processor = CouchDBBoolean().result_processor(dialect, 'boolean')
result = processor(True)  # True
result = processor(False)  # False
result = processor(None)  # None
```

### CouchDBDateTime

日期时间类型（ISO 8601 格式）。

```python
from sqlalchemy_couchdb.types import CouchDBDateTime
from datetime import datetime

Column('created_at', CouchDBDateTime())

# Python → JSON
processor = CouchDBDateTime().bind_processor(dialect)
dt = datetime(2025, 1, 2, 15, 30, 0)
result = processor(dt)  # "2025-01-02T15:30:00"

# JSON → Python
processor = CouchDBDateTime().result_processor(dialect, 'datetime')
result = processor("2025-01-02T15:30:00")  # datetime(2025, 1, 2, 15, 30, 0)
```

**特点**:
- 使用 ISO 8601 格式
- 支持时区
- 自动处理 None 值

### CouchDBDate

日期类型（ISO 8601 格式）。

```python
from sqlalchemy_couchdb.types import CouchDBDate
from datetime import date

Column('birth_date', CouchDBDate())

# Python → JSON
processor = CouchDBDate().bind_processor(dialect)
d = date(2025, 1, 2)
result = processor(d)  # "2025-01-02"

# JSON → Python
processor = CouchDBDate().result_processor(dialect, 'date')
result = processor("2025-01-02")  # date(2025, 1, 2)
```

### CouchDBJSON

JSON 类型（对象或数组）。

```python
from sqlalchemy_couchdb.types import CouchDBJSON

Column('metadata', CouchDBJSON())

# Python → JSON (无转换)
processor = CouchDBJSON().bind_processor(dialect)
data = {"key": "value", "list": [1, 2, 3]}
result = processor(data)  # {"key": "value", "list": [1, 2, 3]}

# JSON → Python (无转换)
processor = CouchDBJSON().result_processor(dialect, 'json')
result = processor({"key": "value"})  # {"key": "value"}
```

**特点**:
- CouchDB 原生支持 JSON
- 无需转换
- 支持嵌套对象和数组

### CouchDBNumeric

高精度数值类型。

```python
from sqlalchemy_couchdb.types import CouchDBNumeric
from decimal import Decimal

Column('amount', CouchDBNumeric(precision=10, scale=2, as_string=True))

# as_string=True (默认，保持精度)
processor = CouchDBNumeric(as_string=True).bind_processor(dialect)
result = processor(Decimal("123.456789"))  # "123.456789"

processor = CouchDBNumeric(as_string=True).result_processor(dialect, 'numeric')
result = processor("123.456789")  # Decimal("123.456789")

# as_string=False (可能损失精度)
processor = CouchDBNumeric(as_string=False).bind_processor(dialect)
result = processor(Decimal("123.456789"))  # 123.456789

processor = CouchDBNumeric(as_string=False).result_processor(dialect, 'numeric')
result = processor(123.456789)  # 123.456789 (float)
```

**参数**:
- `precision`: 总位数
- `scale`: 小数位数
- `as_string`: 是否存储为字符串（默认 True）

## 类型映射配置

### colspecs 映射

```python
from sqlalchemy import types as sa_types
from sqlalchemy_couchdb.types import *

colspecs = {
    sa_types.String: CouchDBString,
    sa_types.Text: CouchDBText,
    sa_types.Integer: CouchDBInteger,
    sa_types.SmallInteger: CouchDBInteger,
    sa_types.BigInteger: CouchDBInteger,
    sa_types.Float: CouchDBFloat,
    sa_types.Numeric: CouchDBNumeric,
    sa_types.Boolean: CouchDBBoolean,
    sa_types.DateTime: CouchDBDateTime,
    sa_types.Date: CouchDBDate,
    sa_types.JSON: CouchDBJSON,
}
```

### 方言注册类型

```python
# 在方言中使用
class CouchDBDialect:
    @property
    def colspecs(self):
        from sqlalchemy_couchdb.types import colspecs
        return colspecs
```

## 使用示例

### 在表定义中使用

```python
from sqlalchemy import Table, Column, MetaData, String, Integer, Float, Boolean, DateTime, Date, JSON
from sqlalchemy_couchdb.types import *

metadata = MetaData()

users = Table('users', metadata,
    Column('_id', String, primary_key=True),
    Column('_rev', String),
    Column('name', CouchDBString(255)),
    Column('age', CouchDBInteger()),
    Column('price', CouchDBFloat()),
    Column('is_active', CouchDBBoolean()),
    Column('created_at', CouchDBDateTime()),
    Column('birth_date', CouchDBDate()),
    Column('metadata', CouchDBJSON()),
    Column('amount', CouchDBNumeric(precision=10, scale=2)),
    Column('type', String)
)
```

### 混合使用

```python
from sqlalchemy import String, Integer
from sqlalchemy_couchdb.types import CouchDBString, CouchDBInteger

# 标准类型（自动映射）
Column('name', String)  # → CouchDBString
Column('age', Integer)  # → CouchDBInteger

# 自定义类型
Column('name', CouchDBString(255))
Column('age', CouchDBInteger())
```

### 自定义类型

```python
from sqlalchemy import types
from sqlalchemy_couchdb.types import CouchDBString

class CouchDBEmail(CouchDBString):
    """邮箱类型"""

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            if '@' not in str(value):
                raise ValueError(f"无效邮箱: {value}")
            return str(value)
        return process

# 使用
Column('email', CouchDBEmail())
```

## 转换过程

### Python → CouchDB (绑定处理)

```python
def bind_processor(self, dialect: Dialect):
    """将 Python 值转换为 CouchDB JSON"""
    def process(value):
        if value is None:
            return None
        # 类型特定转换
        return self._convert_python_to_json(value)
    return process
```

### CouchDB → Python (结果处理)

```python
def result_processor(self, dialect: Dialect, coltype):
    """将 CouchDB JSON 转换为 Python"""
    def process(value):
        if value is None:
            return None
        # 类型特定转换
        return self._convert_json_to_python(value)
    return process
```

## 性能优化

### 1. 选择合适类型

```python
# ✅ 好：使用适当精度
Column('amount', CouchDBNumeric(precision=10, scale=2))

# ❌ 差：不必要高精度
Column('amount', CouchDBNumeric(precision=38, scale=20))
```

### 2. 避免不必要转换

```python
# CouchDBJSON 无转换，性能最佳
Column('data', CouchDBJSON())

# 其他类型都有转换开销
```

### 3. 预编译处理器

```python
# 预获取处理器
dialect = engine.dialect
processor = dialect.type_descriptor(CouchDBString()).bind_processor(dialect)

# 多次使用
for value in values:
    json_value = processor(value)
```

## 测试类型

### 测试绑定处理器

```python
from sqlalchemy_couchdb.types import CouchDBString
from sqlalchemy.engine.interfaces import Dialect

def test_bind_processor():
    dialect = Mock(spec=Dialect)
    processor = CouchDBString().bind_processor(dialect)

    # 测试值转换
    assert processor("Alice") == "Alice"
    assert processor(123) == "123"
    assert processor(None) is None
```

### 测试结果处理器

```python
from sqlalchemy_couchdb.types import CouchDBInteger

def test_result_processor():
    dialect = Mock(spec=Dialect)
    processor = CouchDBInteger().result_processor(dialect, 'integer')

    assert processor(123) == 123
    assert processor(None) is None
```

### 测试日期时间

```python
from sqlalchemy_couchdb.types import CouchDBDateTime
from datetime import datetime

def test_datetime_conversion():
    dialect = Mock(spec=Dialect)
    bind_processor = CouchDBDateTime().bind_processor(dialect)
    result_processor = CouchDBDateTime().result_processor(dialect, 'datetime')

    dt = datetime(2025, 1, 2, 15, 30, 0)
    json_value = bind_processor(dt)
    assert json_value == "2025-01-02T15:30:00"

    restored = result_processor(json_value)
    assert restored == dt
```

## 最佳实践

1. **始终测试转换**: 验证 bind_processor 和 result_processor
2. **使用标准类型**: 优先使用标准 SQLAlchemy 类型（自动映射）
3. **处理 None 值**: 所有类型都应正确处理 None
4. **验证数据**: 自定义类型应验证输入
5. **文档格式**: 明确说明日期时间格式（ISO 8601）

## 相关资源

- [Python JSON 数据类型](https://docs.python.org/3/library/json.html)
- [CouchDB 数据类型](https://docs.couchdb.org/en/stable/json-structure.html)
- [ISO 8601 日期时间格式](https://en.wikipedia.org/wiki/ISO_8601)

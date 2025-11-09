# 类型映射指南

## 概述

SQLAlchemy CouchDB 方言提供完整的 Python ↔ JSON 类型映射系统。所有 SQLAlchemy 类型都会自动转换为对应的 CouchDB JSON 类型，并在 Python 和 JSON 之间进行双向转换。

## 类型映射表

| SQLAlchemy 类型 | CouchDB JSON 类型 | Python 类型 | 示例 |
|----------------|-------------------|-------------|------|
| `CouchDBString` | `string` | `str` | `"Alice"` |
| `CouchDBInteger` | `number` | `int` | `30` |
| `CouchDBFloat` | `number` | `float` | `99.99` |
| `CouchDBBoolean` | `boolean` | `bool` | `true` |
| `CouchDBDateTime` | `string` (ISO 8601) | `datetime` | `"2025-01-02T15:30:00"` |
| `CouchDBDate` | `string` (ISO 8601) | `date` | `"2025-01-02"` |
| `CouchDBJSON` | `object/array` | `dict`/`list` | `{"key": "value"}` |
| `CouchDBNumeric` | `number/string` | `Decimal` | `"123.456789"` |

## 内置类型详解

### 1. CouchDBString

```python
from sqlalchemy import Column, String
from sqlalchemy_couchdb.types import CouchDBString

# 在表定义中使用
users = Table('users', metadata,
    Column('name', CouchDBString),  # 自动转换为 string
)

# Python → JSON 转换
# "Alice" → "Alice"

# JSON → Python 转换
# "Alice" → "Alice"
```

**特点**:
- 所有值自动转换为字符串
- 自动处理 None 值
- 支持 Unicode

### 2. CouchDBInteger

```python
from sqlalchemy import Column, Integer
from sqlalchemy_couchdb.types import CouchDBInteger

users = Table('users', metadata,
    Column('age', CouchDBInteger),  # 自动转换为 number
)

# Python → JSON 转换
# 30 → 30

# JSON → Python 转换
# 30 → 30
```

**特点**:
- 自动转换为整数
- 支持 None 值
- 会截断小数部分（建议使用 Float）

### 3. CouchDBFloat

```python
from sqlalchemy import Column, Float
from sqlalchemy_couchdb.types import CouchDBFloat

users = Table('users', metadata,
    Column('price', CouchDBFloat),  # 自动转换为 number
)

# Python → JSON 转换
# 99.99 → 99.99

# JSON → Python 转换
# 99.99 → 99.99
```

**特点**:
- 自动转换为浮点数
- 支持 None 值
- 注意浮点数精度问题

### 4. CouchDBBoolean

```python
from sqlalchemy import Column, Boolean
from sqlalchemy_couchdb.types import CouchDBBoolean

users = Table('users', metadata,
    Column('is_active', CouchDBBoolean),  # 自动转换为 boolean
)

# Python → JSON 转换
# True → true
# False → false

# JSON → Python 转换
# true → True
# false → False
```

**特点**:
- 自动转换为布尔值
- 支持 None 值
- 任何非零值转为 True

### 5. CouchDBDateTime

```python
from sqlalchemy import Column, DateTime
from sqlalchemy_couchdb.types import CouchDBDateTime
from datetime import datetime

users = Table('users', metadata,
    Column('created_at', CouchDBDateTime),  # ISO 8601 字符串
)

# Python → JSON 转换
# datetime(2025, 1, 2, 15, 30, 0) → "2025-01-02T15:30:00"

# JSON → Python 转换
# "2025-01-02T15:30:00" → datetime(2025, 1, 2, 15, 30, 0)
```

**特点**:
- 使用 ISO 8601 格式
- 支持时区（如果提供）
- 自动处理 None 值

**使用示例**:

```python
from datetime import datetime

# 插入带日期时间的文档
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (_id, name, created_at, type)
        VALUES (:id, :name, :created_at, 'user')
    """), {
        'id': 'user:dt-1',
        'name': 'Alice',
        'created_at': datetime(2025, 1, 2, 15, 30, 0)
    })
    conn.commit()

# 查询时会自动转换回 datetime
result = conn.execute(text("SELECT * FROM users WHERE _id = 'user:dt-1'"))
row = result.fetchone()
print(type(row.created_at))  # <class 'datetime.datetime'>
```

### 6. CouchDBDate

```python
from sqlalchemy import Column, Date
from sqlalchemy_couchdb.types import CouchDBDate
from datetime import date

users = Table('users', metadata,
    Column('birth_date', CouchDBDate),  # ISO 8601 日期字符串
)

# Python → JSON 转换
# date(2025, 1, 2) → "2025-01-02"

# JSON → Python 转换
# "2025-01-02" → date(2025, 1, 2)
```

**特点**:
- 使用 YYYY-MM-DD 格式
- 自动处理 None 值
- 不会存储时间部分

**使用示例**:

```python
from datetime import date

# 插入带日期的文档
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (_id, name, birth_date, type)
        VALUES (:id, :name, :birth_date, 'user')
    """), {
        'id': 'user:date-1',
        'name': 'Bob',
        'birth_date': date(1990, 5, 15)
    })
    conn.commit()

# 查询
result = conn.execute(text("SELECT * FROM users WHERE _id = 'user:date-1'"))
row = result.fetchone()
print(type(row.birth_date))  # <class 'datetime.date'>
```

### 7. CouchDBJSON

```python
from sqlalchemy import Column, JSON
from sqlalchemy_couchdb.types import CouchDBJSON

users = Table('users', metadata,
    Column('metadata', CouchDBJSON),  # 原生 JSON 对象
)

# Python → JSON 转换
# {"key": "value", "list": [1, 2, 3]} → {"key": "value", "list": [1, 2, 3]}

# JSON → Python 转换
# {"key": "value"} → {"key": "value"}
```

**特点**:
- CouchDB 原生支持，无需转换
- 支持嵌套对象和数组
- 灵活存储半结构化数据

**使用示例**:

```python
# 插入复杂 JSON 数据
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (_id, name, metadata, type)
        VALUES (:id, :name, :metadata, 'user')
    """), {
        'id': 'user:json-1',
        'name': 'Charlie',
        'metadata': {
            'preferences': {
                'theme': 'dark',
                'notifications': True
            },
            'tags': ['vip', 'beta'],
            'score': 95.5
        }
    })
    conn.commit()

# 查询 JSON 数据
result = conn.execute(text("SELECT metadata FROM users WHERE _id = 'user:json-1'"))
row = result.fetchone()
print(row.metadata['preferences']['theme'])  # "dark"
```

### 8. CouchDBNumeric（高精度数值）

```python
from sqlalchemy import Column, Numeric
from sqlalchemy_couchdb.types import CouchDBNumeric
from decimal import Decimal

users = Table('transactions', metadata,
    Column('amount', CouchDBNumeric(precision=10, scale=2, as_string=True)),
)

# as_string=True（默认）
# Python → JSON 转换
# Decimal("123.45") → "123.45"

# JSON → Python 转换
# "123.45" → Decimal("123.45")

# as_string=False
# Python → JSON 转换
# Decimal("123.45") → 123.45

# JSON → Python 转换
# 123.45 → 123.45（可能损失精度）
```

**特点**:
- `as_string=True`: 保持精度，存储为字符串
- `as_string=False`: 存储为数字，可能损失精度
- 推荐使用 `as_string=True` 处理货币等敏感数据

**使用示例**:

```python
from decimal import Decimal

# 使用高精度数值（推荐）
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO transactions (_id, amount, type)
        VALUES (:id, :amount, 'transaction')
    """), {
        'id': 'tx:1',
        'amount': Decimal('123.456789')  # 保持完整精度
    })
    conn.commit()

# 查询
result = conn.execute(text("SELECT amount FROM transactions WHERE _id = 'tx:1'"))
row = result.fetchone()
print(row.amount)  # Decimal('123.456789')
print(f"类型: {type(row.amount)}")  # <class 'decimal.Decimal'>
```

## 使用标准 SQLAlchemy 类型

SQLAlchemy CouchDB 方言自动将标准类型映射到自定义类型：

```python
from sqlalchemy import Table, Column, String, Integer, Float, Boolean, DateTime, Date, JSON

users = Table('users', metadata,
    Column('_id', String),           # 自动映射到 CouchDBString
    Column('name', String),
    Column('age', Integer),          # 自动映射到 CouchDBInteger
    Column('price', Float),          # 自动映射到 CouchDBFloat
    Column('is_active', Boolean),    # 自动映射到 CouchDBBoolean
    Column('created_at', DateTime),  # 自动映射到 CouchDBDateTime
    Column('birth_date', Date),      # 自动映射到 CouchDBDate
    Column('metadata', JSON),        # 自动映射到 CouchDBJSON
    Column('type', String)
)
```

## 自定义类型

您也可以扩展类型系统：

```python
from sqlalchemy import types
from sqlalchemy_couchdb.types import CouchDBString

class CouchDBEmail(CouchDBString):
    """邮件类型 - 基于字符串，但添加验证"""

    def bind_processor(self, dialect):
        def process(value):
            if value is None:
                return None
            # 添加简单的邮箱格式检查
            if '@' not in str(value):
                raise ValueError(f"无效的邮箱格式: {value}")
            return str(value)

        return process

# 使用自定义类型
users = Table('users', metadata,
    Column('email', CouchDBEmail),
)
```

## 类型推断

SQLAlchemy 会根据 Python 值的类型自动推断：

```python
from sqlalchemy import text

# SQLAlchemy 会根据值类型自动转换
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (_id, name, age, is_active, created_at, type)
        VALUES (:id, :name, :age, :is_active, :created_at, 'user')
    """), {
        'id': 'user:auto-1',
        'name': 'Alice',           # str → string
        'age': 30,                 # int → number
        'is_active': True,         # bool → boolean
        'created_at': datetime.now(),  # datetime → ISO 8601 string
    })
    conn.commit()
```

## 日期时间格式化

### ISO 8601 格式

CouchDB 使用 ISO 8601 格式存储日期时间：

```python
# 标准格式
"2025-01-02T15:30:00"
"2025-01-02T15:30:00Z"  # UTC 时区
"2025-01-02T15:30:00+08:00"  # 指定时区
```

### 时区处理

```python
from datetime import datetime, timezone
import pytz

# UTC 时间
utc_time = datetime.now(timezone.utc)

# 转换为指定时区
tokyo_tz = pytz.timezone('Asia/Tokyo')
tokyo_time = utc_time.astimezone(tokyo_tz)

# 存储到 CouchDB
with engine.connect() as conn:
    conn.execute(text("""
        INSERT INTO users (_id, created_at, type)
        VALUES (:id, :created_at, 'user')
    """), {
        'id': 'user:tz-1',
        'created_at': utc_time
    })
    conn.commit()
```

## 性能优化

### 1. 选择合适的类型

```python
# ✅ 好：使用适当精度
Column('price', CouchDBNumeric(precision=10, scale=2))

# ❌ 差：不必要的精度
Column('price', CouchDBNumeric(precision=38, scale=20))
```

### 2. 避免过度嵌套 JSON

```python
# ✅ 好：适度嵌套
metadata = {'tag': 'vip', 'score': 95}

# ❌ 差：过度嵌套（影响查询性能）
metadata = {
    'level1': {
        'level2': {
            'level3': {...}
        }
    }
}
```

### 3. 使用索引字段

```python
# 为常用查询字段创建索引（通过 ORDER BY 自动创建）
result = conn.execute(text("""
    SELECT * FROM users
    WHERE type = 'user'
    ORDER BY age  -- 自动为 age 创建索引
    LIMIT 100
"""))
```

## 常见问题

### 1. 日期时间格式不匹配

**问题**:
```python
# 插入错误格式的日期
conn.execute(text("..."), {'date': '2025/01/02'})  # 错误
```

**解决**:
```python
# 使用 datetime 对象
from datetime import datetime
conn.execute(text("..."), {'date': datetime(2025, 1, 2)})

# 或使用 ISO 8601 字符串
conn.execute(text("..."), {'date': '2025-01-02T00:00:00'})
```

### 2. 数值精度损失

**问题**:
```python
# 使用 Float 存储货币
Column('amount', Float)  # 可能损失精度
```

**解决**:
```python
# 使用 Numeric 类型
from sqlalchemy import Numeric
from sqlalchemy_couchdb.types import CouchDBNumeric

Column('amount', CouchDBNumeric(precision=10, scale=2, as_string=True))
```

### 3. JSON 字段查询

```python
# CouchDB 对嵌套 JSON 查询有限制
# ❌ 不推荐：嵌套查询
result = conn.execute(text("""
    SELECT * FROM users
    WHERE metadata->'preferences'->>'theme' = 'dark'
"""))

# ✅ 推荐：使用简单字段或视图
result = conn.execute(text("""
    SELECT * FROM users
    WHERE theme = 'dark'
"""))
```

## 下一步

- [SQL 转 Mango Query](sql-to-mango.md)
- [同步操作](sync-operations.md)
- [异步操作](async-operations.md)

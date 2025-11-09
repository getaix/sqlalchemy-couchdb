# 连接配置

## 连接 URL 格式

### Phase 1: 纯 CouchDB

```
# 同步连接
couchdb://username:password@host:port/database

# 异步连接
couchdb+async://username:password@host:port/database
```

### Phase 2: 混合模式

```
couchdb+hybrid://username:password@host:port/database?secondary_db=<RDBMS_URL>
```

## 连接参数详解

### 基本参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `username` | CouchDB 用户名 | `admin` |
| `password` | CouchDB 密码 | `password123` |
| `host` | CouchDB 主机 | `localhost` |
| `port` | CouchDB 端口 | `5984` (默认) |
| `database` | 数据库名 | `mydb` |

### 示例 URL

```python
from sqlalchemy import create_engine

# 基础连接
engine = create_engine('couchdb://localhost:5984/mydb')

# 带认证的连接
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')

# 远程连接
engine = create_engine('couchdb://user:pass@example.com:5984/production')

# 异步连接
from sqlalchemy.ext.asyncio import create_async_engine
engine = create_async_engine('couchdb+async://admin:password@localhost:5984/mydb')
```

## 连接选项

### 1. 认证方式

#### 用户名密码

```python
engine = create_engine('couchdb://admin:password@localhost:5984/mydb')
```

#### Cookie 认证

```python
engine = create_engine('couchdb://cookie:abc123@localhost:5984/mydb')
```

#### 无认证（开发环境）

```python
engine = create_engine('couchdb://localhost:5984/mydb')
```

### 2. 连接池配置

```python
from sqlalchemy import create_engine

engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    pool_size=10,          # 连接池大小
    max_overflow=20,       # 最大溢出连接
    pool_recycle=3600,     # 连接回收时间（秒）
    pool_timeout=30,       # 获取连接超时时间
    pool_pre_ping=True,    # 连接前测试
)
```

### 3. HTTP 客户端配置

```python
from sqlalchemy_couchdb.client import SyncCouchDBClient

client = SyncCouchDBClient(
    base_url='http://localhost:5984',
    username='admin',
    password='password',
    database='mydb',
    timeout=30.0,           # 请求超时时间
    verify_ssl=True,        # 是否验证 SSL 证书
    ca_cert_path=None,      # CA 证书路径
    client_cert_path=None,  # 客户端证书路径
    client_key_path=None,   # 客户端密钥路径
)
```

## Phase 2: 混合模式连接

### 配置二级数据库

```python
from sqlalchemy import create_engine

# CouchDB + PostgreSQL
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost:5432/mydb'
)

# CouchDB + MySQL
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=mysql+pymysql://user:pass@localhost:3306/mydb'
)

# CouchDB + SQLite
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=sqlite:///mydb.sqlite'
)
```

### URL 查询参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `secondary_db` | 二级数据库连接 URL | `postgresql://...` |
| `routing_strategy` | 路由策略 | `simple`, `hybrid`, `all` |
| `write_mode` | 写操作模式 | `couchdb_only`, `dual_write`, `rdbms_only` |
| `consistency_check` | 一致性检查 | `true`, `false` |
| `check_interval` | 检查间隔（秒） | `60` |

### 完整示例

```python
engine = create_engine(
    'couchdb+hybrid://admin:password@localhost:5984/mydb'
    '?secondary_db=postgresql://user:pass@localhost:5432/mydb'
    '&routing_strategy=hybrid'
    '&write_mode=dual_write'
    '&consistency_check=true'
    '&check_interval=120'
)
```

## 环境变量配置

### 使用 .env 文件

```python
import os
from sqlalchemy import create_engine

# 从环境变量读取配置
COUCHDB_HOST = os.getenv('COUCHDB_HOST', 'localhost')
COUCHDB_PORT = os.getenv('COUCHDB_PORT', '5984')
COUCHDB_USER = os.getenv('COUCHDB_USER', 'admin')
COUCHDB_PASSWORD = os.getenv('COUCHDB_PASSWORD', '')
COUCHDB_DATABASE = os.getenv('COUCHDB_DATABASE', 'mydb')

engine = create_engine(
    f'couchdb://{COUCHDB_USER}:{COUCHDB_PASSWORD}@{COUCHDB_HOST}:{COUCHDB_PORT}/{COUCHDB_DATABASE}'
)
```

### 环境变量清单

```bash
# CouchDB 配置
export COUCHDB_HOST=localhost
export COUCHDB_PORT=5984
export COUCHDB_USER=admin
export COUCHDB_PASSWORD=password
export COUCHDB_DATABASE=mydb

# Phase 2 配置
export SECONDARY_DB_URL=postgresql://user:pass@localhost:5432/mydb
export ROUTING_STRATEGY=hybrid
export WRITE_MODE=dual_write
export CONSISTENCY_CHECK=true
export CHECK_INTERVAL=120
```

## SSL/TLS 配置

### HTTPS 连接

```python
engine = create_engine(
    'couchdb://admin:password@secure-couchdb.com:6984/mydb',
    connect_args={
        'verify_ssl': True,
        'ca_cert_path': '/path/to/ca-cert.pem',
    }
)
```

### 客户端证书

```python
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    connect_args={
        'client_cert_path': '/path/to/client-cert.pem',
        'client_key_path': '/path/to/client-key.pem',
        'verify_ssl': True,
    }
)
```

## 连接测试

### 测试连接

```python
from sqlalchemy import text

def test_connection(engine):
    try:
        with engine.connect() as conn:
            # ping CouchDB
            result = conn.execute(text("SELECT 1"))
            print("✅ 连接成功")
            return True
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

# 使用
test_connection(engine)
```

### 检查数据库状态

```python
def check_database_status(engine):
    try:
        with engine.connect() as conn:
            # 获取数据库信息
            result = conn.execute(text("SELECT db_name, doc_count FROM information_schema.tables WHERE table_type='BASE TABLE'"))
            # 注意：CouchDB 使用不同的方式
            print("数据库状态正常")
    except Exception as e:
        print(f"数据库状态异常: {e}")

check_database_status(engine)
```

## 连接池监控

### 监控连接池状态

```python
from sqlalchemy.pool import StaticPool

def monitor_pool(engine):
    pool = engine.pool
    print(f"池大小: {pool.size()}")
    print(f"已检查 out 数量: {pool.checkedout()}")
    print(f"已返回数量: {pool.returned()}")

monitor_pool(engine)
```

## 常见问题

### 1. 连接超时

```python
# 增加超时时间
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    connect_args={'timeout': 60.0}
)
```

### 2. 连接池耗尽

```python
# 增加池大小
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    pool_size=20,
    max_overflow=30,
)
```

### 3. SSL 验证失败

```python
# 禁用 SSL 验证（仅开发环境）
engine = create_engine(
    'couchdb://admin:password@localhost:5984/mydb',
    connect_args={'verify_ssl': False}
)
```

## 下一步

- [同步操作](../guide/sync-operations.md)
- [异步操作](../guide/async-operations.md)
- [混合数据库模式](../guide/hybrid-mode.md)

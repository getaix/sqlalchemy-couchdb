# CouchDB Client API

## 概述

`CouchDBClient` 是 CouchDB HTTP 客户端，负责与 CouchDB API 通信。支持同步和异步操作。

## 类层次

```
CouchDBClient (基类)
├── SyncCouchDBClient (同步客户端)
└── AsyncCouchDBClient (异步客户端)
```

## CouchDBClient 基类

### 初始化

```python
class CouchDBClient:
    def __init__(
        self,
        base_url: str,
        database: str,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs
    ):
        """
        参数:
            base_url: CouchDB 基础 URL
            database: 数据库名
            username: 用户名
            password: 密码
            **kwargs: 其他 HTTP 参数
        """
```

### 主要方法

#### find()

执行 Mango Query 查询。

**签名**:
```python
def find(
    self,
    selector: dict,
    fields: Optional[List[str]] = None,
    limit: Optional[int] = None,
    skip: Optional[int] = None,
    sort: Optional[List[dict]] = None,
    **kwargs
) -> List[dict]:
    """执行 Mango Query"""
```

**参数**:
- `selector`: Mango selector 对象
- `fields`: 返回字段列表
- `limit`: 限制返回数量
- `skip`: 跳过文档数量
- `sort`: 排序字段

**返回**:
```python
[
    {
        "_id": "doc:1",
        "_rev": "1-abc123",
        "field1": "value1",
        ...
    },
    ...
]
```

**示例**:
```python
client = SyncCouchDBClient(
    base_url='http://localhost:5984',
    database='mydb',
    username='admin',
    password='password'
)

# 执行查询
results = client.find(
    selector={"type": {"$eq": "user"}},
    fields=["_id", "name", "age"],
    limit=10
)

for doc in results:
    print(f"ID: {doc['_id']}, 姓名: {doc['name']}")
```

#### bulk_docs()

批量插入/更新/删除文档。

**签名**:
```python
def bulk_docs(self, docs: List[dict]) -> List[dict]:
    """批量操作文档"""
```

**参数**:
- `docs`: 文档列表

**示例**:
```python
docs = [
    {"_id": "user:1", "name": "Alice", "age": 30, "type": "user"},
    {"_id": "user:2", "name": "Bob", "age": 25, "type": "user"},
]

results = client.bulk_docs(docs)
```

#### ensure_index()

创建索引。

**签名**:
```python
def ensure_index(
    self,
    fields: Union[str, List[str]],
    design_doc: Optional[str] = None,
    name: Optional[str] = None
) -> dict:
    """创建索引"""
```

**参数**:
- `fields`: 索引字段，可以是字符串或列表
- `design_doc`: 设计文档名
- `name`: 索引名

**示例**:
```python
# 单字段索引
client.ensure_index("age")

# 复合索引
client.ensure_index(["age", "name"])

# 自定义名称
client.ensure_index("age", name="age-index")
```

#### ping()

检查连接。

**签名**:
```python
def ping(self) -> bool:
    """检查 CouchDB 连接"""
```

**返回**: `True` 如果连接成功

**示例**:
```python
if client.ping():
    print("✅ 连接正常")
else:
    print("❌ 连接失败")
```

#### get()

获取单个文档。

**签名**:
```python
def get(self, doc_id: str, rev: Optional[str] = None) -> Optional[dict]:
    """获取文档"""
```

**参数**:
- `doc_id`: 文档 ID
- `rev`: 文档版本（可选）

**示例**:
```python
doc = client.get("user:123")
if doc:
    print(f"文档: {doc}")
else:
    print("文档不存在")
```

#### put()

插入或更新文档。

**签名**:
```python
def put(self, doc_id: str, doc: dict) -> dict:
    """插入或更新文档"""
```

**示例**:
```python
result = client.put("user:123", {
    "name": "Alice",
    "age": 30,
    "type": "user"
})
print(f"新版本: {result['rev']}")
```

#### delete()

删除文档。

**签名**:
```python
def delete(self, doc_id: str, rev: str) -> dict:
    """删除文档"""
```

**参数**:
- `doc_id`: 文档 ID
- `rev`: 文档版本

**示例**:
```python
# 先获取文档版本
doc = client.get("user:123")
if doc:
    result = client.delete("user:123", doc["_rev"])
    print("删除成功")
```

## SyncCouchDBClient

同步 CouchDB 客户端。

```python
from sqlalchemy_couchdb.client import SyncCouchDBClient

# 初始化
client = SyncCouchDBClient(
    base_url='http://localhost:5984',
    database='mydb',
    username='admin',
    password='password'
)

# 使用
client.ping()
results = client.find({"type": {"$eq": "user"}})
```

### 配置参数

```python
client = SyncCouchDBClient(
    base_url='http://localhost:5984',
    database='mydb',
    username='admin',
    password='password',
    timeout=30.0,              # 请求超时
    verify_ssl=True,           # 验证 SSL
    ca_cert_path=None,         # CA 证书
    client_cert_path=None,     # 客户端证书
    client_key_path=None,      # 客户端密钥
)
```

## AsyncCouchDBClient

异步 CouchDB 客户端。

```python
import asyncio
from sqlalchemy_couchdb.client import AsyncCouchDBClient

async def main():
    client = AsyncCouchDBClient(
        base_url='http://localhost:5984',
        database='mydb',
        username='admin',
        password='password'
    )

    # 异步操作
    await client.ping()
    results = await client.find({"type": {"$eq": "user"}})

    # 关闭
    await client.close()

asyncio.run(main())
```

### 特殊方法

#### aclose()

异步关闭客户端。

**签名**:
```python
async def aclose(self):
    """异步关闭客户端"""
```

**使用**:
```python
client = AsyncCouchDBClient(...)
try:
    await client.find(...)
finally:
    await client.aclose()
```

#### __aenter__ / __aexit__

异步上下文管理器。

```python
async def main():
    async with AsyncCouchDBClient(...) as client:
        await client.ping()
        results = await client.find(...)
```

## 使用示例

### 基本 CRUD

```python
from sqlalchemy_couchdb.client import SyncCouchDBClient

client = SyncCouchDBClient(
    base_url='http://localhost:5984',
    database='mydb'
)

# CREATE
doc = {"_id": "user:1", "name": "Alice", "age": 30, "type": "user"}
result = client.put("user:1", doc)
print(f"插入成功: {result}")

# READ
doc = client.get("user:1")
print(f"读取: {doc}")

# UPDATE
doc["age"] = 31
result = client.put("user:1", doc)
print(f"更新成功: {result}")

# DELETE
result = client.delete("user:1", doc["_rev"])
print(f"删除成功: {result}")
```

### 高级查询

```python
# 复杂条件查询
results = client.find({
    "selector": {
        "type": {"$eq": "user"},
        "$and": [
            {"age": {"$gte": 25}},
            {"age": {"$lte": 35}},
            {"name": {"$regex": "^A"}}
        ]
    },
    "fields": ["_id", "name", "age"],
    "sort": [{"age": "desc"}],
    "limit": 10
})

for doc in results:
    print(f"{doc['name']}: {doc['age']} 岁")
```

### 索引管理

```python
# 列出所有索引
indexes = client.list_indexes()
print(f"现有索引: {indexes}")

# 创建复合索引
client.ensure_index(
    fields=["type", "age"],
    name="type-age-index"
)

# 创建部分索引
# 注意：需要手动创建，查看 CouchDB 文档
```

### 批量操作

```python
# 批量插入
docs = [
    {"_id": f"user:{i}", "name": f"User{i}", "age": i, "type": "user"}
    for i in range(100)
]

results = client.bulk_docs(docs)
print(f"批量插入 {len(results)} 个文档")

# 批量更新（需要先查询获取 _rev）
docs_to_update = []
for result in results:
    if result.get('ok'):
        # 获取文档
        doc = client.get(result['id'])
        doc['age'] += 1
        doc['_rev'] = result['rev']
        docs_to_update.append(doc)

# 更新
updated = client.bulk_docs(docs_to_update)
```

### 分页查询

```python
# 使用 LIMIT 和 SKIP
page_size = 10
page_num = 1
skip = (page_num - 1) * page_size

results = client.find({
    "selector": {"type": {"$eq": "user"}},
    "limit": page_size,
    "skip": skip,
    "sort": [{"_id": "asc"}]
})

# 高效分页：使用 startkey
if results:
    last_key = results[-1]["_id"]
    next_results = client.find({
        "selector": {"type": {"$eq": "user"}},
        "limit": page_size,
        "startkey": last_key
    })
```

## 错误处理

### 捕获异常

```python
from sqlalchemy_couchdb.exceptions import (
    CouchDBError,
    DocumentConflict,
    NotFoundError
)

try:
    doc = client.get("nonexistent")
except NotFoundError:
    print("文档不存在")
except DocumentConflict:
    print("文档版本冲突")
except CouchDBError as e:
    print(f"CouchDB 错误: {e}")
```

### 重试机制

```python
from functools import wraps

def retry(max_attempts=3, delay=0.1):
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(self, *args, **kwargs)
                except DocumentConflict:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(delay)
            return None
        return wrapper
    return decorator

class SyncCouchDBClient(SyncCouchDBClient):
    @retry(max_attempts=3)
    def update_with_retry(self, doc_id, update_func):
        doc = self.get(doc_id)
        if doc:
            doc = update_func(doc)
            return self.put(doc_id, doc)
        return None
```

## 性能优化

### 连接池

```python
# httpx 客户端配置
client = SyncCouchDBClient(
    base_url='http://localhost:5984',
    database='mydb',
    # httpx 参数
    limits=httpx.Limits(
        max_keepalive_connections=5,
        max_connections=10
    )
)
```

### 缓存

```python
from functools import lru_cache

class CachedCouchDBClient(SyncCouchDBClient):
    @lru_cache(maxsize=128)
    def get_cached(self, doc_id):
        """缓存 get 操作"""
        return super().get(doc_id)

    def invalidate_cache(self, doc_id):
        """失效缓存"""
        self.get_cached.cache_clear()
```

### 批量操作优化

```python
# 分批处理大量数据
batch_size = 100
docs = [...]  # 大量文档

for i in range(0, len(docs), batch_size):
    batch = docs[i:i + batch_size]
    results = client.bulk_docs(batch)
    print(f"处理批次 {i // batch_size + 1}")
```

## 相关资源

- [CouchDB HTTP API](https://docs.couchdb.org/en/stable/api/)
- [Mango Query](https://docs.couchdb.org/en/stable/api/database/find.html)
- [httpx 文档](https://www.python-httpx.org/)

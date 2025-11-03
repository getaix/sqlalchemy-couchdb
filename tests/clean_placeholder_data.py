"""
清理数据库中的占位符数据
"""

import httpx

# 查找所有占位符数据
response = httpx.post(
    "http://admin:123456@localhost:5984/test_db/_find", json={"selector": {"name": ":name"}}
)

data = response.json()
print(f"找到 {len(data['docs'])} 条占位符记录")

# 删除它们
deleted_count = 0
for doc in data["docs"]:
    response = httpx.delete(
        f"http://admin:123456@localhost:5984/test_db/{doc['_id']}?rev={doc['_rev']}"
    )
    if response.status_code == 200:
        deleted_count += 1

print(f"删除了 {deleted_count} 条记录")

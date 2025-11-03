"""
查看数据库中所有 users 的 age 类型
"""

import httpx

response = httpx.post(
    "http://admin:123456@localhost:5984/test_db/_find",
    json={"selector": {"type": "users"}, "limit": 100},
)

data = response.json()
print(f"找到 {len(data['docs'])} 条 users 记录:")
for doc in data["docs"]:
    age = doc.get("age")
    print(f"  name: {doc.get('name')}, age: {age!r} (type: {type(age).__name__})")

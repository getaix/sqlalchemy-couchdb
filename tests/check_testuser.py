"""
直接查看数据库中的 TestUser 记录
"""

import httpx

response = httpx.post(
    "http://admin:123456@localhost:5984/test_db/_find",
    json={
        "selector": {"$or": [{"name": "TestUser1"}, {"name": "TestUser2"}, {"name": "TestUser3"}]}
    },
)

data = response.json()
print(f"找到 {len(data['docs'])} 条记录:")
for doc in data["docs"]:
    print(f"  {doc}")

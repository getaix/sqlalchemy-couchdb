"""
检查 CouchDB 中的数据类型
"""

from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, select

CONNECTION_URL = "couchdb://admin:123456@localhost:5984/test_db"

engine = create_engine(CONNECTION_URL)

metadata = MetaData()
users = Table(
    "users",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("name", String(50)),
    Column("age", Integer),
    Column("email", String(100)),
)

with engine.connect() as conn:
    stmt = select(users).where(users.c.name == "Alice")
    result = conn.execute(stmt)
    row = result.fetchone()

    if row:
        print("找到 Alice:")
        print(f"  name: {row.name!r} (type: {type(row.name).__name__})")
        print(f"  age: {row.age!r} (type: {type(row.age).__name__})")
        print(f"  email: {row.email!r} (type: {type(row.email).__name__})")
    else:
        print("未找到 Alice 记录")

engine.dispose()

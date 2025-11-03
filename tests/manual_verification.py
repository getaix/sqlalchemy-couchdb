"""
全面功能验证脚本

测试 SQLAlchemy CouchDB Dialect 的所有核心功能。
"""

import sys
from datetime import datetime, date

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Date,
    Text,
    JSON as SQLJSON,
    select,
    insert,
    update,
    delete,
    and_,
    or_,
)

# 测试配置
TEST_CONFIG = {
    "host": "localhost",
    "port": 5984,
    "username": "admin",
    "password": "123456",
    "database": "test_db",
}

# 构建连接 URL
CONNECTION_URL = (
    f"couchdb://{TEST_CONFIG['username']}:{TEST_CONFIG['password']}"
    f"@{TEST_CONFIG['host']}:{TEST_CONFIG['port']}/{TEST_CONFIG['database']}"
)

print("=" * 80)
print("SQLAlchemy CouchDB Dialect - 全面功能验证")
print("=" * 80)
print(f"\n连接配置: {CONNECTION_URL}\n")

# 创建引擎
try:
    engine = create_engine(CONNECTION_URL, echo=False)
    print("✓ 引擎创建成功")
except Exception as e:
    print(f"✗ 引擎创建失败: {e}")
    sys.exit(1)


# 定义测试表
metadata = MetaData()

users = Table(
    "users",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("name", String(50)),
    Column("age", Integer),
    Column("email", String(100)),
    Column("salary", Float),
    Column("is_active", Boolean),
    Column("bio", Text),
)

products = Table(
    "products",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("title", String(100)),
    Column("price", Float),
    Column("quantity", Integer),
    Column("created_at", DateTime),
    Column("available", Boolean),
)

events = Table(
    "events",
    metadata,
    Column("_id", String, primary_key=True),
    Column("_rev", String),
    Column("name", String(100)),
    Column("event_date", Date),
    Column("metadata", SQLJSON),
)

print("✓ 表结构定义完成")


# ==================== 测试函数 ====================


def test_connection():
    """测试 1: 数据库连接"""
    print("\n" + "=" * 80)
    print("测试 1: 数据库连接")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            cursor = conn.connection.cursor()
            cursor.execute("PING")
            cursor.close()
            print("✓ 连接测试成功")
            return True
    except Exception as e:
        print(f"✗ 连接测试失败: {e}")
        return False


def test_insert_basic():
    """测试 2: 基本插入操作"""
    print("\n" + "=" * 80)
    print("测试 2: 基本插入操作")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # 清理旧数据
            try:
                stmt = delete(users)
                conn.execute(stmt)
                conn.commit()
            except:
                pass

            # 插入单条
            stmt = insert(users).values(
                name="Alice", age=30, email="alice@example.com", is_active=True
            )
            result = conn.execute(stmt)
            conn.commit()

            print(f"✓ 单条插入成功，影响行数: {result.rowcount}")

            # 批量插入 - 使用单独的insert语句
            test_data = [
                {
                    "name": "Bob",
                    "age": 25,
                    "email": "bob@example.com",
                    "salary": 50000.0,
                    "is_active": True,
                    "bio": None,
                },
                {
                    "name": "Carol",
                    "age": 35,
                    "email": "carol@example.com",
                    "salary": 75000.0,
                    "is_active": True,
                    "bio": None,
                },
                {
                    "name": "Dave",
                    "age": 28,
                    "email": "dave@example.com",
                    "salary": 60000.0,
                    "is_active": False,
                    "bio": None,
                },
                {
                    "name": "Eve",
                    "age": 32,
                    "email": "eve@example.com",
                    "salary": 65000.0,
                    "is_active": True,
                    "bio": "长文本测试" * 100,
                },
            ]

            for data in test_data:
                stmt = insert(users).values(**data)
                conn.execute(stmt)
            conn.commit()

            print("✓ 批量插入成功")
            return True

    except Exception as e:
        print(f"✗ 插入测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_select_basic():
    """测试 3: 基本查询操作"""
    print("\n" + "=" * 80)
    print("测试 3: 基本查询操作")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # 查询所有
            stmt = select(users)
            result = conn.execute(stmt)
            rows = result.fetchall()

            print(f"✓ 查询所有用户，返回 {len(rows)} 行")

            if len(rows) > 0:
                print(f"  示例数据: {rows[0].name}, {rows[0].age}岁")

            # 查询特定字段
            stmt = select(users.c.name, users.c.age)
            result = conn.execute(stmt)
            rows = result.fetchall()

            print(f"✓ 查询特定字段，返回 {len(rows)} 行")

            return True

    except Exception as e:
        print(f"✗ 基本查询失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_where_conditions():
    """测试 4: WHERE 条件"""
    print("\n" + "=" * 80)
    print("测试 4: WHERE 条件测试")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # 测试 = 操作符
            stmt = select(users).where(users.c.name == "Alice")
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE name = 'Alice': {len(rows)} 行")

            # 测试 > 操作符
            stmt = select(users).where(users.c.age > 30)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE age > 30: {len(rows)} 行")

            # 测试 < 操作符
            stmt = select(users).where(users.c.age < 30)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE age < 30: {len(rows)} 行")

            # 测试 >= 操作符
            stmt = select(users).where(users.c.age >= 30)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE age >= 30: {len(rows)} 行")

            # 测试 <= 操作符
            stmt = select(users).where(users.c.age <= 30)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE age <= 30: {len(rows)} 行")

            # 测试 != 操作符
            stmt = select(users).where(users.c.age != 30)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE age != 30: {len(rows)} 行")

            # 测试 IN 操作符
            stmt = select(users).where(users.c.age.in_([25, 30, 35]))
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE age IN (25, 30, 35): {len(rows)} 行")

            # 测试 LIKE 操作符
            stmt = select(users).where(users.c.name.like("A%"))
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE name LIKE 'A%': {len(rows)} 行")

            return True

    except Exception as e:
        print(f"✗ WHERE 条件测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_logical_operators():
    """测试 5: 逻辑操作符"""
    print("\n" + "=" * 80)
    print("测试 5: 逻辑操作符 (AND/OR)")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # 测试 AND
            stmt = select(users).where(and_(users.c.age > 25, users.c.age < 35))
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE age > 25 AND age < 35: {len(rows)} 行")

            # 测试 OR
            stmt = select(users).where(or_(users.c.age < 26, users.c.age > 34))
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ WHERE age < 26 OR age > 34: {len(rows)} 行")

            # 测试复杂条件
            stmt = select(users).where(
                and_(users.c.age >= 25, or_(users.c.name == "Bob", users.c.name == "Carol"))
            )
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ 复杂 AND/OR 组合: {len(rows)} 行")

            return True

    except Exception as e:
        print(f"✗ 逻辑操作符测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_order_by():
    """测试 6: 排序"""
    print("\n" + "=" * 80)
    print("测试 6: ORDER BY 排序")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # 升序
            stmt = select(users).order_by(users.c.age.asc())
            result = conn.execute(stmt)
            rows = result.fetchall()
            ages = [row.age for row in rows]
            print(f"✓ ORDER BY age ASC: {ages}")
            assert ages == sorted(ages), "升序排序失败"

            # 降序
            stmt = select(users).order_by(users.c.age.desc())
            result = conn.execute(stmt)
            rows = result.fetchall()
            ages = [row.age for row in rows]
            print(f"✓ ORDER BY age DESC: {ages}")
            assert ages == sorted(ages, reverse=True), "降序排序失败"

            return True

    except Exception as e:
        print(f"✗ 排序测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_limit_offset():
    """测试 7: 分页"""
    print("\n" + "=" * 80)
    print("测试 7: LIMIT/OFFSET 分页")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # LIMIT
            stmt = select(users).limit(2)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ LIMIT 2: 返回 {len(rows)} 行")
            assert len(rows) <= 2, "LIMIT 失败"

            # OFFSET
            stmt = select(users).offset(2)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ OFFSET 2: 返回 {len(rows)} 行")

            # LIMIT + OFFSET
            stmt = select(users).limit(2).offset(1)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ LIMIT 2 OFFSET 1: 返回 {len(rows)} 行")
            assert len(rows) <= 2, "LIMIT + OFFSET 失败"

            return True

    except Exception as e:
        print(f"✗ 分页测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_update():
    """测试 8: 更新操作"""
    print("\n" + "=" * 80)
    print("测试 8: UPDATE 更新操作")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # 更新单个字段
            stmt = update(users).where(users.c.name == "Alice").values(age=31)
            result = conn.execute(stmt)
            conn.commit()

            print(f"✓ 更新单个字段，影响行数: {result.rowcount}")

            # 验证更新
            stmt = select(users).where(users.c.name == "Alice")
            result = conn.execute(stmt)
            row = result.fetchone()
            assert row.age == 31, f"更新验证失败: 期望 31, 实际 {row.age}"
            print(f"✓ 更新验证成功: age = {row.age}")

            # 更新多个字段
            stmt = (
                update(users)
                .where(users.c.name == "Bob")
                .values(age=26, email="bob.new@example.com")
            )
            result = conn.execute(stmt)
            conn.commit()

            print(f"✓ 更新多个字段，影响行数: {result.rowcount}")

            return True

    except Exception as e:
        print(f"✗ 更新测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_delete():
    """测试 9: 删除操作"""
    print("\n" + "=" * 80)
    print("测试 9: DELETE 删除操作")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # 先清理可能存在的 ToDelete 记录
            try:
                stmt = delete(users).where(users.c.name == "ToDelete")
                conn.execute(stmt)
                conn.commit()
            except:
                pass

            # 插入测试数据
            stmt = insert(users).values(name="ToDelete", age=20, email="delete@example.com")
            conn.execute(stmt)
            conn.commit()

            # 删除
            stmt = delete(users).where(users.c.name == "ToDelete")
            result = conn.execute(stmt)
            conn.commit()

            print(f"✓ 删除操作，影响行数: {result.rowcount}")

            # 验证删除
            stmt = select(users).where(users.c.name == "ToDelete")
            result = conn.execute(stmt)
            rows = result.fetchall()
            if rows:
                print(f"✗ 删除验证失败: 仍然找到 {len(rows)} 行")
                for row in rows:
                    print(f"  {row}")
                raise AssertionError("删除验证失败")
            print("✓ 删除验证成功")

            return True

    except Exception as e:
        print(f"✗ 删除测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_types():
    """测试 10: 类型系统"""
    print("\n" + "=" * 80)
    print("测试 10: 类型系统")
    print("=" * 80)

    try:
        with engine.connect() as conn:
            # 清理旧数据
            try:
                stmt = delete(products)
                conn.execute(stmt)
                conn.commit()

                stmt = delete(events)
                conn.execute(stmt)
                conn.commit()
            except:
                pass

            # 测试 DateTime
            now = datetime.now()
            stmt = insert(products).values(
                title="Product 1",
                price=99.99,
                quantity=10,
                created_at=now,
                available=True,
            )
            conn.execute(stmt)
            conn.commit()

            stmt = select(products).where(products.c.title == "Product 1")
            result = conn.execute(stmt)
            row = result.fetchone()
            print(f"✓ DateTime 类型: {row.created_at}")

            # 测试 Date
            today = date.today()
            stmt = insert(events).values(
                name="Event 1",
                event_date=today,
                metadata={"key": "value", "number": 123},
            )
            conn.execute(stmt)
            conn.commit()

            stmt = select(events).where(events.c.name == "Event 1")
            result = conn.execute(stmt)
            row = result.fetchone()
            print(f"✓ Date 类型: {row.event_date}")
            print(f"✓ JSON 类型: {row.metadata}")

            # 测试 Boolean
            stmt = select(products).where(products.c.available == True)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ Boolean 类型查询: {len(rows)} 行")

            # 测试 Float
            stmt = select(products).where(products.c.price > 50.0)
            result = conn.execute(stmt)
            rows = result.fetchall()
            print(f"✓ Float 类型查询: {len(rows)} 行")

            return True

    except Exception as e:
        print(f"✗ 类型测试失败: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_error_handling():
    """测试 11: 错误处理"""
    print("\n" + "=" * 80)
    print("测试 11: 错误处理")
    print("=" * 80)


    # 测试连接错误
    try:
        bad_engine = create_engine("couchdb://admin:wrongpass@localhost:5984/test_db")
        with bad_engine.connect() as conn:
            stmt = select(users)
            conn.execute(stmt)
        print("✗ 应该抛出错误但没有")
        return False
    except Exception as e:
        print(f"✓ 捕获连接错误: {type(e).__name__}")

    # 测试无效操作
    try:
        with engine.connect() as conn:
            # 使用原始 SQL（不支持）
            from sqlalchemy import text

            conn.execute(text("INVALID SQL SYNTAX"))
        print("✗ 应该抛出错误但没有")
        return False
    except Exception as e:
        print(f"✓ 捕获编程错误: {type(e).__name__}")

    return True


# ==================== 运行所有测试 ====================


def run_all_tests():
    """运行所有测试"""
    tests = [
        test_connection,
        test_insert_basic,
        test_select_basic,
        test_where_conditions,
        test_logical_operators,
        test_order_by,
        test_limit_offset,
        test_update,
        test_delete,
        test_types,
        test_error_handling,
    ]

    results = []
    passed = 0
    failed = 0

    for test in tests:
        try:
            result = test()
            results.append((test.__doc__.split(":")[1].strip(), result))
            if result:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n✗ 测试异常: {e}")
            import traceback

            traceback.print_exc()
            results.append((test.__doc__.split(":")[1].strip(), False))
            failed += 1

    # 打印汇总
    print("\n" + "=" * 80)
    print("测试汇总")
    print("=" * 80)

    for test_name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{status}: {test_name}")

    print("\n" + "=" * 80)
    print(f"总计: {len(tests)} 个测试")
    print(f"通过: {passed} 个")
    print(f"失败: {failed} 个")
    print(f"成功率: {passed / len(tests) * 100:.1f}%")
    print("=" * 80)

    # 清理
    engine.dispose()

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

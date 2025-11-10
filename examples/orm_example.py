"""
CouchDB ORM 使用示例

演示如何使用 SQLAlchemy CouchDB 的 ORM 功能：
1. 定义模型（Declarative Base）
2. 创建关系（Relationship）
3. 使用 Session 进行 CRUD 操作
4. 查询和过滤
"""

from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy_couchdb.orm import declarative_base, relationship, sessionmaker
from datetime import datetime


# ============================================================================
# 1. 定义模型
# ============================================================================

# 创建声明式基类
Base = declarative_base()


class User(Base):
    """用户模型"""

    __tablename__ = "users"

    # 列定义
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True)
    age = Column(Integer)
    created_at = Column(DateTime, default=datetime.now)

    # 关系定义：一个用户有多个帖子
    posts = relationship("Post", back_populates="author")

    def __repr__(self):
        return f"<User(id={self.id}, name={self.name}, email={self.email})>"


class Post(Base):
    """帖子模型"""

    __tablename__ = "posts"

    # 列定义
    id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(String)
    # 注意：CouchDB 不支持传统外键约束
    # 关系通过文档引用（字段值）实现
    author_id = Column(String)  # 存储用户ID的引用
    created_at = Column(DateTime, default=datetime.now)

    # 关系定义：一个帖子属于一个用户
    author = relationship("User", back_populates="posts")

    def __repr__(self):
        return f"<Post(id={self.id}, title={self.title})>"


# ============================================================================
# 2. 创建引擎和 Session
# ============================================================================


def create_session():
    """创建 Session"""
    # 创建 CouchDB 引擎
    engine = create_engine("couchdb://admin:password@localhost:5984/mydb")

    # 创建 Session 工厂
    SessionFactory = sessionmaker(engine)

    # 创建 Session 实例
    session = SessionFactory()

    return session


# ============================================================================
# 3. CRUD 操作示例
# ============================================================================


def example_create():
    """创建记录示例"""
    print("\n=== 创建记录 ===")

    session = create_session()

    # 创建用户
    user = User(id="user1", name="Alice", email="alice@example.com", age=30)

    # 添加到 Session
    session.add(user)

    # 提交（保存到 CouchDB）
    session.commit()

    print(f"Created: {user}")

    session.close()


def example_create_with_relationship():
    """创建带关系的记录"""
    print("\n=== 创建带关系的记录 ===")

    session = create_session()

    # 创建用户
    user = User(id="user2", name="Bob", email="bob@example.com", age=25)

    # 创建帖子
    post1 = Post(
        id="post1", title="First Post", content="Hello World!", author=user  # 通过关系设置作者
    )

    post2 = Post(id="post2", title="Second Post", content="CouchDB is awesome!", author=user)

    # 添加到 Session
    session.add(user)
    session.add_all([post1, post2])

    # 提交
    session.commit()

    print(f"Created user with {len(user.posts)} posts")

    session.close()


def example_query():
    """查询示例"""
    print("\n=== 查询记录 ===")

    session = create_session()

    # 查询所有用户
    users = session.query(User).all()
    print(f"All users: {users}")

    # 条件查询
    alice = session.query(User).filter(User.name == "Alice").first()
    print(f"Found user: {alice}")

    # 按年龄过滤
    young_users = session.query(User).filter(User.age < 30).all()
    print(f"Users under 30: {young_users}")

    # 使用 filter_by（关键字参数形式）
    user = session.query(User).filter_by(email="alice@example.com").first()
    print(f"User by email: {user}")

    # 排序
    users_sorted = session.query(User).order_by(User.age.desc()).all()
    print(f"Users sorted by age: {users_sorted}")

    # 分页
    users_page1 = session.query(User).limit(10).offset(0).all()
    print(f"Page 1: {users_page1}")

    # 计数
    user_count = session.query(User).count()
    print(f"Total users: {user_count}")

    session.close()


def example_update():
    """更新记录示例"""
    print("\n=== 更新记录 ===")

    session = create_session()

    # 查询用户
    user = session.query(User).filter(User.name == "Alice").first()

    if user:
        # 修改属性
        user.name = "Alice Smith"
        user.age = 31

        # 提交（自动检测修改并更新）
        session.commit()

        print(f"Updated: {user}")
    else:
        print("User not found")

    session.close()


def example_delete():
    """删除记录示例"""
    print("\n=== 删除记录 ===")

    session = create_session()

    # 查询用户
    user = session.query(User).filter(User.name == "Bob").first()

    if user:
        # 删除
        session.delete(user)

        # 提交
        session.commit()

        print(f"Deleted: {user}")
    else:
        print("User not found")

    session.close()


# ============================================================================
# 4. 关系访问示例
# ============================================================================


def example_access_relationship():
    """访问关系示例"""
    print("\n=== 访问关系 ===")

    session = create_session()

    # 查询用户
    user = session.query(User).filter(User.name == "Alice").first()

    if user:
        # 访问用户的帖子（通过关系）
        print(f"User {user.name} has {len(user.posts)} posts:")
        for post in user.posts:
            print(f"  - {post.title}")

    # 查询帖子
    post = session.query(Post).filter(Post.title == "First Post").first()

    if post:
        # 访问帖子的作者（通过关系）
        print(f"Post '{post.title}' by {post.author.name}")

    session.close()


# ============================================================================
# 5. 事务示例
# ============================================================================


def example_transaction():
    """事务示例"""
    print("\n=== 事务操作 ===")

    session = create_session()

    try:
        # 创建多个对象
        user1 = User(id="user3", name="Charlie", email="charlie@example.com", age=35)
        user2 = User(id="user4", name="David", email="david@example.com", age=40)

        session.add_all([user1, user2])

        # 模拟错误
        # raise Exception("Something went wrong!")

        # 提交
        session.commit()

        print("Transaction committed successfully")

    except Exception as e:
        # 回滚
        session.rollback()
        print(f"Transaction rolled back: {e}")

    finally:
        session.close()


# ============================================================================
# 6. Session 状态管理示例
# ============================================================================


def example_session_states():
    """Session 状态管理示例"""
    print("\n=== Session 状态管理 ===")

    session = create_session()

    # 1. Transient 状态（临时状态）
    user = User(id="user5", name="Eve", email="eve@example.com", age=28)
    print(f"Transient: {user} (not in session)")

    # 2. Pending 状态（待保存状态）
    session.add(user)
    print(f"Pending: {user} (added to session, not saved)")

    # 3. Persistent 状态（持久化状态）
    session.commit()
    print(f"Persistent: {user} (saved to database)")

    # 4. Detached 状态（分离状态）
    session.expunge(user)
    print(f"Detached: {user} (removed from session)")

    session.close()


# ============================================================================
# 7. Identity Map 示例
# ============================================================================


def example_identity_map():
    """Identity Map 示例"""
    print("\n=== Identity Map (一级缓存) ===")

    session = create_session()

    # 第一次查询
    user1 = session.query(User).filter(User.id == "user1").first()
    print(f"First query: {user1}")

    # 第二次查询同一个对象（从 Identity Map 获取，不会再次查询数据库）
    user2 = session.query(User).filter(User.id == "user1").first()
    print(f"Second query: {user2}")

    # 验证是同一个对象
    print(f"Same object: {user1 is user2}")

    session.close()


# ============================================================================
# 8. 刷新对象示例
# ============================================================================


def example_refresh():
    """刷新对象示例"""
    print("\n=== 刷新对象 ===")

    session = create_session()

    # 查询用户
    user = session.query(User).filter(User.name == "Alice").first()

    if user:
        print(f"Before refresh: {user.name}, age={user.age}")

        # 假设数据库中的数据被外部修改了
        # 刷新对象（从数据库重新加载）
        session.refresh(user)

        print(f"After refresh: {user.name}, age={user.age}")

    session.close()


# ============================================================================
# 主函数
# ============================================================================


def main():
    """运行所有示例"""
    print("=" * 80)
    print("CouchDB ORM Examples")
    print("=" * 80)

    # 注意：这些示例需要运行的 CouchDB 实例
    # 如果没有 CouchDB，示例将无法正常工作

    # CRUD 操作
    # example_create()
    # example_create_with_relationship()
    # example_query()
    # example_update()
    # example_delete()

    # 关系访问
    # example_access_relationship()

    # 事务
    # example_transaction()

    # Session 状态
    # example_session_states()

    # Identity Map
    # example_identity_map()

    # 刷新对象
    # example_refresh()

    print("\n" + "=" * 80)
    print("ORM 功能已实现，但需要连接到实际的 CouchDB 实例才能运行")
    print("=" * 80)


if __name__ == "__main__":
    main()

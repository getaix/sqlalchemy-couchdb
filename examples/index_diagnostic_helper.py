#!/usr/bin/env python3
"""
索引诊断和修复助手

用于诊断和解决 CouchDB 索引相关问题，特别是 no_usable_index 错误。

功能:
1. 分析查询的索引需求
2. 检查现有索引
3. 自动创建缺失的索引
4. 提供索引优化建议
"""

import asyncio
import json
from typing import Optional, Dict, Any, List
from sqlalchemy import create_engine, select, Column, String, DateTime, Integer
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy_couchdb.orm import declarative_base
from datetime import datetime


# ============================================================================
# 1. 模型定义示例 (根据你的实际模型调整)
# ============================================================================

Base = declarative_base()


class AuditLog(Base):
    """审计日志模型"""

    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    log_type = Column(String)  # "operation" 或 "login"
    tenant_id = Column(String)
    create_time = Column(DateTime)
    user_id = Column(String)
    action = Column(String)
    resource = Column(String)

    def __repr__(self):
        return f"<AuditLog(id={self.id}, log_type={self.log_type}, create_time={self.create_time})>"


# ============================================================================
# 2. 同步版本的索引诊断工具
# ============================================================================

def get_client_from_session(session: Session):
    """从同步 Session 获取 CouchDB Client"""
    # 获取底层 DBAPI 连接
    dbapi_conn = session.connection().connection
    return dbapi_conn.client


def diagnose_and_fix_index(
    session: Session,
    query_stmt,
    auto_create: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    诊断查询的索引问题并可选地自动修复

    参数:
        session: SQLAlchemy Session
        query_stmt: SQLAlchemy 查询语句
        auto_create: 是否自动创建缺失的索引
        verbose: 是否打印详细信息

    返回:
        诊断结果字典
    """
    client = get_client_from_session(session)

    try:
        # 尝试执行查询看是否报错
        result = session.execute(query_stmt).scalars().all()

        if verbose:
            print("✅ 查询成功执行")
            print(f"返回 {len(result)} 条记录")

        return {
            "status": "success",
            "index_issue": False,
            "result_count": len(result)
        }

    except Exception as e:
        error_msg = str(e)

        if "no_usable_index" in error_msg.lower():
            if verbose:
                print("⚠️  检测到索引缺失问题")
                print(f"错误信息: {error_msg}")

            # 分析索引需求
            analysis = client.analyze_query_index_needs(
                query_stmt,
                session=session
            )

            if verbose:
                print("\n📊 索引分析结果:")
                print(json.dumps(analysis, indent=2, ensure_ascii=False))

            # 自动创建索引
            if auto_create and "recommendations" in analysis:
                if verbose:
                    print("\n🔧 开始自动创建索引...")

                for rec in analysis["recommendations"]:
                    fields = rec.get("fields", [])
                    index_name = rec.get("name", "auto_generated_index")

                    try:
                        client.ensure_index(
                            fields=fields,
                            name=index_name
                        )

                        if verbose:
                            print(f"✅ 成功创建索引: {index_name}")
                            print(f"   字段: {fields}")

                    except Exception as idx_error:
                        if verbose:
                            print(f"❌ 创建索引失败: {idx_error}")

                # 重试查询
                try:
                    result = session.execute(query_stmt).scalars().all()
                    if verbose:
                        print(f"\n✅ 索引创建后查询成功")
                        print(f"返回 {len(result)} 条记录")

                    return {
                        "status": "fixed",
                        "index_issue": True,
                        "auto_fixed": True,
                        "result_count": len(result),
                        "analysis": analysis
                    }
                except Exception as retry_error:
                    if verbose:
                        print(f"❌ 索引创建后查询仍失败: {retry_error}")

                    return {
                        "status": "error",
                        "index_issue": True,
                        "auto_fixed": False,
                        "error": str(retry_error),
                        "analysis": analysis
                    }

            return {
                "status": "error",
                "index_issue": True,
                "auto_fixed": False,
                "error": error_msg,
                "analysis": analysis
            }

        else:
            # 其他类型的错误
            if verbose:
                print(f"❌ 查询失败 (非索引问题): {error_msg}")

            return {
                "status": "error",
                "index_issue": False,
                "error": error_msg
            }


# ============================================================================
# 3. 异步版本的索引诊断工具
# ============================================================================

async def get_client_from_async_session(session: AsyncSession):
    """从异步 Session 获取 CouchDB Client"""
    # 获取底层连接
    conn = await session.connection()
    raw_conn = await conn.get_raw_connection()
    return raw_conn.driver_connection.client


async def diagnose_and_fix_index_async(
    session: AsyncSession,
    query_stmt,
    auto_create: bool = True,
    verbose: bool = True
) -> Dict[str, Any]:
    """
    异步诊断查询的索引问题并可选地自动修复

    参数:
        session: SQLAlchemy AsyncSession
        query_stmt: SQLAlchemy 查询语句
        auto_create: 是否自动创建缺失的索引
        verbose: 是否打印详细信息

    返回:
        诊断结果字典
    """
    client = await get_client_from_async_session(session)

    try:
        # 尝试执行查询看是否报错
        result = await session.execute(query_stmt)
        result_list = result.scalars().all()

        if verbose:
            print("✅ 查询成功执行")
            print(f"返回 {len(result_list)} 条记录")

        return {
            "status": "success",
            "index_issue": False,
            "result_count": len(result_list)
        }

    except Exception as e:
        error_msg = str(e)

        if "no_usable_index" in error_msg.lower():
            if verbose:
                print("⚠️  检测到索引缺失问题")
                print(f"错误信息: {error_msg}")

            # 分析索引需求
            analysis = await client.analyze_query_index_needs(
                query_stmt,
                session=session
            )

            if verbose:
                print("\n📊 索引分析结果:")
                print(json.dumps(analysis, indent=2, ensure_ascii=False))

            # 自动创建索引
            if auto_create and "recommendations" in analysis:
                if verbose:
                    print("\n🔧 开始自动创建索引...")

                for rec in analysis["recommendations"]:
                    fields = rec.get("fields", [])
                    index_name = rec.get("name", "auto_generated_index")

                    try:
                        await client.ensure_index(
                            fields=fields,
                            name=index_name
                        )

                        if verbose:
                            print(f"✅ 成功创建索引: {index_name}")
                            print(f"   字段: {fields}")

                    except Exception as idx_error:
                        if verbose:
                            print(f"❌ 创建索引失败: {idx_error}")

                # 重试查询
                try:
                    result = await session.execute(query_stmt)
                    result_list = result.scalars().all()

                    if verbose:
                        print(f"\n✅ 索引创建后查询成功")
                        print(f"返回 {len(result_list)} 条记录")

                    return {
                        "status": "fixed",
                        "index_issue": True,
                        "auto_fixed": True,
                        "result_count": len(result_list),
                        "analysis": analysis
                    }
                except Exception as retry_error:
                    if verbose:
                        print(f"❌ 索引创建后查询仍失败: {retry_error}")

                    return {
                        "status": "error",
                        "index_issue": True,
                        "auto_fixed": False,
                        "error": str(retry_error),
                        "analysis": analysis
                    }

            return {
                "status": "error",
                "index_issue": True,
                "auto_fixed": False,
                "error": error_msg,
                "analysis": analysis
            }

        else:
            # 其他类型的错误
            if verbose:
                print(f"❌ 查询失败 (非索引问题): {error_msg}")

            return {
                "status": "error",
                "index_issue": False,
                "error": error_msg
            }


# ============================================================================
# 4. 使用示例
# ============================================================================

def example_sync():
    """同步示例：诊断和修复索引问题"""
    print("=" * 70)
    print("同步版本：索引诊断示例")
    print("=" * 70)

    # 创建引擎和会话
    engine = create_engine("couchdb://admin:123456@localhost:5984/test_db")
    SessionFactory = sessionmaker(engine)

    with SessionFactory() as session:
        # 场景1: log_type = "operation" (假设有索引，应该成功)
        print("\n【场景1】查询 log_type='operation'")
        print("-" * 70)
        stmt1 = select(AuditLog).where(
            AuditLog.log_type == "operation",
            AuditLog.tenant_id == "tenant_123"
        ).order_by(AuditLog.create_time.desc()).limit(20)

        result1 = diagnose_and_fix_index(
            session,
            stmt1,
            auto_create=True,
            verbose=True
        )

        # 场景2: log_type = "login" (可能缺少索引)
        print("\n【场景2】查询 log_type='login'")
        print("-" * 70)
        stmt2 = select(AuditLog).where(
            AuditLog.log_type == "login",
            AuditLog.tenant_id == "tenant_123"
        ).order_by(AuditLog.create_time.desc()).limit(20)

        result2 = diagnose_and_fix_index(
            session,
            stmt2,
            auto_create=True,
            verbose=True
        )

        # 打印总结
        print("\n" + "=" * 70)
        print("诊断总结")
        print("=" * 70)
        print(f"场景1状态: {result1['status']}")
        print(f"场景2状态: {result2['status']}")


async def example_async():
    """异步示例：诊断和修复索引问题"""
    print("=" * 70)
    print("异步版本：索引诊断示例")
    print("=" * 70)

    # 创建异步引擎和会话
    engine = create_async_engine("couchdb+async://admin:123456@localhost:5984/test_db")
    AsyncSessionFactory = async_sessionmaker(engine)

    async with AsyncSessionFactory() as session:
        # 场景1: log_type = "operation"
        print("\n【场景1】查询 log_type='operation'")
        print("-" * 70)
        stmt1 = select(AuditLog).where(
            AuditLog.log_type == "operation",
            AuditLog.tenant_id == "tenant_123"
        ).order_by(AuditLog.create_time.desc()).limit(20)

        result1 = await diagnose_and_fix_index_async(
            session,
            stmt1,
            auto_create=True,
            verbose=True
        )

        # 场景2: log_type = "login"
        print("\n【场景2】查询 log_type='login'")
        print("-" * 70)
        stmt2 = select(AuditLog).where(
            AuditLog.log_type == "login",
            AuditLog.tenant_id == "tenant_123"
        ).order_by(AuditLog.create_time.desc()).limit(20)

        result2 = await diagnose_and_fix_index_async(
            session,
            stmt2,
            auto_create=True,
            verbose=True
        )

        # 打印总结
        print("\n" + "=" * 70)
        print("诊断总结")
        print("=" * 70)
        print(f"场景1状态: {result1['status']}")
        print(f"场景2状态: {result2['status']}")

    await engine.dispose()


# ============================================================================
# 5. 主函数
# ============================================================================

if __name__ == "__main__":
    import sys

    # 根据参数选择同步或异步模式
    if len(sys.argv) > 1 and sys.argv[1] == "async":
        asyncio.run(example_async())
    else:
        example_sync()

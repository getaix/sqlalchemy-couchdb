# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- DualWriteManager 完整回滚功能实现
- 回滚失败日志记录机制
- GitHub Actions CI/CD workflow
- PyPI 自动发布配置
- 语义化版本管理配置

### Changed
- 代码格式化（Black）
- Ruff linting 修复
- 优化类型注解

### Fixed
- 修复示例代码中的语法错误

## [0.1.0] - 2025-01-04

### Added
- SQLAlchemy 2.0+ CouchDB Dialect 核心实现
- 同步和异步数据库访问支持
- SQL 到 Mango Query 编译器
- 完整的 CRUD 操作支持
- 类型系统和数据转换
- DB-API 2.0 兼容接口
- 批量插入优化
- 连接池管理
- 错误处理和异常系统
- 完整的测试套件（100%核心功能覆盖）
- 使用示例和文档

### Phase 1 Features
- 纯 CouchDB 模式支持
- 同步/异步操作
- 基本 CRUD 操作
- WHERE 条件查询
- ORDER BY 排序
- LIMIT/OFFSET 分页
- 批量操作优化

### Phase 2 Features (Experimental)
- 混合数据库架构
- 双写同步机制
- 智能查询路由
- 数据迁移工具

[Unreleased]: https://github.com/getaix/sqlalchemy-couchdb/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/getaix/sqlalchemy-couchdb/releases/tag/v0.1.0

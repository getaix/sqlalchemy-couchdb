# 安装指南

## 系统要求

- **Python**: 3.11 或更高版本
- **SQLAlchemy**: 2.0.0 或更高版本
- **httpx**: 0.27.0 或更高版本

## 安装方式

### 基础安装

```bash
pip install sqlalchemy-couchdb
```

### 开发安装

```bash
git clone https://github.com/getaix/sqlalchemy-couchdb.git
cd sqlalchemy-couchdb

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate  # Windows

# 安装开发依赖
pip install -e ".[dev]"

# 安装可选依赖（用于 Phase 2 混合模式）
pip install -e ".[postgres]"     # PostgreSQL
pip install -e ".[mysql]"        # MySQL
pip install -e ".[all]"          # 所有数据库
```

## 验证安装

```python
import sqlalchemy_couchdb

print(f"SQLAlchemy CouchDB 版本: {sqlalchemy_couchdb.__version__}")
```

## 可选依赖

### Phase 2 混合模式

```bash
# PostgreSQL 支持
pip install sqlalchemy-couchdb[postgres]
# 或
pip install "sqlalchemy-couchdb[postgres]"

# MySQL 支持
pip install sqlalchemy-couchdb[mysql]

# 所有数据库支持
pip install sqlalchemy-couchdb[all]
```

## 设置 CouchDB

### 使用 Docker

```bash
docker run -d -p 5984:5984 \
  -e COUCHDB_USER=admin \
  -e COUCHDB_PASSWORD=password \
  --name couchdb couchdb:3

# 创建数据库
curl -X PUT http://admin:password@localhost:5984/testdb
```

### 手动安装

1. 下载 CouchDB: https://couchdb.apache.org/#download
2. 安装并启动服务
3. 通过管理界面创建数据库
4. 创建管理员账户

## 环境变量

```bash
# .env 文件
export COUCHDB_HOST=localhost
export COUCHDB_PORT=5984
export COUCHDB_USER=admin
export COUCHDB_PASSWORD=password
export COUCHDB_DATABASE=mydb

# Phase 2 混合模式
export SECONDARY_DB_URL=postgresql://user:pass@localhost:5432/mydb
```

## 故障排除

### 常见问题

#### 1. ImportError: No module named 'sqlalchemy_couchdb'

**解决方案**:
```bash
pip install sqlalchemy-couchdb
# 或者
pip install -e .
```

#### 2. httpx 兼容性问题

**解决方案**:
```bash
pip install --upgrade httpx
```

#### 3. Python 版本不兼容

**解决方案**:
```bash
# 检查 Python 版本
python --version  # 应该是 3.11+

# 如果版本过低，升级 Python
# 或使用 pyenv 管理多个版本
pyenv install 3.11.0
pyenv local 3.11.0
```

#### 4. CouchDB 连接失败

**解决方案**:
```bash
# 检查 CouchDB 服务状态
curl http://localhost:5984/

# 检查防火墙设置
sudo ufw status  # Ubuntu/Debian
sudo firewall-cmd --list-ports  # CentOS/RHEL

# 检查端口是否被占用
netstat -tulpn | grep 5984
```

## 性能优化

### 安装建议

1. **使用虚拟环境**: 避免依赖冲突
2. **启用缓存**: 安装 uv 或启用 pip 缓存
3. **使用二进制轮子**: 避免从源码编译

```bash
# 使用 uv 快速安装（推荐）
uv pip install sqlalchemy-couchdb

# 或启用 pip 缓存
pip install --cache-dir ~/.pip/cache sqlalchemy-couchdb
```

## 下一步

- [基础用法](basic-usage.md)
- [连接配置](connection.md)
- [同步操作](../guide/sync-operations.md)
- [异步操作](../guide/async-operations.md)

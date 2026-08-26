# 数据库引擎与会话管理
# 为什么用同步 SQLAlchemy + SQLite？
#   - 学习项目，同步代码更直观、更易调试（异步 ORM 样板多、难排错）
#   - SQLite 单文件、零运维，MVP 完全够用（Phase 6 的长期记忆也是它）
#
# 三个关键配置：
#   1. check_same_thread=False：SQLite 默认禁止跨线程使用连接，
#      而 FastAPI 的同步端点在线程池执行，必须放开
#   2. WAL 模式：并发读写在 SQLite 下更稳（写不阻塞读），
#      通过 PRAGMA 开启，对普通文件是持久设置
#   3. 每操作独立 session：SessionLocal() 用完即关，避免跨线程复用

import os
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# 数据库文件位置：默认 backend/xuan_shu.db
# 可用环境变量 XUANSHU_DB_PATH 覆盖（测试用临时库隔离；Docker 里挂到持久卷）
_DEFAULT_DB = Path(__file__).resolve().parents[2] / "xuan_shu.db"
_db_path = Path(os.getenv("XUANSHU_DB_PATH", str(_DEFAULT_DB)))
DATABASE_URL = f"sqlite:///{_db_path}"

# SQLite 不会自动创建父目录：若配置了自定义路径，启动前确保目录存在
_db_path.parent.mkdir(parents=True, exist_ok=True)

# 所有 ORM 模型的基类（models.py 继承它）
class Base(DeclarativeBase):
    """ORM 声明基类：SQLAlchemy 2.0 风格"""


# 创建引擎：check_same_thread=False 允许跨线程使用
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

# 会话工厂：autoflush=False 避免查询时意外提前 flush
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# 连接建立后自动开启 WAL 模式（并发读写下更稳）
@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def init_db() -> None:
    """初始化数据库：建表 + 写入默认用户。

    在应用启动时调用一次（main.py lifespan）。
    幂等：已存在的表/用户不会重复创建。
    """
    # 导入 models 以注册所有表定义（否则 create_all 看不到表）
    from app.database import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # 种子数据：默认用户 user_id=1（MVP 单用户模式）
    from app.database.models import User

    with SessionLocal() as db:
        if db.get(User, 1) is None:
            db.add(User(id=1, name="default_user"))
            db.commit()


def get_db():
    """FastAPI 依赖：请求级数据库会话（自动关闭）。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# pytest 全局配置
# 关键：必须在导入任何 app.* 模块之前设置 XUANSHU_DB_PATH，
# 让 SQLAlchemy 引擎指向临时测试库，避免污染开发数据库 xuan_shu.db

import os
import tempfile
from pathlib import Path

# 设置测试库路径（必须在 import app 之前！）
_TMP_DB = Path(tempfile.mkdtemp()) / "test.db"
os.environ["XUANSHU_DB_PATH"] = str(_TMP_DB)

import pytest  # noqa: E402

from app.database.database import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """整个测试会话只初始化一次测试库"""
    init_db()
    yield

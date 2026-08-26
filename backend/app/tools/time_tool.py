# 时间工具：查询当前日期时间
# 为什么单独一个工具？模型不知道"现在"是几点（训练数据有截止时间），
# 必须由真实时钟提供——这是 Agent 工具的最经典例子

from datetime import datetime
from zoneinfo import ZoneInfo

from langchain_core.tools import tool

# 固定北京时间（Asia/Shanghai），避免服务器时区不一致
_BEIJING_TZ = ZoneInfo("Asia/Shanghai")


@tool
def get_current_time() -> str:
    """获取当前日期和时间（北京时间）。

    当用户询问"现在几点""今天几号""今天是星期几"时调用本工具。
    """
    now = datetime.now(_BEIJING_TZ)
    # 中文星期映射，输出更贴合中文用户
    weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    weekday = weekdays[now.weekday()]
    return now.strftime(f"%Y-%m-%d %H:%M:%S {weekday}")

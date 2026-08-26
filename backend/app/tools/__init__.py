# 工具汇总：所有注册给 Agent 的工具
# 新增工具时：实现 → 在此导入并加入 ALL_TOOLS → 自动被 graph bind
# （nodes.py 用 ALL_TOOLS 绑定，ToolNode 用 ALL_TOOLS 执行）

from app.tools.calculator_tool import calculator
from app.tools.memory_tool import forget_memory, recall_memory, remember
from app.tools.note_tool import delete_note, save_note, search_notes
from app.tools.time_tool import get_current_time
from app.tools.todo_tool import complete_todo, create_todo, delete_todo, get_todos

ALL_TOOLS = [
    get_current_time,
    calculator,
    create_todo,
    get_todos,
    complete_todo,
    delete_todo,
    save_note,
    search_notes,
    delete_note,
    remember,
    recall_memory,
    forget_memory,
]

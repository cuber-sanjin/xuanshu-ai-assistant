# 安全计算器：基于 AST 白名单求值，绝不用 eval
# 为什么不能 eval？
#   eval("__import__('os').system('rm -rf /')") 可直接执行任意代码——远程注入漏洞。
# 本方案：只允许"数字常量 + 四则/取模/幂 + 括号"，任何其他节点（函数调用、
# 变量名、属性访问等）一律拒绝，从语法层面杜绝注入。

import ast
import operator
from typing import Any

from langchain_core.tools import tool

# 白名单：二元运算符 → Python 实现
_BIN_OPS: dict[type, Any] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# 白名单：一元运算符
_UNARY_OPS: dict[type, Any] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# 常见全角/中文符号 → 半角（用户输入习惯）
_SYMBOL_MAP = {
    "×": "*",
    "÷": "/",
    "（": "(",
    "）": ")",
    "＋": "+",
    "－": "-",
    "＊": "*",
}


def _eval_node(node: ast.AST) -> float:
    """递归求值 AST 节点，非白名单节点直接抛错。"""
    # 数字常量：只允许 int/float，杜绝字符串（字符串可被利用做更多操作）
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return node.value
        raise ValueError(f"仅支持数字常量，不支持: {node.value!r}")

    # 二元运算：左右子节点递归求值
    if isinstance(node, ast.BinOp):
        op_fn = _BIN_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"不支持的运算符: {type(node.op).__name__}")
        return op_fn(_eval_node(node.left), _eval_node(node.right))

    # 一元运算：如 -5、+3
    if isinstance(node, ast.UnaryOp):
        op_fn = _UNARY_OPS.get(type(node.op))
        if op_fn is None:
            raise ValueError(f"不支持的一元运算符: {type(node.op).__name__}")
        return op_fn(_eval_node(node.operand))

    # 其他任何节点（Call/Name/Attribute/List 等）→ 拒绝
    raise ValueError(f"表达式包含不支持的元素: {type(node).__name__}")


def safe_calculate(expression: str) -> str:
    """安全计算数学表达式，返回结果字符串。

    异常时返回错误说明而不是抛出，方便 LLM 直接读结果。
    """
    # 1. 预处理：统一符号、去空白
    expr = expression.strip()
    for zh, en in _SYMBOL_MAP.items():
        expr = expr.replace(zh, en)

    # 2. 解析为 AST（语法错误在此抛出）
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        return f"表达式语法错误: {e}"

    # 3. 白名单求值（恶意表达式在此被拒绝）
    try:
        result = _eval_node(tree.body)
    except (ValueError, ZeroDivisionError) as e:
        return f"无法计算: {e}"

    # 整数结果去小数点（10.0 → 10），浮点保留合理精度
    if isinstance(result, float) and result.is_integer():
        return str(int(result))
    return str(result)


@tool
def calculator(expression: str) -> str:
    """计算数学表达式。支持 + - * / % ** 和括号。

    当用户要求"算一下/计算"并给出算式时调用本工具。
    示例：calculator("128*37")、calculator("(1+2)*3")、calculator("2**10")
    """
    return safe_calculate(expression)

# 计算器工具测试：重点是"安全"——恶意表达式必须被拒绝

from app.tools.calculator_tool import safe_calculate


def test_basic_arithmetic():
    assert safe_calculate("128*37") == "4736"


def test_parentheses():
    assert safe_calculate("(1+2)*3") == "9"


def test_power():
    assert safe_calculate("2**10") == "1024"


def test_float_result():
    assert safe_calculate("10/4") == "2.5"


def test_fullwidth_symbols():
    # 用户输入全角 × ÷ 也能算
    assert safe_calculate("128×37") == "4736"
    assert safe_calculate("100÷4") == "25"


def test_reject_code_injection():
    """核心安全用例：执行任意代码的表达式必须被拒绝"""
    result = safe_calculate("__import__('os').system('echo hacked')")
    assert "不支持" in result


def test_reject_function_call():
    result = safe_calculate("len([1,2,3])")
    assert "不支持" in result


def test_reject_variable():
    result = safe_calculate("x + 1")
    assert "不支持" in result


def test_reject_string():
    result = safe_calculate("'abc'")
    assert "不支持" in result


def test_division_by_zero():
    result = safe_calculate("1/0")
    assert "无法计算" in result


def test_syntax_error():
    result = safe_calculate("1++*2")
    assert "语法错误" in result or "不支持" in result

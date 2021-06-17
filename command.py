from typing import TypeVar
from .variable import ResultVariable

def isContext(context):
    return type(context) in (str,ResultVariable)

# コマンドの型戻り値をチェックをするデコレータ
T = TypeVar('T')
def command(func:T) -> T:
    def inner(*args,**kwargs) -> 'ResultVariable':
        result = func(*args,**kwargs)
        assert isContext(result), f'command must return ResultVariable instance. not {result} in {func}'
        return result
    return inner
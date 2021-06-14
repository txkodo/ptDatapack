from .datapack import Function
from .mcpath import McPath

def call(path:McPath):
    return f'function {path.with_suffix(".mcfunction").function_path}'
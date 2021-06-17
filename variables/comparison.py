from pyDatapack.variable import Variable
from typing import Union

# 比較演算結果 execute ifのサブコマンドとなったりBoolDataにキャストしたりできる。
class Comparison(Variable):
    def __init__(self, expression:str, contexts: list[Union[str, 'Variable']] = []) -> None:
        super().__init__(contexts=contexts)
        self.expression = expression
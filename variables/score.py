from pyDatapack.id import gen_objective_id,gen_scoreholder_id
from pyDatapack.command import command
from pyDatapack.variable import Variable,ResultVariable
from typing import Union,Callable

class ObjectiveError(Exception): pass

# Scoreboard Objective
class Objective:
    name_set = set()
    default:'Objective'

    def __new__(cls, name:str = None ) -> 'Objective':
        if name and name in cls.name_set:
            raise ObjectiveError(f'Objective "{name}" already exists. Use other name.')
        cls.name_set.add(name)
        return super().__new__(cls)

    def __init__(self,name:str = None) -> None:
        self.name = name or gen_objective_id()

Objective.default = Objective('-')

class ScoreHolderError(Exception):pass

# Scoreboard
class Score(Variable):
    name_set = set()

    def __new__(cls, name = None, objective:Objective = None, contexts=[]) -> 'Score':
        if name and name in cls.name_set:
            raise ScoreHolderError(f'Score holder "{name}" already exists. Use other name.')
        cls.name_set.add(name)
        return super().__new__(cls)

    def __init__(self, name = None, objective:Objective = None, contexts=[]) -> None:
        super().__init__(contexts=contexts)
        self.name = name or gen_scoreholder_id()
        self.objective = objective or Objective.default
    
    @property
    def expression(self):
        return f'{self.name} {self.objective.name}'
    
    # 自己代入演算子のオーバーロードの親定義
    @command
    def __iop(self,opstr:str,opsign:str,value:Union[int,'Score']):
        operation = lambda value:f'scoreboard players operation {self.expression} {opsign} {value.expression}'
        if type(value) is Score:
            self.addcontext(value,operation(value))
        elif opstr:
            self.addcontext(f'scoreboard players {opstr} {self.expression} {value}')
        else:
            s = Score()
            s.set(value)
            self.addcontext(s,operation(s))
        return ResultVariable(self)

    # 演算の親定義
    def __op(self,iop:Callable,value):
        new = Score()
        new.set(self)
        iop(new,value)
        new.addcontext(self)
        return new

    @command
    def get(self) -> ResultVariable:
        # 状態変更ではないので自分自身は渡さない
        return ResultVariable(f'scoreboard players get {self.expression}')

    # def __eq__(self,value:Union[int,'Score']) -> Sou:
    #     new = Score()
    #     new.addcontext([new.set(self),new.add(value)])
    #     return new

# 演算子オーバーロード
    @command
    def set(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop('set','=',value)

    @command
    def add(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop('add','+=',value)

    def __add__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.add,value)

    @command
    def remove(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop('remove','-=',value)

    def __sub__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.remove,value)

    @command
    def multiply(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop(None,'*=',value)

    def __mul__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.multiply,value)

    @command
    def div(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop(None,'*=',value)

    def __floordiv__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.div,value)

    @command
    def mod(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop(None,'*=',value)

    def __mod__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.mod,value)

    @command
    def mod(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop(None,'*=',value)

    @command
    def max(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop(None,'>',value)

    @command
    def min(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop(None,'<',value)
    
    @command
    def switch(self,value:Union[int,'Score']) -> list[str]:
        return self.__iop(None,'><',value)
#>
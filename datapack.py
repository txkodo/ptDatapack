import mcpath
from os import name, path
from typing import Callable, Container, Iterable, TypeVar, Union
from .id import gen_function_id, gen_objective_id, gen_scoreholder_id, gen_datapath_id
from .mcpath import McPath
import re

# モジュール(意味を持ったファンクション群)
class Module:
    def __init__(self, main: 'MainModule', path: str) -> None:
        self.path = main.path/path
        (self.path/'-').rmtree(ignore_errors=True)
    
    def func(self,name=None):
        return Function(self.path,name)

# 名前空間オブジェクト
class MainModule(Module):
    def __init__(self, path: McPath,funcnames:Iterable=[]) -> None:
        path.setDirectory('functions')
        self.path = path
        (self.path/'-').rmtree(ignore_errors=True)
        self.funcs:list[Function] = []
        for funcname in funcnames:
            func = self.func(funcname)
            setattr(self,funcname,func)
            self.funcs.append(func)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        for func in self.funcs:
            self > func

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

# スコアやデータ等のスーパークラス
class Variable:
    def __init__(self,contexts:list[Union[str,'Variable']]=[]) -> None:
        self.__contexts = []
        self.addcontext(*contexts)

    def addcontext(self,*contexts) -> None:
        commands = []
        for context in contexts:
            assert isinstance(context,(str,Variable)),f'str or Variable is allowed in context. not {type(context)}\n{context}.'
            commands.append(context)

        self.__contexts.extend(commands)

    def reflesh(self) -> list[str]:
        commands = [] 
        for context in self.__contexts:
            if type(context) is str:
                commands.append(context)
            elif isinstance(context,Variable):
                commands.extend(context.reflesh())
            else:
                assert False, f'{type(context)} is not allowed in context.'

        self.__contexts = []
        return commands

class ResultVariable(Variable):
    def __init__(self, *contexts:Union[str, 'Variable']) -> None:
        super().__init__(contexts=contexts)

class CommandAddtionFailed(Exception):pass

# ファンクション
class Function(Variable):
    called = set()
    def __init__(self,path:McPath,name:str=None,contexts=[]) -> None:
        super().__init__(contexts=contexts)
        self.commands:list[Union[str,Function]] = []
        self.__calling = False
        self.__baked = False
        self.hasname = bool(name)
        self.name = (name or ( '-/' + gen_function_id())) + '.mcfunction'
        self.path = path/self.name

    def __lt__(self,value:Module):
        self.bake()

    def __gt__(self,result:Union[str,list[str],'Function']):
        # 文字列の場合追記
        if type(result) is str:
            self.commands.append(result)
        # 処理結果の場合コンテクストを追加
        elif isContext(result):
            self.commands.extend(result.reflesh())
        # ファンクション系の場合呼び出し結果を追加
        elif type(result) in (Function,SubFunction):
            self.commands.extend(result.reflesh())
            self.commands.append(result)
        # エラー
        else:
            raise CommandAddtionFailed(f'you can append only list[str] instance to "Function". not {type(result)}.')

    def __enter__(self):
        return self

    def __exit__(self,*args):
        pass

    def call(self):
        # 再帰して帰ってきた場合
        if self.__calling:
          # ファンクションファイルに出力フラグを立てる
          self.__baked = True
          # 呼び出し文を返す
          return [f'function {self.path.function_path}']
        # 再帰チェックのためのフラグを立てる
        self.__calling = True
        # 内容の文字列化
        texts = self.textify()
        # 出力フラグがあるもしくはフェイル名がある場合はファイルに出力
        if self.__baked or self.hasname:
          self.bake()
          return [f'function {self.path.function_path}']
        self.__calling = False
        self.__baked = False
        return texts

    def textify(self):
        commands = []
        for command in self.commands:
            if type(command) is str:
                commands.append(command)
            elif type(command) in (Function,SubFunction):
                commands.extend(command.call())
        return commands

    def bake(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text('\n'.join(self.textify()))

    def Child(self):
        new = Function(self.path.parent)
        self > new
        return new

    def _subcommand(self,value:str) -> 'Function':
        new = Function(self.path.parent)
        subcommand = SubFunction(value,new)
        self > subcommand
        return new

    def Positioned(self,pos:str):
        return self._subcommand('positioned ' + pos)

    def As(self,entity:str):
        return self._subcommand('as ' + entity)

    def If(self,condition:Union[str,'Comparison','Data']):
        if type(condition) is str:
            return self._subcommand('if '+condition)
        elif type(condition) is Comparison:
            self.addcontext(condition)
            return self._subcommand('if '+ condition.expression)
        elif isinstance(condition,Data):
            self.addcontext(condition)
            return self._subcommand('if '+ condition.check_eixst().expression)
        assert False, f'{type(condition)} is not allowed in Subfunction.If'

    def Unless(self,condition:str):
        return self._subcommand('unless '+condition)

    def For(self,value:Union[int,'Score']):
        if type(value) in (int,Score):
            i = Score()
            self  > i.set(value)
            child = self.If(f'score {i.expression} matches 0..')
            child > i.remove(1)
            new   = child.new()
            child > new
            child.If(f'score {i.expression} matches 0..') > child
            return new

    def While(self,value:str):
        if type(value) in (str,):
            child = self.If(value)
            new   = child.new()
            child > new
            child.If(value) > child
            return new

    def DoWhile(self,value:str):
        if type(value) in (str,):
            child = self.Child()
            new   = child.new()
            child > new
            child.If(value) > child
            return new


class NonBakebleError(Exception):pass

# functionを呼び出すexecuteのサブコマンド
class SubFunction(Variable):
    def __init__(self, subcommand:str, function:Function,contexts:list[Union[str,'Variable']]=[]) -> None:
        super().__init__(contexts=contexts)
        self.function = function
        self.subcommand = subcommand

    def call(self):
        texts = self.function.textify()
        if len(texts) == 0:
            # コマンドがない場合なにも出力しない
            return ''
        if len(texts) == 1:
            # 一行ファンクションの場合exexcuteに埋め込む
            return ['execute ' + self.subcommand + ' run ' + texts[0]]
        # 複数行ファンクションの場合焼き付けてexexcuteから呼び出す
        self.function.bake()
        return ['execute ' + self.subcommand + ' run function ' + (self.function.path).function_path]

# 比較演算結果 execute ifのサブコマンドとなったりBoolDataにキャストしたりできる。
class Comparison(Variable):
    def __init__(self, expression:str, contexts: list[Union[str, 'Variable']] = []) -> None:
        super().__init__(contexts=contexts)
        self.expression = expression

# ストレージ名前空間
class StorageNamespace:
    name_set = set()
    default:'StorageNamespace'
    def __init__(self,namespace,id='') -> None:
        self.namespace = namespace
        self.id = id

    @property
    def expression(self):
        return f'storage {self.namespace}:{self.id}'
StorageNamespace.default = StorageNamespace('-')

class DataSetError(Exception):pass

# nbt全般のスーパークラス
class Data(Variable):
    convertmap = lambda:{
            bool:BoolData,
            int:IntData,
            Score:IntData,
            str:StrData,
            dict:Compound
        }
    def __init__(self, name:str=None, parent:str=None, holder:StorageNamespace=StorageNamespace.default, contexts: list[Union[str, 'Variable']]=[]) -> None:
        super().__init__(contexts=contexts)
        # ストレージ名前空間やエンティティ名など
        self.holder = holder
        # パスの最後の部分( .a [i] [{n=1}])
        self.name   = name or gen_datapath_id()
        # パスの最後以外の部分(x.y.z)
        self.parent = parent or ''

        self.value = None
    # # 別のストレージからデータを移動
    # def move(self,path_from:'Data'):
    #     self.addcontext([f'data modify {self.expression} set from {path_from.expression}'])

    # データに代入
    @command
    def set(self,value):
        nbtstr,context = self._set(value)
        self.addcontext(f'data modify {self.expression} set value {nbtstr}',*context)
        return ResultVariable(self)

    @staticmethod
    def genInstance(name,parent,holder,value) -> 'Data':
        return {
            bool:BoolData,
            int:IntData,
            Score:IntData,
            str:StrData,
            dict:Compound
        }[type(value)](name,parent,holder)

    def check_eixst(self):
        return Comparison(f'data {self.expression}',[self])

    def __eq__(self,value:str):
        match = re.fullmatch(r'\[\s*\{(.*)\}\s*\]',value)
        assert not match, 's.t[{a:x}]に対して同値比較はできません'
        return Comparison(f'data {self.holder.expression} {self.parent}{{{self.name[1:]}:{value}}}',[self])

    # # データを違う場所にコピー
    # def copyWithParent(self,path,holder,parent):
    #     if parent:
    #         path += self.relpath
    #     return self.__class__(self,path,holder)

    @property
    def expression(self):
        return f'{self.holder.expression} {self.parent}{self.name}'

class BoolData(Data):

    def _set(self,value:Union[bool,Comparison]):
        assert type(value) in (bool,Comparison)
        if type(value) is bool:
            return '1b' if value else '0b',[]
        else:
            return '-2b',[f'data modify {self.expression} set value 0b',f'execute if {value.expression} run data modify {self.expression} set value 1b']
    
    def __eq__(self, value: bool):
        assert type(value) is bool
        return super().__eq__(str(int(value))+'b')
    
    def check_eixst(self):
        return self.__eq__(True)

class IntData(Data):
    
    def _set(self,value:Union[int,'Score']):
        assert type(value) in (int,Score)
        if type(value) is int:
            return str(value),[]
        else:
            value:Score
            return '-2b',[f'execute store result {self.expression} int 1 run {value.get().reflesh()}']

class StrData(Data):

    def _set(self,value:str):
        assert type(value) is str
        return f'"{value}"',[]


class Compound(Data,Iterable):
    def __init__(self, name:str=None, parent:str=None, holder:StorageNamespace=StorageNamespace.default, contexts: list[Union[str, 'Variable']]=[]) -> None:
        super().__init__( name,parent,holder,contexts=contexts)
        self.value = {}

    # 設定時のパスチェックは行われないので注意
    def setitem(self,key,value):
        self.value[key] = value

    # forで回せるようにtIterable化する        
    def __iter__(self):
        return iter(self.value.items())

    def __getitem__(self,key):
        return self.value[key]

    def _set(self,value:dict):
        assert type(value) is dict
        text    = {}
        context = []
        for k,v in value.items():
            child = self.genInstance('.'+k, self.parent + self.name ,self.holder,v)
            c_text,c_context = child._set(v)
            self.value[k] = child
            text[k] = c_text
            context.extend(c_context)
        text = f'{{{ ",".join(f"{k}:{v}" for k,v in text.items()) }}}'
        return text,context

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
    
    # 演算子のオーバーロードの親定義
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
import mcpath
from os import name
from typing import Callable, Iterable, TypeVar, Union
from .id import gen_function_id, gen_objective_id, gen_scoreholder_id, gen_datapath_id
from .mcpath import McPath


# モジュール(意味を持ったファンクション群)
class Module:
    def __init__(self, main: 'MainModule', path: str) -> None:
        self.path = main.path/path
        (self.path/'-').rmtree(ignore_errors=True)

# 名前空間オブジェクト
class MainModule(Module):
    def __init__(self, path: McPath,funcnames:Iterable=[]) -> None:
        path.setDirectory('functions')
        self.path = path
        (self.path/'-').rmtree(ignore_errors=True)
        self.funcs:list[Function] = []
        for funcname in funcnames:
            func = Function(funcname)
            setattr(self,funcname,func)
            self.funcs.append(func)

    def __enter__(self):
        return self

    def __exit__(self,*args):
        for func in self.funcs:
            self > func

def isContext(context):
    return type(context) is list and all(map(lambda x:type(x) is str,context))

# コマンドの型戻り値をチェックをするデコレータ
T = TypeVar('T')
def command(func:T) -> T:
    def inner(*args,**kwargs) -> list[str]:
        result = func(*args,**kwargs)
        assert isContext(result), 'command must return context:list[str]'
        return result
    return inner

# スコアやデータ等のスーパークラス
class Variable:
    def __init__(self,contexts:list[Union[str,'Variable']]=[]) -> None:
        self.contexts = []
        self.addcontext(contexts)

    def addcontext(self,contexts=[]) -> None:
        commands = []
        for context in contexts:
            if type(context) is str:
                commands.append(context)
            elif isinstance(context,Variable):
                commands.extend(context.reflesh())
        self.contexts.extend(commands)

    def reflesh(self) -> list[str]:
        commands = self.contexts
        self.contexts = []
        return commands

class ResultVariable(Variable):
    pass

class CommandAddtionFailed(Exception):pass

# ファンクション
class Function(Variable):
    called = set()
    def __init__(self,name:str=None,contexts=[]) -> None:
        super().__init__(contexts=contexts)
        self.commands:list[Union[str,Function]] = []
        self.__calling = False
        self.__baked = False
        self.name = (name or ( '-/' + gen_function_id())) + '.mcfunction'

    def __lt__(self,value:Module):
      self.bake(value.path)

    def __gt__(self,result:Union[str,list[str],'Function']):
        # 文字列の場合追記
        if type(result) is str:
            self.commands.append(result)
        # 処理結果の場合コンテクストを追加
        elif isContext(result):
            self.commands.extend(result)
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

    def call(self,dirpath:McPath,join=True):
        if self.__calling:
          self.__baked = True
          return [f'function {self.path.function_path}']
        self.__calling = True
        texts = self.textify(dirpath)
        if self.__baked:
          self.bake(dirpath.path)
          return [f'function {self.path.function_path}']
        self.__calling = False
        self.__baked = False
        return texts

    def textify(self,dirpath:McPath):
        commands = []
        for command in self.commands:
            if type(command) is str:
                commands.append(command)
            elif type(command) in (Function,SubFunction):
                commands.extend(command.call(dirpath))
        return commands

    def bake(self,dirpath:McPath):
        path = dirpath/self.name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text('\n'.join(self.textify(dirpath)))

    def Child(self):
        new = Function()
        self > new
        return new

    def _subcommand(self,value:str) -> 'Function':
        new = Function()
        subcommand = SubFunction(value,new)
        self > subcommand
        return new

    def Positioned(self,pos:str):
        return self._subcommand('positioned ' + pos)

    def As(self,entity:str):
        return self._subcommand('as ' + entity)
    
    def If(self,condition:str):
        return self._subcommand('if '+condition)

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

    def call(self,dirpath:mcpath):
        texts = self.function.textify(dirpath)
        if len(texts) == 0:
            # コマンドがない場合なにも出力しない
            return ''
        if len(texts) == 1:
            # 一行ファンクションの場合exexcuteに埋め込む
            return ['execute ' + self.subcommand + ' run ' + texts[0]]
        # 複数行ファンクションの場合焼き付けてexexcuteから呼び出す
        self.function.bake(dirpath)
        return ['execute ' + self.subcommand + ' run function ' + (dirpath/self.function.name).function_path]


# pythonの組み込み型等の内容をmcDataに変換
def toData(value, path, holder) -> tuple[list[str],'Data',str]:
    t = type(value)
    context = []
    result  = None
    text    = ''
    # Dataのインスタンスだった場合
    if isinstance(t,Data):
        value:Data
        result   = t.__class__(path, holder)
        context = [f'data modify {result.expression} set from {value.expression}']
        text     = '-2b'
    # boolの内容
    elif t is bool:
        result = BoolData(path, holder)
        text     = '1b' if value else '0b'
    # strの内容
    elif t is str:
        result = StrData(path, holder)
        text     = '"'+value+'"'
    # intの内容
    elif t is int:
        result = IntData(path, holder)
        text     = str(value)
    # Scoreの内容
    elif t is Score:
        result = IntData(path, holder)
        context = [f'execute store result {result.expression} int 1 run {value.get()[0]}']
        text     = '-2b'
    # dictの内容
    elif t is dict:
        result = Compound(path, holder)
        texts = []
        for k,v in value.items():
            c_contexts,c_result,c_text = toData(v,path+'.'+k,holder)
            texts.append(k + ':' + c_text)    
            context.extend(c_contexts)
            result.setitem(k,c_result)
        text = '{'+','.join(texts)+'}'

    return context , result , text

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

# class Comparison()

class DataSetError(Exception):pass

# nbt全般のスーパークラス
class Data(Variable):
    def __init__(self, path, holder:StorageNamespace, contexts: list[Union[str, 'Variable']] = [] ) -> None:
        super().__init__(contexts=contexts)
        # ストレージ名前空間やエンティティ名など
        self.holder = holder
        # 絶対パス
        self.path = path or gen_datapath_id()

        self.value = None
    # # 別のストレージからデータを移動
    # def move(self,path_from:'Data'):
    #     self.addcontext([f'data modify {self.expression} set from {path_from.expression}'])

    # 文字化されたものをデータに代入
    @command
    def set(self,value:str):
        context , result , text =toData(value,self.path,self.holder)
        self.value = result.value
        return [f'data modify {self.expression} set value {text}'] + context

    # # データを違う場所にコピー
    # def copyWithParent(self,path,holder,parent):
    #     if parent:
    #         path += self.relpath
    #     return self.__class__(self,path,holder)

    @property
    def expression(self):
        return f'{self.holder.expression} {self.path}'

class BoolData(Data):
    def __init__(self, path:str=None, holder:StorageNamespace=StorageNamespace.default, contexts: list[Union[str, 'Variable']]=[]) -> None:
        super().__init__( path,holder,contexts=contexts)


class IntData(Data):
    def __init__(self, path:str=None, holder:StorageNamespace=StorageNamespace.default, contexts: list[Union[str, 'Variable']]=[]) -> None:
        super().__init__( path,holder,contexts=contexts)

    # def eval(self):
    #     return self.subcommand or f'{self.path}{{{self.value}:1b}}'

class StrData(Data):
    def __init__(self, path:str=None, holder:StorageNamespace=StorageNamespace.default, contexts: list[Union[str, 'Variable']]=[]) -> None:
        super().__init__( path,holder,contexts=contexts)


class Compound(Data):
    def __init__(self, path:str=None, holder:StorageNamespace=StorageNamespace.default, contexts: list[Union[str, 'Variable']]=[]) -> None:
        super().__init__( path,holder,contexts=contexts)
        self.value = {}

    # 設定時のパスチェックは行われないので注意
    def setitem(self,key,value):
        self.value[key] = value

    def __getitem__(self,key):
        return self.value[key]
    
    def set(self, value: str):
        r = super().set(value)
        return r

# class Comparison(ResultVariable):
#     def __init__(self, subcommand, contexts: list[Union[str, 'Variable']]) -> None:
#         context = [f'data modify storage TEST set value 0b',f'execute if {subcommand} run data modify storage TEST set value 1b']
#         super().__init__(contexts=contexts)
#         self.subcommand = subcommand

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
            return value.contexts + [operation(value)]
        if opstr:
            return [f'scoreboard players {opstr} {self.expression} {value}']
        else:
            s = Score()
            return s.set(value) + [operation(s)]

    def __op(self,iop:Callable,value):
        new = Score()
        new.addcontext([new.set(self),iop(new,value)])
        return new

    @command
    def get(self) -> list[str]:
        return [f'scoreboard players get {self.expression}']

    # def __eq__(self,value:Union[int,'Score']) -> Sou:
    #     new = Score()
    #     new.addcontext([new.set(self),new.add(value)])
    #     return new

# 演算子オーバーロード
    @command
    def set(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop('set','=',value)

    @command
    def add(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop('add','+=',value)

    def __add__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.add,value)

    @command
    def remove(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop('remove','-=',value)

    def __sub__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.remove,value)

    @command
    def multiply(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop(None,'*=',value)

    def __mul__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.multiply,value)

    @command
    def div(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop(None,'*=',value)

    def __floordiv__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.div,value)

    @command
    def mod(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop(None,'*=',value)

    def __mod__(self,value:Union[int,'Score']) -> 'Score':
        return self.__op(Score.mod,value)

    @command
    def mod(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop(None,'*=',value)

    @command
    def max(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop(None,'>',value)

    @command
    def min(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop(None,'<',value)
    
    @command
    def switch(self,value:Union[int,'Score']) -> list[str]:
        return self.contexts+self.__iop(None,'><',value)
#>
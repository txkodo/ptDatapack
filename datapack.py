from typing import Iterable, Union
from .id import gen_function_id
from .mcpath import McPath
from .command import isContext
from .variable import Variable
from .variables.data import Data,Compound
from .variables.comparison import Comparison
from .variables.score import Score

class MainModule:   
    # ワークスペースのMCパス
    workspace:McPath = None

    @staticmethod
    def func(name=None):
        return Function(MainModule.workspace,name)

class pyDatapackError(Exception):pass

# モジュール(意味を持ったファンクション群)
class Module:
    def __init__(self, path: str, data_annotation:dict = {} ) -> None:
        if MainModule.workspace is None:
            raise pyDatapackError('set variable "MainModule.workspace"(class:Mcpath) first.')
        MainModule.workspace.setDirectory('functions')

        self.path = MainModule.workspace/path
        (self.path/'-').rmtree(ignore_errors=True)

        self.data = Compound(data_annotation)

    def func(self,name=None):
        return Function(self.path,name)

#     def __enter__(self):
#         return self

#     def __exit__(self,*args):
#         for func in self.funcs:
#             self > func

class CommandAddtionFailed(Exception):pass

# ファンクション
class Function(Variable):
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

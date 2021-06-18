from pyDatapack.id import gen_datapath_id
from pyDatapack.command import command
from pyDatapack.variable import Variable,ResultVariable
from pyDatapack.datapath import DataPath
from .score import Score
from .comparison import Comparison
from typing import Union,Iterable

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
            bool:Bool,
            int:Int,
            Score:Int,
            str:Str,
            dict:Compound
        }

    def __init__(self, datapath:DataPath=None, holder:StorageNamespace=StorageNamespace.default, contexts: list[Union[str, 'Variable']]=[]) -> None:
        super().__init__(contexts=contexts)
        # ストレージ名前空間やエンティティ名など
        self.holder = holder
        # パス
        self.datapath   = datapath or DataPath(gen_datapath_id())
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
    def genInstance(path,holder,value) -> 'Data':
        return {
            bool:Bool,
            int:Int,
            Score:Int,
            str:Str,
            dict:Compound
        }[type(value)](path,holder)

    def check_eixst(self):
        return Comparison(f'data {self.expression}',[self])

    def __eq__(self,value:str):
        return Comparison(f'data {self.holder.expression} {self.datapath.compare(value)}',[self])

    # # データを違う場所にコピー
    # def copyWithParent(self,path,holder,parent):
    #     if parent:
    #         path += self.relpath
    #     return self.__class__(self,path,holder)

    @property
    def expression(self):
        return f'{self.holder.expression} {self.datapath}'

class Bool(Data):

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

class Int(Data):
    
    def _set(self,value:Union[int,'Score']):
        assert type(value) in (int,Score)
        if type(value) is int:
            return str(value),[]
        else:
            value:Score
            return '-2b',[f'execute store result {self.expression} int 1 run {value.get().reflesh()}']

class Str(Data):
    def _set(self,value:str):
        assert type(value) is str
        return f'"{value}"',[]

class Compound(Data,Iterable):
    def __init__(self, annotation:dict[str,Union[type,dict]]={}, datapath:DataPath=None, holder:StorageNamespace=StorageNamespace.default, contexts: list[Union[str, 'Variable']]=[],frozen = False) -> None:
        super().__init__( datapath,holder,contexts=contexts)
        self.frozen = frozen
        self.value:dict[str,Data] = {}
        for k,v in annotation.items():
            if type(v) is dict:
                self.value[k] = Compound(v,self.datapath/f'.{k}',holder,contexts)
            else:
                self.value[k] = v(self.datapath/f'.{k}',holder,contexts)
    
    # def annotate(self,annotation:dict[str,Union[type,dict]]):
    #     for k,v in annotation.items():
    #         if type(v) is dict:
    #             self.value[k] = Compound(v,self.datapath/f'.{k}', self.holder,self.__contexts)
    #         else:
    #             self.value[k] = v(self.datapath/f'.{k}', self.holder,self.__contexts)

    # forで回せるようにIterable化する        
    def __iter__(self):
        return iter(self.value.items())

    def __getitem__(self,key) -> Data:
        return self.value[key]

    def _set(self,value:dict):
        assert type(value) is dict
        text    = {}
        context = []
        for k,v in value.items():
            child = self.genInstance(self.datapath/f'.{k}' ,self.holder,v)
            c_text,c_context = child._set(v)
            if k in self.value:
                if type(self.value[k]) is not type(child):
                    raise TypeError(f'Compound value pair to key "{k}" annotated to be type "{type(self.value[k])}" not "{type(child)}"')
            elif self.frozen:
                raise KeyError(f'failed to add compound key "{k}". This compound tag is frozen.')
            self.value[k] = child
            text[k] = c_text
            context.extend(c_context)
        text = f'{{{ ",".join(f"{k}:{v}" for k,v in text.items()) }}}'
        return text,context
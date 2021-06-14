from ast import Index
from pyDatapack.datapack import Data
from typing import Union
import re

class DataPath:
    class Part:
        def __init__(self) -> None:
            pass

        def __repr__(self) -> str:
            pass
    
    class Head(Part):
        def __init__(self,value:str) -> None:
            assert type(value) is str
            self.value = value

        def __repr__(self) -> str:
            return self.value
    
    class HeadSelector(Part):
        def __init__(self,selector:dict) -> None:
            assert type(selector) is dict
            self.selector = selector

        def __repr__(self) -> str:
            return '{' + ','.join( f'{k}:{v}' for k,v in self.selector.items()) + '}'

    class Child(Part):
        def __init__(self,value:str) -> None:
            assert type(value) is str
            self.value = value
        
        def __repr__(self) -> str:
            return '.' + self.value

    class ChildWithSelector(Part):
        def __init__(self,value:str,selector:dict) -> None:
            assert type(value) is str
            assert type(selector) is dict
            self.value = value
            self.selector = selector
        
        def __repr__(self) -> str:
            return '.' + '{' + ','.join( f'{k}:{v}' for k,v in self.selector.items()) + '}'

    class Index(Part):
        def __init__(self,value:int) -> None:
            assert type(value) is int
            self.value = value

        def __repr__(self) -> str:
            return f'[{self.value}]'

    class ListSelector(Part):
        def __init__(self,selector:dict) -> None:
            assert type(selector) is dict
            self.selector = selector
        
        def __repr__(self) -> str:
            return '[{' + ','.join( f'{k}:{v}' for k,v in self.selector.items()) + '}]'

    def __init__(self,path:Union[str,'DataPath']) -> None:
        assert type(path) in (str,DataPath)
        self.parts = DataPathDecoder(path).parts if type(path) is str else path.parts
        print(self.parts)

class DataPathDecodeError(Exception):pass

class DataPathDecoder:
    def __init__(self,path:str) -> None:
        assert type(path) is str
        self.path  = path
        self.index = 0
        self.length = len(self.path)
        self.parts = [self.getfirstpart()]
        while self.index < self.length:
            self.parts.append(self.getpart())
            pass

    @property
    def char(self) -> str:
        return self.path[self.index]

    def getfirstpart(self) -> DataPath.Part:
        if self.char == '{':
            return DataPath.HeadSelector(self.getSelector())
        else:
            word = self.getword()
            if word:
                return DataPath.Head(word)
            else:
                raise DataPathDecodeError(f'DataPath must starts with "{{" or word . "-> {self.path}"')

    def getpart(self) -> DataPath.Part:
        # [ から始まる -> Index/ListSelector
        if self.char == '[':
            self.index += 1
            word = self.getword()
            # [ の後がすぐ単語 -> Index
            if word:
                self.index += 1
                try:
                    return DataPath.Index(int(word))
                except ValueError:
                    raise DataPathDecodeError(f'List index must be integer. "{self.path[:self.index-1]} <- {self.path[self.index-1:]}"')
            # [ の後が { -> ListSelector
            elif self.char == '{':
                selector = self.getSelector()
                # 現在位置が]なので一文字進める
                assert self.char == ']',self.char
                self.index += 1
                return DataPath.ListSelector(selector)
            else:
                assert False, f'word or "{{" not {self.char}'
        # . から始まる -> Child/ChildWithSelector
        elif self.char == '.':
            self.index += 1
            word = self.getword(False)
            assert word
            # 単語の次が . /[ -> Child
            if self.index == self.length or self.char in '[.':
                return DataPath.Child(word)
            # 単語の次が { -> ChildWithSelector
            if self.char == '{':
                selector = self.getSelector()
                return DataPath.ChildWithSelector(word,selector)
            else:
                assert False, f'"." or "{{" not {self.char}'
        else:
            assert False, f'"[" or "." not {self.char}'

    def getword(self,ignore_space=True):
        self.index
        if ignore_space:
            match = re.match(r'\s*([0-9a-zA-Z-_-]+|"(?:\\"|\\\\|[^"\\])+"|\'(?:\\\'|\\\\|[^\'\\])+\')\s*', self.path[self.index:])
        else:
            match = re.match(r'([0-9a-zA-Z-_-]+|"(?:\\"|\\\\|[^"\\])+"|\'(?:\\\'|\\\\|[^\'\\])+\')', self.path[self.index:])
        if match:
            self.index += match.span(0)[1]
            return match.group(1)
        match = re.match('\s*', self.path[self.index:])
        self.index += match.span(0)[1]
        return None
    
    
    def getSelector(self) -> dict:
        assert self.char == '{',self.char
        self.index += 1
        compound = {}
        while self.char != '}':
            # key:valueのペアを抽出
            key = self.getword()
            # 現在位置が:なので一文字進める
            self.index += 1
            value = self.getnbt()

            if type(key)   is not str: raise DataPathDecodeError(f'compound key is needed. "{self.path[:self.index]} <HERE> {self.path[self.index:]}"')
            if type(value) is not str: raise DataPathDecodeError(f'compound value is needed. "{self.path[:self.index]} <HERE> {self.path[self.index:]}"')

            compound[key] = value

            if self.char not in ',}': raise DataPathDecodeError(f'use "," or "}}". "{self.path[:self.index+1]} <- {self.path[self.index+1:]}"')
        self.index += 1

        return compound
 
    def getnbt(self) -> str:
        if self.char == '{':
            self.index += 1
            compound = {}
            while self.char != '}':
                # key:valueのペアを抽出
                key = self.getword()
                # 現在位置が:なので一文字進める
                self.index += 1
                value = self.getnbt()

                if type(key) is not str: raise DataPathDecodeError(f'compound key is needed. "{self.path[:self.index]} <HERE> {self.path[self.index:]}"')
                if type(value) is not str: raise DataPathDecodeError(f'compound value is needed. "{self.path[:self.index]} <HERE> {self.path[self.index:]}"')

                compound[key] = value

                self.index += 1
                if self.char not in ',}': raise DataPathDecodeError(f'use "," or "}}". "{self.path[:self.index]} <- {self.path[self.index:]}"')

            return f'{{{",".join( f"{k}:{v}" for k,v in compound.items())}}}'
        elif self.char == '[':
            self.index += 1
            prefix = ''
            if self.path[self.index:self.index+2] in ('I;','B;'):
                prefix = self.path[self.index,self.index+2]
                self.index += 2
            listtag = []
            while self.char != ']':
                # itemを抽出
                item = self.getword()
                # ] が即見つかったら抜ける
                if not item:
                    assert self.char == ']',self.char
                    # 現在位置が]なので一文字進める
                    self.index += 1
                    break
                listtag.append(item)
                # ] が見つかったら抜ける
                if self.char == ']':
                    # 現在位置が]なので一文字進める
                    self.index += 1
                    break
                # , が見つかったら次へ
                if self.char == ',':
                    # 現在位置が,なので一文字進める
                    self.index += 1
                    continue
                assert False,self.char
            return f'[{prefix}{",".join(listtag)}]'
        else:
            word = self.getword()
            return word


DataPath('a.d.fsa[0]')

from typing import Union

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

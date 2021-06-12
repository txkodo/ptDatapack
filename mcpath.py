import io
import shutil
from pathlib import Path

class McPathException(Exception):
  pass

class McPath:
  attributes = ('rootpath','directory','path')

  @classmethod
  def _new(cls,**kwargs):
    self = object.__new__(cls)
    for arg,val in kwargs.items():
      setattr(self,arg,val)
    return self

  def __repr__(self) -> str:
    if self.directory:
      return str(self.rootpath/self.directory/self.path)
    else:
      return str(self.rootpath/self.path)

  def __init__(self,path:str) -> None:
    self.rootpath  = Path(path)
    self.directory = ''
    self.path      = Path('')

  @property
  def name(self) -> str:
    return self.path.name

  @property
  def normal_path(self) -> Path:
    return self.rootpath/self.directory/self.path

  @property
  def function_path(self) -> str:
    if self.path.suffix != '.mcfunction':
      raise McPathException('function file must have suffix ".mcfunction"')
    return self.rootpath.name + ':' + self.non_suffix

  @property
  def storage_path(self) -> str:
    return self.rootpath.name + ': ' + self.non_suffix.replace('/','.')

  @property
  def non_suffix(self):
    return self.path.with_suffix('').as_posix()

  @property
  def parent(self):
    return self._new_instance(path=self.path.parent)

  def with_suffix(self,suffix:str):
    return self._new_instance(path=self.path.with_suffix(suffix))
  
  def with_name(self,name:str):
    return self._new_instance(path=self.path.with_name(name))

  def with_directory(self,dir:str):
    new = self._new_instance()
    new.setDirectory(dir)
    return new

  def setDirectory(self,name:str):
    if str(Path(name).parent)!='.':
      raise McPathException('Directory name must not has hierarchy')
    self.directory = name
  
  def pathFromAbs(self,path):
    parts = Path(path).relative_to(self.rootpath).parts
    return self._new_instance(directory=parts[0],path=Path(*parts[1:]))

  def _new_instance(self,**kwargs) -> 'McPath':
    attributes = { attr: kwargs[attr] if attr in kwargs else getattr(self,attr) for attr in type(self).attributes}
    return type(self)._new(**attributes)

  def __truediv__(self,value) -> 'McPath':
    return self._new_instance(path = self.path/value)

  def open(self,*arg,**kwarg) -> io.TextIOWrapper:
    if self.path.is_dir():
      McPathException('Cannot open directory')
    path = self.normal_path
    path.parent.mkdir(exist_ok=True,parents=True)
    return path.open(*arg,**kwarg)

  def append_text(self, data, encoding=None, errors=None):
    # Open the file in text mode, append to it, and close the file.
    if not isinstance(data, str):
        raise TypeError('data must be str, not %s' % data.__class__.__name__)
    with self.open(mode='a', encoding=encoding, errors=errors) as f:
        return f.write(data)

  def write_text(self, data, encoding=None, errors=None):
    # Open the file in text mode, append to it, and close the file.
    if not isinstance(data, str):
        raise TypeError('data must be str, not %s' % data.__class__.__name__)
    with self.open(mode='w', encoding=encoding, errors=errors) as f:
        return f.write(data)

  def read_text(self, encoding=None, errors=None):
    # Open the file in text mode, append to it, and close the file.
    with self.open(mode='r', encoding=encoding, errors=errors) as f:
        return f.read()

  # ファイルを削除
  def unlink(self,missing_ok=False):
    self.normal_path.unlink(missing_ok=missing_ok)

  # ディレクトリを中身ごと削除
  def rmtree(self,ignore_errors=False):
    shutil.rmtree(self.normal_path,ignore_errors=ignore_errors)
  
  def mkdir(self, mode=0o777, parents=False, exist_ok=False) -> None:
    self.normal_path.mkdir(mode,parents,exist_ok)

  def exists(self,ignore_errors=False):
    return self.normal_path.exists()

  def iterdir(self,ignore_errors=False):
    return map(self.pathFromAbs,self.normal_path.iterdir())

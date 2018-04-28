
from abc import ABC

from .compat import NoneType


class JSONSerializable(ABC):
    pass


JSONSerializable.register(NoneType)
JSONSerializable.register(int)
JSONSerializable.register(float)
JSONSerializable.register(list)
JSONSerializable.register(str)

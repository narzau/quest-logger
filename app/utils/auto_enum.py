import enum

class AutoEnum(enum.Enum):
    def __eq__(self, other):
        if isinstance(other, type(self)):
            return self is other
        return self.value == other
    
    def __hash__(self):
        return hash(self.value)
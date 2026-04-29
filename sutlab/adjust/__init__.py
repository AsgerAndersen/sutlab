# sutlab/adjust — functions that adjust the values of a SUT

from sutlab.adjust._add import adjust_add_sut
from sutlab.adjust._subtract import adjust_subtract_sut
from sutlab.adjust._substitute import adjust_substitute_sut

__all__ = ["adjust_add_sut", "adjust_subtract_sut", "adjust_substitute_sut"]

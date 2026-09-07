"""
Optimization passes package.

Every pass is a class exposing:
    name: str                                    -- human-readable identifier
    apply(instructions: List[Instruction]) -> List[Instruction]
    self.changes: int                            -- set after apply(), for stats

PASS_REGISTRY maps a pass's string name (used as a "gene" by the
genetic algorithm) to its class. PASS_NAMES is the ordered list of
valid gene values a chromosome can be built from.
"""

import copy

from .constant_folding import ConstantFolding
from .constant_propagation import ConstantPropagation
from .copy_propagation import CopyPropagation
from .common_subexpression import CommonSubexpressionElimination
from .dead_code_elimination import DeadCodeElimination
from .strength_reduction import StrengthReduction

PASS_REGISTRY = {
    "ConstantFolding": ConstantFolding,
    "ConstantPropagation": ConstantPropagation,
    "CopyPropagation": CopyPropagation,
    "CommonSubexpressionElimination": CommonSubexpressionElimination,
    "DeadCodeElimination": DeadCodeElimination,
    "StrengthReduction": StrengthReduction,
}

PASS_NAMES = list(PASS_REGISTRY.keys())

# A sensible, hand-picked, textbook fixed order -- used as the
# "traditional compiler" baseline that the evolutionary search is
# compared against.
TRADITIONAL_SEQUENCE = [
    "ConstantPropagation",
    "ConstantFolding",
    "CopyPropagation",
    "CommonSubexpressionElimination",
    "StrengthReduction",
    "DeadCodeElimination",
]


def apply_pass_sequence(instructions, sequence):
    """Applies a sequence (list of pass-name strings) to `instructions` in order.

    Returns a brand-new instruction list; `instructions` is never mutated.
    Raises KeyError if `sequence` contains an unknown pass name.
    """
    current = copy.deepcopy(instructions)
    for name in sequence:
        pass_cls = PASS_REGISTRY[name]
        current = pass_cls().apply(current)
    return current

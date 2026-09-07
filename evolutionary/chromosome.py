"""
Chromosome representation for the Genetic Algorithm.

A chromosome is an ordered sequence ("genes") of optimization pass
names, e.g.:

    ["ConstantFolding", "ConstantPropagation", "CopyPropagation", "DeadCodeElimination"]

Applying the passes in that exact order to a program's Three-Address
Code is one candidate "optimization strategy". Different orderings and
different lengths represent genuinely different strategies -- this is
the search space the GA explores to solve the phase-ordering problem.
"""

import random
from optimizations import PASS_NAMES

DEFAULT_MIN_LEN = 3
DEFAULT_MAX_LEN = 8


class Chromosome:
    def __init__(self, genes=None, min_len=DEFAULT_MIN_LEN, max_len=DEFAULT_MAX_LEN):
        self.min_len = min_len
        self.max_len = max_len
        self.genes = list(genes) if genes is not None else self._random_genes()
        self.fitness = None
        self.metrics = None
        self.optimized_instructions = None

    def _random_genes(self):
        length = random.randint(self.min_len, self.max_len)
        return [random.choice(PASS_NAMES) for _ in range(length)]

    def copy(self):
        clone = Chromosome(genes=list(self.genes), min_len=self.min_len, max_len=self.max_len)
        return clone

    def __repr__(self):
        return " -> ".join(self.genes)

    def __len__(self):
        return len(self.genes)

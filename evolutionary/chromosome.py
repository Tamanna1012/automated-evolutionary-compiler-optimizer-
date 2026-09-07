"""
Chromosome representation for the Genetic Algorithm.

A chromosome is a FIXED-LENGTH ordered sequence ("genes") of
optimization pass names, e.g. (with CHROMOSOME_LENGTH = 6):

    ["ConstantFolding", "ConstantPropagation", "CopyPropagation",
     "DeadCodeElimination", "ConstantFolding", "StrengthReduction"]

Applying the passes in that exact order to a program's Three-Address
Code is one candidate "optimization strategy". A pass name may repeat
(running Constant Propagation twice is a valid, and sometimes useful,
strategy) -- this is the search space the GA explores to solve the
phase-ordering problem.

Keeping every chromosome the same length keeps the whole algorithm
textbook-simple: crossover and mutation never have to worry about
genomes of different sizes, which is exactly how a "classic" genetic
algorithm over fixed-length arrays works.
"""

import random
from optimizations import PASS_NAMES

CHROMOSOME_LENGTH = 6  # one slot per optimization pass


class Chromosome:
    def __init__(self, genes=None):
        self.genes = list(genes) if genes is not None else self._random_genes()
        self.fitness = None
        self.metrics = None
        self.optimized_instructions = None

    @staticmethod
    def _random_genes():
        return [random.choice(PASS_NAMES) for _ in range(CHROMOSOME_LENGTH)]

    def copy(self):
        return Chromosome(genes=list(self.genes))

    def __repr__(self):
        return " -> ".join(self.genes)

    def __len__(self):
        return len(self.genes)

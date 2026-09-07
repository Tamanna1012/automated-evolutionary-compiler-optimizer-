"""
Genetic Algorithm Engine
-------------------------
Solves the compiler *phase-ordering problem*: rather than applying
optimization passes in one fixed, hand-picked order, this searches the
space of possible pass sequences for the one that yields the best
`evaluate_fitness` score on the program at hand.

A textbook, fixed-length genetic algorithm -- every chromosome is the
same length (see chromosome.py), so there is nothing clever needed to
combine or mutate two of them. Four standard operators:

    Selection  -- tournament selection (pick k random individuals, keep the fittest)
    Crossover  -- single-point crossover on the gene list
    Mutation   -- per-gene point mutation (replace a gene with a random pass)
    Elitism    -- the top-N fittest individuals are carried into the
                  next generation unchanged, guaranteeing fitness never
                  regresses from one generation to the next
"""

import random
from typing import List

from optimizations import PASS_NAMES
from .chromosome import Chromosome, CHROMOSOME_LENGTH
from .fitness import evaluate_fitness
from compiler.interpreter import run_tac, TACRuntimeError


class GeneticAlgorithm:
    def __init__(
        self,
        instructions,
        population_size=30,
        generations=40,
        mutation_rate=0.2,
        crossover_rate=0.8,
        elitism_count=2,
        tournament_size=3,
        seed=None,
    ):
        self.instructions = instructions
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elitism_count = max(1, elitism_count)
        self.tournament_size = tournament_size
        if seed is not None:
            random.seed(seed)

        try:
            self.original_output = run_tac(instructions)
        except TACRuntimeError:
            self.original_output = None  # every candidate will then score 0, surfaced to the caller

    # ---- core loop -----------------------------------------------------
    def run(self):
        population = [Chromosome() for _ in range(self.population_size)]

        history = []
        best_ever = None

        for generation in range(1, self.generations + 1):
            self._evaluate_population(population)
            population.sort(key=lambda c: c.fitness, reverse=True)

            gen_best = population[0]
            if best_ever is None or gen_best.fitness > best_ever.fitness:
                best_ever = gen_best.copy()
                best_ever.fitness = gen_best.fitness
                best_ever.metrics = gen_best.metrics
                best_ever.optimized_instructions = gen_best.optimized_instructions

            avg_fitness = sum(c.fitness for c in population) / len(population)
            history.append({
                "generation": generation,
                "best_fitness": round(gen_best.fitness, 3),
                "avg_fitness": round(avg_fitness, 3),
                "best_sequence": list(gen_best.genes),
            })

            if generation == self.generations:
                break  # no need to breed a population that will never be evaluated

            population = self._next_generation(population)

        return best_ever, history

    # ---- fitness evaluation -----------------------------------------------------
    def _evaluate_population(self, population: List[Chromosome]):
        for chrom in population:
            if chrom.fitness is not None:
                continue  # elites already evaluated
            fitness, optimized, metrics = evaluate_fitness(
                self.instructions, chrom.genes, original_output=self.original_output
            )
            chrom.fitness = fitness
            chrom.optimized_instructions = optimized
            chrom.metrics = metrics

    # ---- genetic operators -----------------------------------------------------
    def _tournament_select(self, population: List[Chromosome]) -> Chromosome:
        contenders = random.sample(population, min(self.tournament_size, len(population)))
        return max(contenders, key=lambda c: c.fitness)

    def _crossover(self, parent1: Chromosome, parent2: Chromosome):
        """Single-point crossover: swap gene tails past a random cut point.
        Both parents are the same fixed length, so no length bookkeeping
        is needed -- the children are automatically the same length too."""
        if random.random() > self.crossover_rate:
            return parent1.copy(), parent2.copy()

        cut = random.randint(1, CHROMOSOME_LENGTH - 1)
        child1_genes = parent1.genes[:cut] + parent2.genes[cut:]
        child2_genes = parent2.genes[:cut] + parent1.genes[cut:]
        return Chromosome(genes=child1_genes), Chromosome(genes=child2_genes)

    def _mutate(self, chrom: Chromosome) -> Chromosome:
        """Point mutation: each gene independently has a chance to be
        replaced by a randomly chosen pass name."""
        genes = [
            random.choice(PASS_NAMES) if random.random() < self.mutation_rate else gene
            for gene in chrom.genes
        ]
        return Chromosome(genes=genes)

    def _next_generation(self, population: List[Chromosome]) -> List[Chromosome]:
        next_gen = []

        # Elitism: carry the fittest individuals forward untouched, so
        # the best-known fitness can never decrease across generations.
        for elite in population[: self.elitism_count]:
            clone = elite.copy()
            clone.fitness = elite.fitness
            clone.metrics = elite.metrics
            clone.optimized_instructions = elite.optimized_instructions
            next_gen.append(clone)

        while len(next_gen) < self.population_size:
            parent1 = self._tournament_select(population)
            parent2 = self._tournament_select(population)
            child1, child2 = self._crossover(parent1, parent2)
            child1 = self._mutate(child1)
            child2 = self._mutate(child2)
            next_gen.append(child1)
            if len(next_gen) < self.population_size:
                next_gen.append(child2)

        return next_gen

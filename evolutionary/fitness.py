"""
Fitness Function
----------------
Scores how "good" a candidate optimization sequence is when applied to
a specific program's TAC. This is the objective the Genetic Algorithm
maximizes.

STEP 1 -- Correctness gate (hard constraint)
    The optimized program is actually executed with the TAC
    interpreter (compiler/interpreter.py) and its `print()` output is
    compared against the original program's output. If they differ --
    or if applying the sequence or running the code raises any error
    (e.g. a pass produced malformed TAC, or an infinite loop) -- the
    sequence is semantically unsafe and is rejected outright with
    fitness = 0. This is what makes the search sound: no matter how
    much smaller the code gets, an incorrect transformation can never
    win.

STEP 2 -- Weighted improvement score (0-100 scale)
    For sequences that pass the correctness gate, fitness is a weighted
    sum of four normalized improvement ratios plus a small parsimony
    bonus that discourages needlessly long sequences:

        fitness = 100 * (
              0.35 * instruction_reduction
            + 0.25 * cost_reduction
            + 0.20 * operation_reduction
            + 0.10 * temp_variable_reduction
            + 0.10 * parsimony_bonus
        )

    Where:
      instruction_reduction = (orig_count - opt_count) / orig_count
          Fewer TAC instructions = smaller, simpler generated code.

      cost_reduction = (orig_cost - opt_cost) / orig_cost
          `estimate_cost` assigns a rough relative execution weight per
          instruction: multiply=3, divide=4, add/subtract/compare=2,
          everything else=1. This approximates runtime cost, not just
          static instruction count, so replacing a multiply with an
          add (Strength Reduction) is rewarded even when the
          instruction COUNT doesn't change.

      operation_reduction = (orig_binops - opt_binops) / orig_binops
          Rewards eliminating redundant computation specifically
          (constant folding, CSE, strength reduction all reduce this).

      temp_variable_reduction = (orig_temps - opt_temps) / orig_temps
          Fewer live temporaries approximates lower register pressure.

      parsimony_bonus = 1 / len(sequence)
          A mild preference for shorter, more efficient pass sequences
          over longer ones that reach the same result -- discourages
          the GA from padding chromosomes with no-op passes.

    All four ratios are clamped to [0, 1] before weighting (a sequence
    can never score below 0 for a single metric, e.g. if it happens to
    increase instruction count).
"""

import re

from optimizations import apply_pass_sequence
from compiler.interpreter import run_tac, TACRuntimeError

TEMP_PATTERN = re.compile(r"^t\d+$")

WEIGHTS = {
    "instruction_reduction": 0.35,
    "cost_reduction": 0.25,
    "operation_reduction": 0.20,
    "temp_reduction": 0.10,
    "parsimony": 0.10,
}

INSTRUCTION_COST = {
    "assign": 1,
    "print": 1,
    "goto": 1,
    "if_false_goto": 1,
    "label": 0,
}

# Binop cost is operator-specific: multiply/divide are modeled as more
# expensive than add/subtract/compare, which is what real hardware looks
# like and is what actually gives Strength Reduction (e.g. x*2 -> x+x)
# something to be rewarded for in the fitness score, even when it doesn't
# change the instruction count.
BINOP_COST = {
    "*": 3,
    "/": 4,
}
DEFAULT_BINOP_COST = 2  # +, -, and all relational operators


def _instruction_cost(instr):
    if instr.kind == "binop":
        return BINOP_COST.get(instr.op, DEFAULT_BINOP_COST)
    return INSTRUCTION_COST.get(instr.kind, 1)


def estimate_cost(instructions):
    return sum(_instruction_cost(instr) for instr in instructions)


def count_binops(instructions):
    return sum(1 for instr in instructions if instr.kind == "binop")


def count_temps(instructions):
    temps = {instr.dest for instr in instructions
             if instr.kind in ("assign", "binop") and instr.dest and TEMP_PATTERN.match(instr.dest)}
    return len(temps)


def _ratio(before, after):
    if before <= 0:
        return 0.0
    value = (before - after) / before
    return max(0.0, min(1.0, value))


def evaluate_fitness(original_instructions, sequence, original_output=None):
    """
    Returns (fitness_score: float, optimized_instructions, metrics: dict)

    `original_output` may be passed in (pre-computed once per GA run) to
    avoid re-interpreting the unmodified program for every chromosome.
    """
    if original_output is None:
        try:
            original_output = run_tac(original_instructions)
        except TACRuntimeError as exc:
            # The *original* program doesn't even run -- nothing to compare against.
            return 0.0, original_instructions, {"error": f"original program failed: {exc}"}

    if not sequence:
        return 0.0, original_instructions, {"error": "empty sequence"}

    try:
        optimized = apply_pass_sequence(original_instructions, sequence)
    except Exception as exc:  # a malformed/unsafe pass application
        return 0.0, original_instructions, {"error": f"pass application failed: {exc}"}

    try:
        optimized_output = run_tac(optimized)
    except TACRuntimeError as exc:
        return 0.0, original_instructions, {"error": f"optimized program failed to run: {exc}"}

    if optimized_output != original_output:
        return 0.0, original_instructions, {
            "error": "semantics changed: optimized output differs from original output",
            "original_output": original_output,
            "optimized_output": optimized_output,
        }

    orig_count = len(original_instructions)
    opt_count = len(optimized)

    orig_cost = estimate_cost(original_instructions)
    opt_cost = estimate_cost(optimized)

    orig_ops = count_binops(original_instructions)
    opt_ops = count_binops(optimized)

    orig_temps = count_temps(original_instructions)
    opt_temps = count_temps(optimized)

    instruction_reduction = _ratio(orig_count, opt_count)
    cost_reduction = _ratio(orig_cost, opt_cost)
    operation_reduction = _ratio(orig_ops, opt_ops) if orig_ops else 0.0
    temp_reduction = _ratio(orig_temps, opt_temps) if orig_temps else 0.0
    parsimony = 1.0 / len(sequence)

    fitness = 100.0 * (
        WEIGHTS["instruction_reduction"] * instruction_reduction
        + WEIGHTS["cost_reduction"] * cost_reduction
        + WEIGHTS["operation_reduction"] * operation_reduction
        + WEIGHTS["temp_reduction"] * temp_reduction
        + WEIGHTS["parsimony"] * parsimony
    )

    metrics = {
        "instruction_count_before": orig_count,
        "instruction_count_after": opt_count,
        "cost_before": orig_cost,
        "cost_after": opt_cost,
        "binop_count_before": orig_ops,
        "binop_count_after": opt_ops,
        "temp_count_before": orig_temps,
        "temp_count_after": opt_temps,
        "instruction_reduction_pct": round(instruction_reduction * 100, 2),
        "cost_reduction_pct": round(cost_reduction * 100, 2),
        "operation_reduction_pct": round(operation_reduction * 100, 2),
        "temp_reduction_pct": round(temp_reduction * 100, 2),
        "sequence_length": len(sequence),
        "fitness": round(fitness, 3),
    }

    return fitness, optimized, metrics

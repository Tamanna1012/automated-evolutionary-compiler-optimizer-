"""
Fitness Function
----------------
Scores how "good" a candidate optimization sequence is when applied to
a specific program's TAC. This is the objective the Genetic Algorithm
maximizes. Kept deliberately simple: two ideas, in plain language.

STEP 1 -- Correctness gate ("did we break the program?")
    The optimized program is actually executed with the TAC
    interpreter (compiler/interpreter.py) and its `print()` output is
    compared against the original program's output. If they differ --
    or the sequence errors out, or the optimized program fails to run
    -- the sequence is unsafe and is rejected outright: fitness = 0.
    No matter how much smaller the code got, an incorrect
    transformation can never win.

STEP 2 -- Weighted improvement score ("how much smaller/cheaper?")
    For sequences that pass the gate:

        fitness = 100 * (0.7 * instruction_reduction + 0.3 * cost_reduction)

      instruction_reduction = (instructions before - instructions after) / instructions before
          The main signal: fewer TAC instructions after optimization.

      cost_reduction = (cost before - cost after) / cost before
          A slightly more realistic version of the same idea: every
          arithmetic/comparison instruction ("binop") costs 2 units,
          everything else costs 1. This is what lets a program with
          the SAME instruction count still score higher if it replaced
          some computation with a cheaper one.

    Instruction count gets the bigger weight (0.7) because it is the
    easiest number to point at and explain; cost is a smaller (0.3)
    tie-breaker on top of it. Both ratios are clamped to [0, 1] so a
    sequence can never score below 0 on either term.
"""

from optimizations import apply_pass_sequence
from compiler.interpreter import run_tac, TACRuntimeError

INSTRUCTION_REDUCTION_WEIGHT = 0.7
COST_REDUCTION_WEIGHT = 0.3

BINOP_COST = 2
OTHER_COST = 1


def estimate_cost(instructions):
    return sum(BINOP_COST if instr.kind == "binop" else OTHER_COST for instr in instructions)


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

    instruction_reduction = _ratio(orig_count, opt_count)
    cost_reduction = _ratio(orig_cost, opt_cost)

    fitness = 100.0 * (
        INSTRUCTION_REDUCTION_WEIGHT * instruction_reduction
        + COST_REDUCTION_WEIGHT * cost_reduction
    )

    metrics = {
        "instruction_count_before": orig_count,
        "instruction_count_after": opt_count,
        "cost_before": orig_cost,
        "cost_after": opt_cost,
        "instruction_reduction_pct": round(instruction_reduction * 100, 2),
        "cost_reduction_pct": round(cost_reduction * 100, 2),
        "sequence_length": len(sequence),
        "fitness": round(fitness, 3),
    }

    return fitness, optimized, metrics

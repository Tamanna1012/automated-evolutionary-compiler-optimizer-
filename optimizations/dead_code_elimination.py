"""
Dead Code Elimination (DCE)
----------------------------
Removes instructions whose result is never used anywhere in the
program. Because this toy language has no external I/O other than
`print(...)`, `print` instructions are the only genuine "roots" of
liveness -- a computation only matters if it (transitively) feeds a
print statement, a branch condition, or another still-live computation.

Algorithm: global use-set fixed-point iteration.
    1. Collect the set of variable names used as an operand by ANY
       currently-remaining instruction (binop / assign / if_false_goto
       / print).
    2. Drop any `assign`/`binop` instruction whose destination variable
       is not in that use-set.
    3. Repeat, because removing one dead instruction can make the
       instructions that fed it dead too (cascading elimination) --
       until a pass removes nothing.

Control-flow instructions (label / goto / if_false_goto) are never
removed by this pass -- unreachable-code elimination is a distinct
optimization and is left as a documented future improvement.
"""

from compiler.intermediate_code import clone_instructions


class DeadCodeElimination:
    name = "DeadCodeElimination"

    def apply(self, instructions):
        current = clone_instructions(instructions)
        total_removed = 0

        while True:
            used = set()
            for instr in current:
                used.update(instr.uses())

            kept = []
            removed_this_round = 0
            for instr in current:
                if instr.kind in ("assign", "binop") and instr.dest not in used:
                    removed_this_round += 1
                    continue
                kept.append(instr)

            current = kept
            total_removed += removed_this_round
            if removed_this_round == 0:
                break

        self.changes = total_removed
        return current

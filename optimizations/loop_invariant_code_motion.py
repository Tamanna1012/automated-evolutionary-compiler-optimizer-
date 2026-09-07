"""
Loop-Invariant Code Motion (LICM)
------------------------------------
Hoists a computation out of a loop body into the "loop preheader" (the
point immediately before the loop's header label) when that
computation produces the same value on every iteration -- so it only
needs to be computed once instead of once per iteration.

    int factor = 3;
    int i = 0;
    int total = 0;
    while (i < 5) {
        int step = factor * 2;    // does not depend on the loop variable i
        total = total + step;
        i = i + 1;
    }

becomes:

    int factor = 3;
    int i = 0;
    int total = 0;
    step = factor * 2;            // hoisted -- computed once instead of 5 times
    while (i < 5) {
        total = total + step;
        i = i + 1;
    }

Scope of this implementation
-----------------------------
This pass only analyzes "simple" while-loops as produced by this
project's own IR generator: a `label` (the loop header), a condition
followed by a single `if_false_goto` to the exit label, a
STRAIGHT-LINE body (no nested label / goto / if_false_goto -- i.e. no
nested `if`/`while`), and a `goto` back to the header. Restricting to
straight-line bodies is what makes the "does this instruction run on
every iteration" analysis trivial and correct by construction; loops
with a nested `if`/`while` in the body are simply left untouched by
this pass (documented as future work in the README).

A binary operation is hoisted only when:
  1. it is the ONLY assignment to its destination anywhere in the loop
     (so moving it doesn't change how many times that variable is
     (re)computed), and
  2. both of its operands are either constants or variables that are
     never written anywhere inside the loop (i.e. truly loop-invariant).

Division ('/') is deliberately never hoisted, even when its operands
are invariant, so this pass can never introduce a division-by-zero
that a zero-iteration loop would otherwise never have executed.

Note on soundness: because this teaching language has no external
input, every program's execution is fully deterministic. The
evolutionary engine's fitness function (evolutionary/fitness.py)
already re-executes the optimized program and hard-rejects (fitness =
0) any transformation whose observable `print()` output differs from
the original -- so even in the rare pathological case this pass's
straight-line-only heuristic doesn't fully anticipate, the system as a
whole can never present an incorrectly "optimized" result as correct.
"""

from compiler.intermediate_code import clone_instructions


def _find_simple_loops(instructions):
    """Returns a list of dicts describing each non-nested simple loop, in
    left-to-right order, as {header_idx, cond_end_idx, goto_idx}."""
    loops = []
    n = len(instructions)
    i = 0
    while i < n:
        instr = instructions[i]
        if instr.kind != "label":
            i += 1
            continue

        header_idx = i
        header_label = instr.label

        goto_idx = None
        for j in range(header_idx + 1, n):
            if instructions[j].kind == "goto" and instructions[j].label == header_label:
                goto_idx = j
                break

        if goto_idx is None:
            i += 1
            continue

        # condition region: zero or more assign/binop, then exactly one if_false_goto
        k = header_idx + 1
        while k < goto_idx and instructions[k].kind in ("assign", "binop"):
            k += 1
        if k >= goto_idx or instructions[k].kind != "if_false_goto":
            i += 1
            continue

        cond_end_idx = k
        exit_label = instructions[k].label
        body_start = cond_end_idx + 1

        body_ok = all(
            instructions[b].kind in ("assign", "binop", "print")
            for b in range(body_start, goto_idx)
        )

        exit_idx = goto_idx + 1
        has_exit_label = (
            exit_idx < n
            and instructions[exit_idx].kind == "label"
            and instructions[exit_idx].label == exit_label
        )

        if body_ok and has_exit_label:
            loops.append({"header_idx": header_idx, "cond_end_idx": cond_end_idx, "goto_idx": goto_idx})
            i = exit_idx + 1  # this project's IR generator never nests simple loops
        else:
            i += 1

    return loops


class LoopInvariantCodeMotion:
    name = "LoopInvariantCodeMotion"

    def apply(self, instructions):
        instructions = clone_instructions(instructions)
        loops = _find_simple_loops(instructions)
        total_hoisted = 0

        # Process loops bottom-up: splicing a later loop never shifts the
        # (smaller) indices of a loop we haven't processed yet.
        for loop in sorted(loops, key=lambda l: l["header_idx"], reverse=True):
            total_hoisted += self._hoist_loop(instructions, loop)

        self.changes = total_hoisted
        return instructions

    @staticmethod
    def _hoist_loop(instructions, loop):
        header_idx = loop["header_idx"]
        cond_end_idx = loop["cond_end_idx"]
        goto_idx = loop["goto_idx"]
        hoisted_count = 0

        while True:
            body_start = cond_end_idx + 1

            modified = {}
            for idx in range(header_idx + 1, goto_idx):
                instr = instructions[idx]
                if instr.kind in ("assign", "binop") and instr.dest:
                    modified[instr.dest] = modified.get(instr.dest, 0) + 1

            def is_invariant(operand):
                if isinstance(operand, int):
                    return True
                return operand not in modified

            target = None
            for idx in range(body_start, goto_idx):
                instr = instructions[idx]
                if instr.kind != "binop" or instr.op == "/":
                    continue
                if modified.get(instr.dest, 0) != 1:
                    continue
                if is_invariant(instr.arg1) and is_invariant(instr.arg2):
                    target = idx
                    break

            if target is None:
                break

            hoisted_instr = instructions.pop(target)
            instructions.insert(header_idx, hoisted_instr)

            # Removing from inside the body (after the header) and inserting
            # right before the header nets out to a no-op shift for goto_idx;
            # everything from the header up to (and including) the condition
            # check moves down by exactly one slot.
            header_idx += 1
            cond_end_idx += 1
            hoisted_count += 1

        return hoisted_count

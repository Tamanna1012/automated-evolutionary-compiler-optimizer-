"""
Constant Propagation
--------------------
Tracks which variables are known to currently hold a compile-time
constant value and substitutes that constant directly into later
instructions that read the variable.

    a = 10
    b = a + 5     -->     b = 10 + 5      (then ConstantFolding can fold it to 15)

This pass only *substitutes* known constants into operand positions; it
deliberately does not also perform the arithmetic itself (that is
ConstantFolding's job). Keeping the two passes separate is what makes
pass *ordering* matter -- propagation before folding is far more
effective than folding alone, which is exactly the phase-ordering
problem this project's genetic algorithm is built to explore.

Known-constant facts are conservatively cleared at every label, since a
label is a possible join point for control flow (e.g. the target of a
loop back-edge) where we cannot statically know which value reaches it.
"""

from compiler.intermediate_code import clone_instructions


class ConstantPropagation:
    name = "ConstantPropagation"

    def apply(self, instructions):
        instructions = clone_instructions(instructions)
        constants = {}
        changed = 0

        for instr in instructions:
            if instr.kind == "label":
                constants.clear()
                continue

            if instr.kind == "assign":
                if isinstance(instr.arg1, str) and instr.arg1 in constants:
                    instr.arg1 = constants[instr.arg1]
                    changed += 1
                if isinstance(instr.arg1, int):
                    constants[instr.dest] = instr.arg1
                else:
                    constants.pop(instr.dest, None)

            elif instr.kind == "binop":
                if isinstance(instr.arg1, str) and instr.arg1 in constants:
                    instr.arg1 = constants[instr.arg1]
                    changed += 1
                if isinstance(instr.arg2, str) and instr.arg2 in constants:
                    instr.arg2 = constants[instr.arg2]
                    changed += 1
                constants.pop(instr.dest, None)

            elif instr.kind in ("if_false_goto", "print"):
                if isinstance(instr.arg1, str) and instr.arg1 in constants:
                    instr.arg1 = constants[instr.arg1]
                    changed += 1

        self.changes = changed
        return instructions

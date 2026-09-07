"""
Copy Propagation
----------------
When one variable is a plain copy of another ("a = b"), later uses of
the copy's target can be replaced by the original variable, which often
lets Dead Code Elimination remove the copy instruction entirely.

    a = b
    c = a + 5      -->     c = b + 5

A forward dataflow map `copies: var -> var` records simple copy facts.
Whenever a variable is redefined (by any kind of instruction), any
fact that mentions it -- as source or as target -- is invalidated,
which is what keeps this transformation safe.
"""

from compiler.intermediate_code import clone_instructions


class CopyPropagation:
    name = "CopyPropagation"

    def apply(self, instructions):
        instructions = clone_instructions(instructions)
        copies = {}
        changed = 0

        def resolve(operand):
            nonlocal changed
            if isinstance(operand, str) and operand in copies:
                changed += 1
                return copies[operand]
            return operand

        def invalidate(var):
            copies.pop(var, None)
            for k in [k for k, v in copies.items() if v == var]:
                copies.pop(k, None)

        for instr in instructions:
            if instr.kind == "label":
                copies.clear()
                continue

            if instr.kind == "assign":
                instr.arg1 = resolve(instr.arg1)
                invalidate(instr.dest)
                if isinstance(instr.arg1, str):
                    copies[instr.dest] = instr.arg1

            elif instr.kind == "binop":
                instr.arg1 = resolve(instr.arg1)
                instr.arg2 = resolve(instr.arg2)
                invalidate(instr.dest)

            elif instr.kind in ("if_false_goto", "print"):
                instr.arg1 = resolve(instr.arg1)

        self.changes = changed
        return instructions

"""
Strength Reduction
------------------
Replaces an expensive operation with a cheaper equivalent one:

    x = a * 2      -->     x = a + a     (multiply replaced by an add)
    x = a * 1      -->     x = a         (identity)
    x = a * 0      -->     x = 0
    x = a / 1      -->     x = a         (identity)

Only safe, value-preserving rewrites for integer arithmetic are
applied. The multiply-by-2 case is the classic textbook example of
strength reduction (a single addition is cheaper than a multiply on
most real hardware); the identity/zero cases are simple special-case
simplifications bundled into the same pass since they share the same
"look at a binop with a constant operand" shape.
"""

from compiler.intermediate_code import Instruction, clone_instructions


class StrengthReduction:
    name = "StrengthReduction"

    def apply(self, instructions):
        instructions = clone_instructions(instructions)
        result = []
        changed = 0

        for instr in instructions:
            if instr.kind != "binop":
                result.append(instr)
                continue

            new_instr = self._reduce(instr)
            if new_instr is not None:
                result.append(new_instr)
                changed += 1
            else:
                result.append(instr)

        self.changes = changed
        return result

    @staticmethod
    def _reduce(instr: Instruction):
        op, a1, a2, dest = instr.op, instr.arg1, instr.arg2, instr.dest

        if op == "*":
            # constant on the right: a1 * a2
            if isinstance(a2, int):
                if a2 == 2:
                    return Instruction("binop", dest=dest, op="+", arg1=a1, arg2=a1)
                if a2 == 1:
                    return Instruction("assign", dest=dest, arg1=a1)
                if a2 == 0:
                    return Instruction("assign", dest=dest, arg1=0)
            # constant on the left: a1 * a2
            if isinstance(a1, int):
                if a1 == 2:
                    return Instruction("binop", dest=dest, op="+", arg1=a2, arg2=a2)
                if a1 == 1:
                    return Instruction("assign", dest=dest, arg1=a2)
                if a1 == 0:
                    return Instruction("assign", dest=dest, arg1=0)

        if op == "/":
            if isinstance(a2, int) and a2 == 1:
                return Instruction("assign", dest=dest, arg1=a1)

        return None

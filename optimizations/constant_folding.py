"""
Constant Folding
----------------
If a binary operation's two operands are BOTH known constants at
compile time, evaluate the operation now and replace it with a plain
assignment.

    t1 = 5 + 10        -->     t1 = 15

Division by zero is left untouched (the expression is not folded) so
that we never bake a crash into "optimized" code; the interpreter will
raise a runtime error if that path is ever actually executed, which is
correct behavior to preserve.
"""

from compiler.intermediate_code import Instruction, clone_instructions


class ConstantFolding:
    name = "ConstantFolding"

    def apply(self, instructions):
        instructions = clone_instructions(instructions)
        result = []
        changed = 0

        for instr in instructions:
            if (
                instr.kind == "binop"
                and isinstance(instr.arg1, int)
                and isinstance(instr.arg2, int)
            ):
                folded = self._fold(instr.op, instr.arg1, instr.arg2)
                if folded is not None:
                    result.append(Instruction("assign", dest=instr.dest, arg1=folded))
                    changed += 1
                    continue
            result.append(instr)

        self.changes = changed
        return result

    @staticmethod
    def _fold(op, a, b):
        try:
            if op == "+":
                return a + b
            if op == "-":
                return a - b
            if op == "*":
                return a * b
            if op == "/":
                if b == 0:
                    return None
                q = abs(a) // abs(b)
                return q if (a < 0) == (b < 0) else -q
            if op == "<":
                return 1 if a < b else 0
            if op == ">":
                return 1 if a > b else 0
            if op == "<=":
                return 1 if a <= b else 0
            if op == ">=":
                return 1 if a >= b else 0
            if op == "==":
                return 1 if a == b else 0
            if op == "!=":
                return 1 if a != b else 0
        except ArithmeticError:
            return None
        return None

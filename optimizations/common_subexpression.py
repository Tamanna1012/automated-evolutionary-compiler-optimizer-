"""
Common Subexpression Elimination (CSE)
---------------------------------------
If the exact same expression (same operator, same operands) has already
been computed earlier in the current basic block and none of its
operands have been redefined since, reuse the previously-computed
value instead of recomputing it.

    x = a + b
    y = a + b       -->     y = x

Commutative operators (+ and *) are normalized (operands sorted) so
that "a + b" and "b + a" are recognized as the same expression.

The set of "available expressions" is reset at every label (a new
basic block) and any expression depending on a variable is invalidated
the moment that variable is redefined -- both are required for this
pass to be safe in the presence of branches and loops.
"""

from compiler.intermediate_code import Instruction, clone_instructions

COMMUTATIVE = {"+", "*"}


class CommonSubexpressionElimination:
    name = "CommonSubexpressionElimination"

    def apply(self, instructions):
        instructions = clone_instructions(instructions)
        available = {}   # (op, arg1, arg2) -> variable holding the result
        result = []
        changed = 0

        def make_key(op, a1, a2):
            if op in COMMUTATIVE:
                pair = tuple(sorted((repr(a1), repr(a2))))
                return (op, pair)
            return (op, a1, a2)

        def touches(key, var):
            if len(key) == 2:  # commutative: (op, (repr(a1), repr(a2)))
                return repr(var) in key[1]
            return key[1] == var or key[2] == var

        for instr in instructions:
            if instr.kind == "label":
                available.clear()
                result.append(instr)
                continue

            if instr.kind == "binop":
                key = make_key(instr.op, instr.arg1, instr.arg2)
                if key in available:
                    result.append(Instruction("assign", dest=instr.dest, arg1=available[key]))
                    changed += 1
                else:
                    available[key] = instr.dest
                    result.append(instr)
                # This instruction (re)defines instr.dest, so any cached
                # expression -- including the one we may have just stored --
                # that reads the OLD value of instr.dest is now stale.
                # (Handles self-referential ops like "a = a + b" correctly:
                # the freshly-inserted entry gets dropped again immediately.)
                for k in [k for k in available if touches(k, instr.dest)]:
                    available.pop(k, None)
                continue

            if instr.kind == "assign":
                for k in [k for k in available if touches(k, instr.dest)]:
                    available.pop(k, None)
                result.append(instr)
                continue

            result.append(instr)

        self.changes = changed
        return result

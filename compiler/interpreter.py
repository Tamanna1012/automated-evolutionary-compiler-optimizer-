"""
A minimal Three-Address-Code interpreter.

This is NOT part of a traditional compiler pipeline -- it exists purely
as a *correctness oracle*. Before the evolutionary engine is allowed to
accept an optimization sequence, it actually executes both the original
TAC and the optimized TAC and compares their `print()` output. If the
outputs differ, the sequence produced semantically incorrect code and is
rejected (fitness = 0). This is what guarantees the GA can never "cheat"
by discovering a sequence that shrinks the code but changes its meaning.
"""

from typing import List
from .intermediate_code import Instruction


class TACRuntimeError(Exception):
    pass


def _compute(op, a, b):
    if op == "+":
        return a + b
    if op == "-":
        return a - b
    if op == "*":
        return a * b
    if op == "/":
        if b == 0:
            raise TACRuntimeError("division by zero")
        # integer division, truncating toward zero (like C)
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
    raise TACRuntimeError(f"unknown operator '{op}'")


def run_tac(instructions: List[Instruction], max_steps: int = 200_000) -> List[int]:
    """Executes a TAC program and returns the list of values passed to print()."""
    env = {}
    output = []

    label_index = {
        instr.label: idx for idx, instr in enumerate(instructions) if instr.kind == "label"
    }

    def value_of(operand):
        if isinstance(operand, int):
            return operand
        if operand in env:
            return env[operand]
        raise TACRuntimeError(f"use of undefined variable '{operand}'")

    pc = 0
    steps = 0
    while pc < len(instructions):
        steps += 1
        if steps > max_steps:
            raise TACRuntimeError(
                "execution step limit exceeded (possible infinite loop in source program)"
            )

        instr = instructions[pc]

        if instr.kind == "label":
            pc += 1
        elif instr.kind == "goto":
            if instr.label not in label_index:
                raise TACRuntimeError(f"undefined label '{instr.label}'")
            pc = label_index[instr.label]
        elif instr.kind == "if_false_goto":
            cond = value_of(instr.arg1)
            if cond == 0:
                if instr.label not in label_index:
                    raise TACRuntimeError(f"undefined label '{instr.label}'")
                pc = label_index[instr.label]
            else:
                pc += 1
        elif instr.kind == "assign":
            env[instr.dest] = value_of(instr.arg1)
            pc += 1
        elif instr.kind == "binop":
            a = value_of(instr.arg1)
            b = value_of(instr.arg2)
            env[instr.dest] = _compute(instr.op, a, b)
            pc += 1
        elif instr.kind == "print":
            output.append(value_of(instr.arg1))
            pc += 1
        else:
            raise TACRuntimeError(f"unknown instruction kind '{instr.kind}'")

    return output

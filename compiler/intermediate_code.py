"""
Intermediate Representation: Three-Address Code (TAC)
-------------------------------------------------------
This is Phase 3 of the compiler pipeline. Every optimization pass and
the genetic algorithm operate exclusively on lists of `Instruction`
objects defined here -- this shared representation is what makes the
optimization passes composable and reorderable.

Instruction kinds:
    assign        dest = arg1                     (arg1: var name or int constant)
    binop         dest = arg1 <op> arg2            (arg1/arg2: var name or int constant)
    label         L<k>:                            (jump target, marks a basic-block start)
    goto          goto L<k>
    if_false_goto if arg1 == 0 goto L<k>
    print         print(arg1)

A variable reference is a Python `str`; a constant is a Python `int`.
This makes "is this operand a constant?" a simple `isinstance` check,
which every optimization pass relies on.
"""

from dataclasses import dataclass
from typing import Optional, Union, List
import copy as _copy

from .ast_nodes import Program, VarDecl, Assign, Print, If, While, BinOp, UnaryOp, Num, Var

Operand = Union[str, int]


@dataclass
class Instruction:
    kind: str
    dest: Optional[str] = None
    op: Optional[str] = None
    arg1: Optional[Operand] = None
    arg2: Optional[Operand] = None
    label: Optional[str] = None

    def uses(self) -> List[str]:
        """Variable names read (not written) by this instruction."""
        result = []
        if self.kind in ("assign",):
            if isinstance(self.arg1, str):
                result.append(self.arg1)
        elif self.kind == "binop":
            if isinstance(self.arg1, str):
                result.append(self.arg1)
            if isinstance(self.arg2, str):
                result.append(self.arg2)
        elif self.kind in ("if_false_goto", "print"):
            if isinstance(self.arg1, str):
                result.append(self.arg1)
        return result

    def defines(self) -> Optional[str]:
        """Variable name written by this instruction, if any."""
        if self.kind in ("assign", "binop"):
            return self.dest
        return None

    def clone(self):
        return _copy.copy(self)

    def __str__(self):
        if self.kind == "assign":
            return f"{self.dest} = {self.arg1}"
        if self.kind == "binop":
            return f"{self.dest} = {self.arg1} {self.op} {self.arg2}"
        if self.kind == "label":
            return f"{self.label}:"
        if self.kind == "goto":
            return f"goto {self.label}"
        if self.kind == "if_false_goto":
            return f"if_false {self.arg1} goto {self.label}"
        if self.kind == "print":
            return f"print({self.arg1})"
        return f"<unknown:{self.kind}>"


def clone_instructions(instructions: List[Instruction]) -> List[Instruction]:
    return [i.clone() for i in instructions]


class IRGenerator:
    """Walks the AST and emits a flat list of TAC Instruction objects."""

    def __init__(self):
        self.instructions: List[Instruction] = []
        self._temp_count = 0
        self._label_count = 0

    def _new_temp(self) -> str:
        self._temp_count += 1
        return f"t{self._temp_count}"

    def _new_label(self) -> str:
        self._label_count += 1
        return f"L{self._label_count}"

    def _emit(self, instr: Instruction):
        self.instructions.append(instr)

    def generate(self, program: Program) -> List[Instruction]:
        self.instructions = []
        self._temp_count = 0
        self._label_count = 0
        for stmt in program.statements:
            self._gen_stmt(stmt)
        return self.instructions

    # ---- statements --------------------------------------------------------
    def _gen_stmt(self, node):
        if isinstance(node, VarDecl):
            value = self._gen_expr(node.expr)
            self._emit(Instruction("assign", dest=node.name, arg1=value))
        elif isinstance(node, Assign):
            value = self._gen_expr(node.expr)
            self._emit(Instruction("assign", dest=node.name, arg1=value))
        elif isinstance(node, Print):
            value = self._gen_expr(node.expr)
            self._emit(Instruction("print", arg1=value))
        elif isinstance(node, If):
            self._gen_if(node)
        elif isinstance(node, While):
            self._gen_while(node)
        else:
            raise TypeError(f"Unknown statement node: {type(node).__name__}")

    def _gen_if(self, node: If):
        cond_val = self._gen_expr(node.cond)
        l_else = self._new_label()
        l_end = self._new_label()

        self._emit(Instruction("if_false_goto", arg1=cond_val, label=l_else))
        for stmt in node.then_body:
            self._gen_stmt(stmt)
        self._emit(Instruction("goto", label=l_end))
        self._emit(Instruction("label", label=l_else))
        for stmt in node.else_body:
            self._gen_stmt(stmt)
        self._emit(Instruction("label", label=l_end))

    def _gen_while(self, node: While):
        l_start = self._new_label()
        l_end = self._new_label()

        self._emit(Instruction("label", label=l_start))
        cond_val = self._gen_expr(node.cond)
        self._emit(Instruction("if_false_goto", arg1=cond_val, label=l_end))
        for stmt in node.body:
            self._gen_stmt(stmt)
        self._emit(Instruction("goto", label=l_start))
        self._emit(Instruction("label", label=l_end))

    # ---- expressions --------------------------------------------------------
    def _gen_expr(self, node) -> Operand:
        """Returns an Operand (variable name or int constant) holding the value."""
        if isinstance(node, Num):
            return node.value
        if isinstance(node, Var):
            return node.name
        if isinstance(node, UnaryOp):
            operand = self._gen_expr(node.operand)
            temp = self._new_temp()
            self._emit(Instruction("binop", dest=temp, op="-", arg1=0, arg2=operand))
            return temp
        if isinstance(node, BinOp):
            left = self._gen_expr(node.left)
            right = self._gen_expr(node.right)
            temp = self._new_temp()
            self._emit(Instruction("binop", dest=temp, op=node.op, arg1=left, arg2=right))
            return temp
        raise TypeError(f"Unknown expression node: {type(node).__name__}")


def tac_to_lines(instructions: List[Instruction]) -> List[str]:
    return [str(instr) for instr in instructions]

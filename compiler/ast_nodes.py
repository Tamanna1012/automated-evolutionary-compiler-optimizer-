"""
Abstract Syntax Tree (AST) node definitions.

Each node is a lightweight class. The parser builds a tree of these
objects; the IR generator walks the tree to emit Three-Address Code.
"""


class Node:
    """Base class purely for isinstance() checks and a shared repr."""

    def to_dict(self):
        raise NotImplementedError


class Program(Node):
    def __init__(self, statements):
        self.statements = statements

    def to_dict(self):
        return {"node": "Program", "children": [s.to_dict() for s in self.statements]}


class VarDecl(Node):
    """int <name> = <expr>;"""

    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

    def to_dict(self):
        return {
            "node": "VarDecl",
            "name": self.name,
            "children": [self.expr.to_dict()],
        }


class Assign(Node):
    """<name> = <expr>;"""

    def __init__(self, name, expr):
        self.name = name
        self.expr = expr

    def to_dict(self):
        return {
            "node": "Assign",
            "name": self.name,
            "children": [self.expr.to_dict()],
        }


class Print(Node):
    """print(<expr>);"""

    def __init__(self, expr):
        self.expr = expr

    def to_dict(self):
        return {"node": "Print", "children": [self.expr.to_dict()]}


class If(Node):
    def __init__(self, cond, then_body, else_body=None):
        self.cond = cond
        self.then_body = then_body      # list of statements
        self.else_body = else_body or []  # list of statements

    def to_dict(self):
        return {
            "node": "If",
            "children": [
                {"node": "Condition", "children": [self.cond.to_dict()]},
                {"node": "Then", "children": [s.to_dict() for s in self.then_body]},
                {"node": "Else", "children": [s.to_dict() for s in self.else_body]},
            ],
        }


class While(Node):
    def __init__(self, cond, body):
        self.cond = cond
        self.body = body

    def to_dict(self):
        return {
            "node": "While",
            "children": [
                {"node": "Condition", "children": [self.cond.to_dict()]},
                {"node": "Body", "children": [s.to_dict() for s in self.body]},
            ],
        }


class BinOp(Node):
    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right

    def to_dict(self):
        return {
            "node": f"BinOp({self.op})",
            "children": [self.left.to_dict(), self.right.to_dict()],
        }


class UnaryOp(Node):
    def __init__(self, op, operand):
        self.op = op
        self.operand = operand

    def to_dict(self):
        return {"node": f"UnaryOp({self.op})", "children": [self.operand.to_dict()]}


class Num(Node):
    def __init__(self, value):
        self.value = int(value)

    def to_dict(self):
        return {"node": f"Num({self.value})", "children": []}


class Var(Node):
    def __init__(self, name):
        self.name = name

    def to_dict(self):
        return {"node": f"Var({self.name})", "children": []}

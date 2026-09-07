"""
Parser (Syntax Analysis)
------------------------
A hand-written recursive-descent parser for the simplified language.
Builds an Abstract Syntax Tree (AST) from the token stream produced by
the Lexer. This is Phase 2 of the compiler pipeline.

Grammar (EBNF):

    program     := statement*
    statement   := decl_stmt | assign_stmt | if_stmt | while_stmt | print_stmt
    decl_stmt   := 'int' IDENT '=' expr ';'
    assign_stmt := IDENT '=' expr ';'
    print_stmt  := 'print' '(' expr ')' ';'
    if_stmt     := 'if' '(' expr ')' block ('else' block)?
    while_stmt  := 'while' '(' expr ')' block
    block       := '{' statement* '}'

    expr        := comparison
    comparison  := addsub (('<'|'>'|'<='|'>='|'=='|'!=') addsub)?
    addsub      := term (('+'|'-') term)*
    term        := unary (('*'|'/') unary)*
    unary       := '-' unary | primary
    primary     := NUMBER | IDENT | '(' expr ')'
"""

from .ast_nodes import Program, VarDecl, Assign, Print, If, While, BinOp, UnaryOp, Num, Var

COMPARISON_OPS = {"LT", "GT", "LE", "GE", "EQ", "NE"}
OP_SYMBOL = {
    "LT": "<", "GT": ">", "LE": "<=", "GE": ">=", "EQ": "==", "NE": "!=",
    "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/",
}


class ParserError(Exception):
    pass


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    # ---- token stream helpers ------------------------------------------------
    def _peek(self):
        return self.tokens[self.pos]

    def _advance(self):
        tok = self.tokens[self.pos]
        if tok.type != "EOF":
            self.pos += 1
        return tok

    def _check(self, ttype, value=None):
        tok = self._peek()
        if tok.type != ttype:
            return False
        if value is not None and tok.value != value:
            return False
        return True

    def _expect(self, ttype, value=None):
        if not self._check(ttype, value):
            tok = self._peek()
            expected = value if value is not None else ttype
            raise ParserError(
                f"Expected '{expected}' but found '{tok.value or tok.type}' "
                f"at line {tok.line}, column {tok.col}"
            )
        return self._advance()

    # ---- entry point -----------------------------------------------------
    def parse(self):
        statements = []
        while not self._check("EOF"):
            statements.append(self._statement())
        return Program(statements)

    # ---- statements --------------------------------------------------------
    def _block(self):
        self._expect("LBRACE")
        stmts = []
        while not self._check("RBRACE"):
            stmts.append(self._statement())
        self._expect("RBRACE")
        return stmts

    def _statement(self):
        tok = self._peek()

        if tok.type == "KEYWORD" and tok.value == "int":
            return self._decl_stmt()
        if tok.type == "KEYWORD" and tok.value == "if":
            return self._if_stmt()
        if tok.type == "KEYWORD" and tok.value == "while":
            return self._while_stmt()
        if tok.type == "KEYWORD" and tok.value == "print":
            return self._print_stmt()
        if tok.type == "IDENT":
            return self._assign_stmt()

        raise ParserError(
            f"Unexpected token '{tok.value or tok.type}' at line {tok.line}, column {tok.col}"
        )

    def _decl_stmt(self):
        self._expect("KEYWORD", "int")
        name_tok = self._expect("IDENT")
        self._expect("ASSIGN")
        expr = self._expr()
        self._expect("SEMI")
        return VarDecl(name_tok.value, expr)

    def _assign_stmt(self):
        name_tok = self._expect("IDENT")
        self._expect("ASSIGN")
        expr = self._expr()
        self._expect("SEMI")
        return Assign(name_tok.value, expr)

    def _print_stmt(self):
        self._expect("KEYWORD", "print")
        self._expect("LPAREN")
        expr = self._expr()
        self._expect("RPAREN")
        self._expect("SEMI")
        return Print(expr)

    def _if_stmt(self):
        self._expect("KEYWORD", "if")
        self._expect("LPAREN")
        cond = self._expr()
        self._expect("RPAREN")
        then_body = self._block()
        else_body = []
        if self._check("KEYWORD", "else"):
            self._advance()
            else_body = self._block()
        return If(cond, then_body, else_body)

    def _while_stmt(self):
        self._expect("KEYWORD", "while")
        self._expect("LPAREN")
        cond = self._expr()
        self._expect("RPAREN")
        body = self._block()
        return While(cond, body)

    # ---- expressions (precedence climbing) --------------------------------
    def _expr(self):
        return self._comparison()

    def _comparison(self):
        left = self._addsub()
        if self._peek().type in COMPARISON_OPS:
            op_tok = self._advance()
            right = self._addsub()
            left = BinOp(OP_SYMBOL[op_tok.type], left, right)
        return left

    def _addsub(self):
        left = self._term()
        while self._peek().type in ("PLUS", "MINUS"):
            op_tok = self._advance()
            right = self._term()
            left = BinOp(OP_SYMBOL[op_tok.type], left, right)
        return left

    def _term(self):
        left = self._unary()
        while self._peek().type in ("STAR", "SLASH"):
            op_tok = self._advance()
            right = self._unary()
            left = BinOp(OP_SYMBOL[op_tok.type], left, right)
        return left

    def _unary(self):
        if self._check("MINUS"):
            self._advance()
            operand = self._unary()
            return UnaryOp("-", operand)
        return self._primary()

    def _primary(self):
        tok = self._peek()
        if tok.type == "NUMBER":
            self._advance()
            return Num(tok.value)
        if tok.type == "IDENT":
            self._advance()
            return Var(tok.value)
        if tok.type == "LPAREN":
            self._advance()
            expr = self._expr()
            self._expect("RPAREN")
            return expr
        raise ParserError(
            f"Unexpected token '{tok.value or tok.type}' in expression at "
            f"line {tok.line}, column {tok.col}"
        )

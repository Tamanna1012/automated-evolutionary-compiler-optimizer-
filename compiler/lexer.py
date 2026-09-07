"""
Lexical Analyzer (Lexer / Tokenizer)
-------------------------------------
Converts raw source text of the simplified C-like language into a flat
list of Token objects. This is Phase 1 of the compiler pipeline.

Supported token categories:
    KEYWORD     int, if, else, while, print
    IDENT       variable names
    NUMBER      integer literals
    Operators   + - * / = == != < > <= >=
    Delimiters  ( ) { } ;
    EOF         end-of-file sentinel, always the last token
"""

from dataclasses import dataclass

KEYWORDS = {"int", "if", "else", "while", "print"}

# Multi-character operators must be tried before their single-character
# prefixes (e.g. "==" before "="), so this list is ordered longest-first.
SYMBOLS = [
    ("==", "EQ"), ("!=", "NE"), ("<=", "LE"), (">=", "GE"),
    ("+", "PLUS"), ("-", "MINUS"), ("*", "STAR"), ("/", "SLASH"),
    ("=", "ASSIGN"), ("<", "LT"), (">", "GT"),
    ("(", "LPAREN"), (")", "RPAREN"),
    ("{", "LBRACE"), ("}", "RBRACE"),
    (";", "SEMI"),
]


class LexerError(Exception):
    """Raised when the source text contains a character the lexer cannot classify."""
    pass


@dataclass
class Token:
    type: str    # e.g. 'IDENT', 'NUMBER', 'KEYWORD', 'PLUS', 'EOF' ...
    value: str   # the literal text/lexeme
    line: int
    col: int

    def to_dict(self):
        return {"type": self.type, "value": self.value, "line": self.line, "col": self.col}


class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.col = 1

    def _advance(self, n=1):
        for _ in range(n):
            if self.pos < len(self.source) and self.source[self.pos] == "\n":
                self.line += 1
                self.col = 1
            else:
                self.col += 1
            self.pos += 1

    def tokenize(self):
        tokens = []
        src = self.source
        n = len(src)

        while self.pos < n:
            ch = src[self.pos]

            # Skip whitespace
            if ch in " \t\r\n":
                self._advance()
                continue

            # Skip single-line comments: // ...
            if ch == "/" and self.pos + 1 < n and src[self.pos + 1] == "/":
                while self.pos < n and src[self.pos] != "\n":
                    self._advance()
                continue

            start_line, start_col = self.line, self.col

            # Numbers
            if ch.isdigit():
                start = self.pos
                while self.pos < n and src[self.pos].isdigit():
                    self._advance()
                tokens.append(Token("NUMBER", src[start:self.pos], start_line, start_col))
                continue

            # Identifiers / keywords
            if ch.isalpha() or ch == "_":
                start = self.pos
                while self.pos < n and (src[self.pos].isalnum() or src[self.pos] == "_"):
                    self._advance()
                word = src[start:self.pos]
                ttype = "KEYWORD" if word in KEYWORDS else "IDENT"
                tokens.append(Token(ttype, word, start_line, start_col))
                continue

            # Operators / delimiters (longest match first)
            matched = False
            for sym, ttype in SYMBOLS:
                if src.startswith(sym, self.pos):
                    tokens.append(Token(ttype, sym, start_line, start_col))
                    self._advance(len(sym))
                    matched = True
                    break
            if matched:
                continue

            raise LexerError(
                f"Unexpected character '{ch}' at line {start_line}, column {start_col}"
            )

        tokens.append(Token("EOF", "", self.line, self.col))
        return tokens

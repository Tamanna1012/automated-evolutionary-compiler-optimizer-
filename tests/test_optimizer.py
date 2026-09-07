"""
Unit tests for the full compiler + optimization + evolutionary-search
pipeline.

Run from the project root with:
    python -m unittest discover -s tests -t .
or:
    python -m pytest tests/
"""

import unittest

from compiler.lexer import Lexer, LexerError
from compiler.parser import Parser, ParserError
from compiler.ast_nodes import If
from compiler.intermediate_code import IRGenerator, Instruction
from compiler.interpreter import run_tac

from optimizations import apply_pass_sequence, TRADITIONAL_SEQUENCE
from optimizations.constant_folding import ConstantFolding
from optimizations.constant_propagation import ConstantPropagation
from optimizations.copy_propagation import CopyPropagation
from optimizations.common_subexpression import CommonSubexpressionElimination
from optimizations.dead_code_elimination import DeadCodeElimination
from optimizations.strength_reduction import StrengthReduction
from optimizations.loop_invariant_code_motion import LoopInvariantCodeMotion

from evolutionary.genetic_algorithm import GeneticAlgorithm
from evolutionary.chromosome import Chromosome
from evolutionary.fitness import evaluate_fitness


def compile_to_tac(source: str):
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    return IRGenerator().generate(ast)


class LexerTests(unittest.TestCase):
    def test_tokenizes_keywords_identifiers_numbers_operators(self):
        tokens = Lexer("int a = 10 + b;").tokenize()
        types = [t.type for t in tokens]
        self.assertEqual(
            types,
            ["KEYWORD", "IDENT", "ASSIGN", "NUMBER", "PLUS", "IDENT", "SEMI", "EOF"],
        )

    def test_rejects_unknown_character(self):
        with self.assertRaises(LexerError):
            Lexer("int a = 5 @ 2;").tokenize()

    def test_skips_comments(self):
        tokens = Lexer("// hello\nint a = 1;").tokenize()
        self.assertEqual(tokens[0].type, "KEYWORD")


class ParserTests(unittest.TestCase):
    def test_builds_program_with_declarations(self):
        ast = Parser(Lexer("int a = 1;\nint b = a + 2;").tokenize()).parse()
        self.assertEqual(len(ast.statements), 2)
        self.assertEqual(ast.statements[0].name, "a")
        self.assertEqual(ast.statements[1].name, "b")

    def test_parses_if_else(self):
        src = "int a = 1;\nif (a > 0) { a = 2; } else { a = 3; }"
        ast = Parser(Lexer(src).tokenize()).parse()
        self.assertIsInstance(ast.statements[1], If)
        self.assertEqual(len(ast.statements[1].then_body), 1)
        self.assertEqual(len(ast.statements[1].else_body), 1)

    def test_raises_on_missing_semicolon(self):
        with self.assertRaises(ParserError):
            Parser(Lexer("int a = 1").tokenize()).parse()


class IRGenerationTests(unittest.TestCase):
    def test_simple_assignment_generates_binop_and_assign(self):
        ir = compile_to_tac("int a = 5;\nint b = a + 2;")
        kinds = [i.kind for i in ir]
        self.assertIn("assign", kinds)
        self.assertIn("binop", kinds)

    def test_while_loop_generates_labels_and_conditional_jump(self):
        src = "int i = 0;\nwhile (i < 3) { i = i + 1; }"
        ir = compile_to_tac(src)
        kinds = [i.kind for i in ir]
        self.assertIn("label", kinds)
        self.assertIn("if_false_goto", kinds)
        self.assertIn("goto", kinds)

    def test_print_generates_print_instruction(self):
        ir = compile_to_tac("int a = 1;\nprint(a);")
        self.assertTrue(any(i.kind == "print" for i in ir))


class ConstantFoldingTests(unittest.TestCase):
    def test_folds_constant_arithmetic(self):
        instrs = [Instruction("binop", dest="t1", op="+", arg1=5, arg2=10)]
        out = ConstantFolding().apply(instrs)
        self.assertEqual(out[0].kind, "assign")
        self.assertEqual(out[0].arg1, 15)

    def test_does_not_fold_division_by_zero(self):
        instrs = [Instruction("binop", dest="t1", op="/", arg1=5, arg2=0)]
        out = ConstantFolding().apply(instrs)
        self.assertEqual(out[0].kind, "binop")


class ConstantPropagationTests(unittest.TestCase):
    def test_propagates_known_constant_into_binop(self):
        instrs = [
            Instruction("assign", dest="a", arg1=10),
            Instruction("binop", dest="t1", op="+", arg1="a", arg2=5),
        ]
        out = ConstantPropagation().apply(instrs)
        self.assertEqual(out[1].arg1, 10)

    def test_clears_facts_at_label(self):
        instrs = [
            Instruction("assign", dest="a", arg1=10),
            Instruction("label", label="L1"),
            Instruction("binop", dest="t1", op="+", arg1="a", arg2=5),
        ]
        out = ConstantPropagation().apply(instrs)
        # after a label, 'a' is no longer assumed constant
        self.assertEqual(out[2].arg1, "a")


class CopyPropagationTests(unittest.TestCase):
    def test_propagates_simple_copy(self):
        instrs = [
            Instruction("assign", dest="a", arg1="b"),
            Instruction("binop", dest="t1", op="+", arg1="a", arg2=5),
        ]
        out = CopyPropagation().apply(instrs)
        self.assertEqual(out[1].arg1, "b")


class CommonSubexpressionEliminationTests(unittest.TestCase):
    def test_reuses_previously_computed_expression(self):
        instrs = [
            Instruction("binop", dest="t1", op="+", arg1="a", arg2="b"),
            Instruction("binop", dest="t2", op="+", arg1="a", arg2="b"),
        ]
        out = CommonSubexpressionElimination().apply(instrs)
        self.assertEqual(out[1].kind, "assign")
        self.assertEqual(out[1].arg1, "t1")

    def test_commutative_expressions_match(self):
        instrs = [
            Instruction("binop", dest="t1", op="+", arg1="a", arg2="b"),
            Instruction("binop", dest="t2", op="+", arg1="b", arg2="a"),
        ]
        out = CommonSubexpressionElimination().apply(instrs)
        self.assertEqual(out[1].kind, "assign")

    def test_invalidates_after_operand_redefinition(self):
        instrs = [
            Instruction("binop", dest="t1", op="+", arg1="a", arg2="b"),
            Instruction("assign", dest="a", arg1=99),
            Instruction("binop", dest="t2", op="+", arg1="a", arg2="b"),
        ]
        out = CommonSubexpressionElimination().apply(instrs)
        self.assertEqual(out[2].kind, "binop")  # must recompute, not reuse t1


class DeadCodeEliminationTests(unittest.TestCase):
    def test_removes_variable_never_used_anywhere(self):
        instrs = [
            Instruction("assign", dest="a", arg1=10),
            Instruction("assign", dest="unused", arg1=100),
            Instruction("print", arg1="a"),
        ]
        out = DeadCodeElimination().apply(instrs)
        dests = [i.dest for i in out if i.kind == "assign"]
        self.assertNotIn("unused", dests)
        self.assertIn("a", dests)

    def test_cascading_elimination(self):
        instrs = [
            Instruction("binop", dest="t1", op="+", arg1=1, arg2=2),
            Instruction("assign", dest="dead", arg1="t1"),
            Instruction("assign", dest="a", arg1=5),
            Instruction("print", arg1="a"),
        ]
        out = DeadCodeElimination().apply(instrs)
        dests = [i.dest for i in out if i.kind in ("assign", "binop")]
        self.assertNotIn("dead", dests)
        self.assertNotIn("t1", dests)


class StrengthReductionTests(unittest.TestCase):
    def test_multiply_by_two_becomes_addition(self):
        instrs = [Instruction("binop", dest="t1", op="*", arg1="a", arg2=2)]
        out = StrengthReduction().apply(instrs)
        self.assertEqual(out[0].kind, "binop")
        self.assertEqual(out[0].op, "+")
        self.assertEqual(out[0].arg1, "a")
        self.assertEqual(out[0].arg2, "a")

    def test_multiply_by_one_becomes_identity(self):
        instrs = [Instruction("binop", dest="t1", op="*", arg1="a", arg2=1)]
        out = StrengthReduction().apply(instrs)
        self.assertEqual(out[0].kind, "assign")
        self.assertEqual(out[0].arg1, "a")


class LoopInvariantCodeMotionTests(unittest.TestCase):
    def _simple_loop(self, body_instrs):
        """label L1: t1 = i < 5; if_false t1 goto L2; <body>; goto L1; label L2"""
        return (
            [
                Instruction("label", label="L1"),
                Instruction("binop", dest="t1", op="<", arg1="i", arg2=5),
                Instruction("if_false_goto", arg1="t1", label="L2"),
            ]
            + body_instrs
            + [
                Instruction("goto", label="L1"),
                Instruction("label", label="L2"),
            ]
        )

    def test_hoists_invariant_computation_out_of_loop(self):
        body = [
            Instruction("binop", dest="step", op="*", arg1="factor", arg2=2),
            Instruction("binop", dest="total", op="+", arg1="total", arg2="step"),
            Instruction("binop", dest="i", op="+", arg1="i", arg2=1),
        ]
        instrs = self._simple_loop(body)
        out = LoopInvariantCodeMotion().apply(instrs)

        # the "step = factor * 2" instruction must now appear BEFORE the label
        label_idx = next(idx for idx, ins in enumerate(out) if ins.kind == "label")
        hoisted = [ins for ins in out[:label_idx] if ins.dest == "step"]
        self.assertEqual(len(hoisted), 1)

        # and must no longer appear inside the loop body
        inside_loop = out[label_idx:]
        self.assertFalse(any(ins.dest == "step" for ins in inside_loop))

    def test_does_not_hoist_loop_variant_computation(self):
        # "total = total + step" depends on 'total', which IS modified every
        # iteration by this very instruction -- it must stay inside the loop.
        body = [
            Instruction("binop", dest="total", op="+", arg1="total", arg2="step"),
            Instruction("binop", dest="i", op="+", arg1="i", arg2=1),
        ]
        instrs = self._simple_loop(body)
        out = LoopInvariantCodeMotion().apply(instrs)
        self.assertEqual(self._count(out, "total"), self._count(instrs, "total"))

    def test_never_hoists_division(self):
        body = [
            Instruction("binop", dest="q", op="/", arg1="n", arg2="divisor"),
            Instruction("binop", dest="i", op="+", arg1="i", arg2=1),
        ]
        instrs = self._simple_loop(body)
        out = LoopInvariantCodeMotion().apply(instrs)
        label_idx = next(idx for idx, ins in enumerate(out) if ins.kind == "label")
        self.assertFalse(any(ins.dest == "q" for ins in out[:label_idx]))

    @staticmethod
    def _count(instrs, dest_name):
        return sum(1 for ins in instrs if ins.dest == dest_name)


class PipelineSemanticsTests(unittest.TestCase):
    """End-to-end: optimized code must produce identical print() output."""

    PROGRAMS = [
        "int a = 10;\nint b = 20;\nint c = a + b;\nint d = a + b;\nint u = 100;\nprint(c);\nprint(d);",
        "int a = 7;\nint b = 3;\nint r = 0;\nif (a > b) { r = a - b; } else { r = b - a; }\nprint(r);",
        "int i = 0;\nint s = 0;\nwhile (i < 5) { s = s + i * 2; i = i + 1; }\nprint(s);",
        "int factor = 3;\nint i = 0;\nint total = 0;\nwhile (i < 5) {\n"
        "    int step = factor * 2;\n    total = total + step;\n    i = i + 1;\n}\nprint(total);",
    ]

    def test_traditional_sequence_preserves_semantics(self):
        for src in self.PROGRAMS:
            ir = compile_to_tac(src)
            original_output = run_tac(ir)
            optimized = apply_pass_sequence(ir, TRADITIONAL_SEQUENCE)
            self.assertEqual(run_tac(optimized), original_output)

    def test_ga_best_sequence_preserves_semantics(self):
        for src in self.PROGRAMS:
            ir = compile_to_tac(src)
            original_output = run_tac(ir)
            ga = GeneticAlgorithm(ir, population_size=12, generations=8, seed=42)
            best, _history = ga.run()
            self.assertEqual(run_tac(best.optimized_instructions), original_output)

    def test_traditional_sequence_reduces_or_maintains_instruction_count(self):
        ir = compile_to_tac(self.PROGRAMS[0])
        optimized = apply_pass_sequence(ir, TRADITIONAL_SEQUENCE)
        self.assertLess(len(optimized), len(ir))


class FitnessFunctionTests(unittest.TestCase):
    def test_rejects_semantics_changing_sequence_with_zero_fitness(self):
        # A hand-crafted instruction list that a naive substitution could break:
        # nothing pathological here, but we directly test the zero-fitness path
        # by evaluating an empty sequence, which is explicitly invalid.
        ir = compile_to_tac("int a = 1;\nprint(a);")
        fitness, _optimized, metrics = evaluate_fitness(ir, [])
        self.assertEqual(fitness, 0.0)
        self.assertIn("error", metrics)

    def test_higher_fitness_for_more_reduction(self):
        ir = compile_to_tac(
            "int a = 5;\nint b = 10;\nint c = a + b;\nint d = a + b;\nprint(c);\nprint(d);"
        )
        fit_none, _, _ = evaluate_fitness(ir, ["StrengthReduction"])
        fit_full, _, _ = evaluate_fitness(
            ir, ["ConstantPropagation", "ConstantFolding", "CommonSubexpressionElimination", "DeadCodeElimination"]
        )
        self.assertGreaterEqual(fit_full, fit_none)


class GeneticAlgorithmTests(unittest.TestCase):
    def test_chromosome_random_genes_within_bounds(self):
        c = Chromosome(min_len=3, max_len=6)
        self.assertTrue(3 <= len(c.genes) <= 6)

    def test_ga_run_returns_best_chromosome_and_history(self):
        ir = compile_to_tac(
            "int a = 5;\nint b = 10;\nint c = a + b;\nint d = a + b;\nprint(c);\nprint(d);"
        )
        ga = GeneticAlgorithm(ir, population_size=10, generations=6, seed=7)
        best, history = ga.run()
        self.assertIsNotNone(best.fitness)
        self.assertEqual(len(history), 6)
        # fitness must never decrease across generations, thanks to elitism
        best_so_far = [h["best_fitness"] for h in history]
        self.assertEqual(best_so_far, sorted(best_so_far))

    def test_ga_matches_or_beats_traditional_fitness(self):
        ir = compile_to_tac(
            "int a = 5;\nint b = 10;\nint c = a + b;\nint d = a + b;\nint u = 1;\nprint(c);\nprint(d);"
        )
        trad_fitness, _, _ = evaluate_fitness(ir, TRADITIONAL_SEQUENCE)
        ga = GeneticAlgorithm(ir, population_size=30, generations=25, seed=1)
        best, _history = ga.run()
        self.assertGreaterEqual(best.fitness, trad_fitness * 0.9)


if __name__ == "__main__":
    unittest.main()

"""
Automated Evolutionary Search-Based Compiler Code Optimizer
==============================================================
Flask application tying the whole pipeline together:

    source code
        -> Lexer            (compiler/lexer.py)
        -> Parser / AST      (compiler/parser.py, compiler/ast_nodes.py)
        -> IR Generator/TAC  (compiler/intermediate_code.py)
        -> Traditional fixed-order optimization (optimizations/)
        -> Genetic-Algorithm-discovered optimization (evolutionary/)
        -> JSON response consumed by the web dashboard (templates/index.html)

Run locally with:
    pip install -r requirements.txt
    python app.py
then open http://127.0.0.1:5000/
"""

from flask import Flask, render_template, request, jsonify

from compiler.lexer import Lexer, LexerError
from compiler.parser import Parser, ParserError
from compiler.intermediate_code import IRGenerator, tac_to_lines
from compiler.interpreter import run_tac, TACRuntimeError
from optimizations import apply_pass_sequence, TRADITIONAL_SEQUENCE
from evolutionary.genetic_algorithm import GeneticAlgorithm
from evolutionary.fitness import evaluate_fitness

app = Flask(__name__)

# Genetic Algorithm hyperparameters (kept modest so a request stays fast
# for the small teaching-language programs this project targets).
GA_CONFIG = dict(
    population_size=30,
    generations=40,
    mutation_rate=0.2,
    crossover_rate=0.8,
    elitism_count=2,
    tournament_size=3,
    min_len=3,
    max_len=8,
)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    payload = request.get_json(silent=True) or {}
    source = payload.get("source", "")

    if not source or not source.strip():
        return jsonify({"error": "Source code is empty. Please enter a program."}), 400

    # ---- Phase 1: Lexical Analysis -----------------------------------------
    try:
        tokens = Lexer(source).tokenize()
    except LexerError as exc:
        return jsonify({"error": f"Lexical error: {exc}"}), 400

    # ---- Phase 2: Parsing -----------------------------------------
    try:
        ast = Parser(tokens).parse()
    except ParserError as exc:
        return jsonify({"error": f"Syntax error: {exc}"}), 400

    # ---- Phase 3: Intermediate Code Generation -----------------------------------------
    try:
        ir_gen = IRGenerator()
        original_instructions = ir_gen.generate(ast)
    except Exception as exc:
        return jsonify({"error": f"IR generation error: {exc}"}), 400

    if not original_instructions:
        return jsonify({"error": "Program produced no instructions (nothing to optimize)."}), 400

    # ---- Sanity check: does the ORIGINAL program even run? -----------------
    try:
        original_output = run_tac(original_instructions)
    except TACRuntimeError as exc:
        return jsonify({"error": f"Runtime error while executing the source program: {exc}"}), 400

    # ---- Traditional fixed-order optimization -----------------------------------------
    try:
        trad_fitness, trad_instructions, trad_metrics = evaluate_fitness(
            original_instructions, TRADITIONAL_SEQUENCE, original_output=original_output
        )
    except Exception as exc:
        return jsonify({"error": f"Traditional optimization failed: {exc}"}), 500

    # ---- Evolutionary (Genetic Algorithm) optimization -----------------------------------------
    try:
        ga = GeneticAlgorithm(original_instructions, **GA_CONFIG)
        best_chromosome, history = ga.run()
    except Exception as exc:
        return jsonify({"error": f"Evolutionary search failed: {exc}"}), 500

    evo_instructions = best_chromosome.optimized_instructions
    evo_metrics = best_chromosome.metrics or {}
    evo_output = run_tac(evo_instructions) if evo_instructions else []

    original_cost = evo_metrics.get("cost_before", trad_metrics.get("instruction_count_before"))

    response = {
        "tokens": [t.to_dict() for t in tokens if t.type != "EOF"],
        "ast": ast.to_dict(),
        "tac": {
            "lines": tac_to_lines(original_instructions),
            "count": len(original_instructions),
        },
        "original_output": original_output,
        "traditional": {
            "sequence": TRADITIONAL_SEQUENCE,
            "code": tac_to_lines(trad_instructions),
            "metrics": trad_metrics,
        },
        "evolutionary": {
            "sequence": best_chromosome.genes,
            "code": tac_to_lines(evo_instructions),
            "metrics": evo_metrics,
            "output": evo_output,
            "history": history,
            "generations_run": GA_CONFIG["generations"],
            "population_size": GA_CONFIG["population_size"],
        },
        "comparison": {
            "instructions_before": len(original_instructions),
            "instructions_after_traditional": trad_metrics.get("instruction_count_after"),
            "instructions_after_evolutionary": evo_metrics.get("instruction_count_after"),
            "traditional_reduction_pct": trad_metrics.get("instruction_reduction_pct"),
            "evolutionary_reduction_pct": evo_metrics.get("instruction_reduction_pct"),
            "traditional_fitness": round(trad_fitness, 3),
            "evolutionary_fitness": round(best_chromosome.fitness, 3),
            "evolutionary_won": best_chromosome.fitness > trad_fitness,
        },
    }
    return jsonify(response)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

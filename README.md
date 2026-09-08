# Automated Evolutionary Search-Based Compiler Code Optimizer

A Final Year B.Tech (CSE) Compiler Design project: a small but complete
compiler front-end (lexer -> parser -> AST -> Three-Address-Code) paired
with a library of classic optimization passes, whose **execution order**
is discovered automatically by a **Genetic Algorithm** instead of being
hard-coded by the programmer.

The whole thing is deliberately kept simple on purpose: 6 optimization
passes (no more), a plain textbook genetic algorithm (fixed-length
chromosomes, no exotic operators), and a 2-factor fitness formula with
round, obvious weights. Nothing in here needs a research paper to
justify -- see Section 0 below for the one-minute version.

---

## 0. Explain This Project in One Minute (for viva)

1. **"We built a tiny compiler."** It reads simple C-like code (`int`,
   `if`/`else`, `while`, `print`), turns it into tokens, then an AST,
   then Three-Address Code (TAC) -- the standard textbook pipeline.
2. **"We wrote 6 optimization passes."** Constant Folding, Constant
   Propagation, Copy Propagation, Common Subexpression Elimination,
   Dead Code Elimination, Strength Reduction -- each one is a small,
   independent function that takes TAC in and gives back smaller/better
   TAC.
3. **"Running them in a fixed order isn't always best."** Some orders
   expose more opportunities than others (Section 8 shows a real
   example: reordering two passes shrinks the same program from 6
   instructions down to 3).
4. **"So we used a Genetic Algorithm to search for a better order."** A
   chromosome is just a list of 6 pass names. We start with 30 random
   lists, score each one, keep the best ones, breed and mutate them for
   40 generations, and keep the best sequence ever found.
5. **"How do we know it's not cheating?"** Before trusting any
   sequence's score, we actually *run* the optimized program and check
   its output still matches the original. If it doesn't, that
   sequence scores zero -- no matter how small the code got.
6. **"The score itself is simple too."** `fitness = 70% × (fewer
   instructions) + 30% × (cheaper instructions)`. That's it -- two
   numbers, two round weights.

That's the whole project. Everything below is the same six points,
written out in full detail.

---

## 1. Problem Statement

A compiler typically applies its optimization passes in one fixed,
hand-picked order (e.g. "always run Constant Folding, then Dead Code
Elimination, then Copy Propagation"). But optimization passes interact:
running Constant Propagation *before* Constant Folding exposes more
foldable expressions than running Folding alone; running Dead Code
Elimination *after* Common Subexpression Elimination removes more code
than running it before. There is no single fixed order that is optimal
for every program -- this is the well-known **phase-ordering problem**
in compiler construction.

This project treats phase ordering as a **search problem**: it encodes
candidate pass orderings as chromosomes and uses a Genetic Algorithm to
search for the ordering that produces the smallest, cheapest code for
the *specific* program being compiled -- while a built-in
interpreter-based correctness check guarantees the search can never
accept a sequence that changes what the program actually computes.

## 2. Objectives

1. Implement a working lexer, recursive-descent parser, and AST for a
   simplified C-like language.
2. Lower the AST into Three-Address Code (TAC), a standard intermediate
   representation.
3. Implement six classic, independently-testable optimization passes
   operating on TAC.
4. Implement a genuinely functional, textbook-simple Genetic Algorithm
   (selection, crossover, mutation, elitism) that searches the space of
   pass *sequences* for the fittest one.
5. Design and justify a small, easy-to-defend fitness function that
   rewards smaller, cheaper code while hard-rejecting semantically
   incorrect transformations.
6. Compare a traditional fixed-order optimizer against the
   evolutionary one on the same program, with concrete metrics.
7. Present all of this through a clean web dashboard.

## 3. Features

- Custom simplified C-like language: `int` declarations, assignment,
  arithmetic (`+ - * /`), relational operators, `if`/`else`, `while`,
  and `print(...)` for observable output.
- Hand-written lexer, recursive-descent parser, and AST.
- Three-Address Code generation with proper label/`goto` lowering for
  branches and loops.
- A tiny TAC **interpreter** used purely as a correctness oracle (see
  Section 6).
- Six optimization passes: Constant Folding, Constant Propagation, Copy
  Propagation, Common Subexpression Elimination, Dead Code Elimination,
  Strength Reduction.
- A real, textbook-simple Genetic Algorithm (population of 30, 40
  generations by default) with tournament selection, single-point
  crossover, point mutation, and elitism -- every chromosome is a
  fixed length of 6 genes, so there is no special-case bookkeeping
  anywhere in the algorithm.
- A 2-factor fitness function with plain 70/30 weights.
- A Flask backend exposing one JSON API (`/api/analyze`) that runs the
  entire pipeline twice (fixed order vs. GA-discovered order) and
  returns everything the dashboard needs.
- A single-page dashboard: tokens table, AST tree, TAC listing,
  side-by-side optimization comparison, a generation-by-generation
  fitness chart, and a performance comparison table.
- 29 automated unit/integration tests covering every pass, the parser,
  the IR generator, the fitness function, and end-to-end semantic
  preservation.

## 4. System Architecture

```
                    ┌──────────────────┐
   source code ---->│      Lexer       │----> tokens
                    └──────────────────┘
                              |
                              v
                    ┌──────────────────┐
                    │      Parser      │----> AST
                    └──────────────────┘
                              |
                              v
                    ┌──────────────────┐
                    │   IR Generator   │----> Three-Address Code (TAC)
                    └──────────────────┘
                              |
              ┌───────────────┴────────────────┐
              v                                 v
   ┌────────────────────┐           ┌─────────────────────────┐
   │ Traditional fixed-  │           │   Genetic Algorithm     │
   │ order optimizer     │           │   (evolutionary/)       │
   │ (one hand-picked    │           │   searches pass-order   │
   │  pass sequence)     │           │   "chromosomes"         │
   └────────────────────┘           └─────────────────────────┘
              |                                 |
              v                                 v
      optimized TAC                     best optimized TAC
              \_________________  ________________/
                                \/
                     ┌─────────────────────┐
                     │  Comparison / JSON   │
                     │  API response        │
                     └─────────────────────┘
                                |
                                v
                     ┌─────────────────────┐
                     │   Web Dashboard      │
                     └─────────────────────┘
```

## 5. Compiler Pipeline Explained

### 5.1 Lexical Analysis (`compiler/lexer.py`)
Converts raw source text into a flat token stream (`KEYWORD`, `IDENT`,
`NUMBER`, operators, delimiters), tracking line/column for error
messages. Handles `//` comments.

### 5.2 Parsing (`compiler/parser.py`, `compiler/ast_nodes.py`)
A recursive-descent parser implements this grammar:

```
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
```

The result is an Abstract Syntax Tree built from the node classes in
`ast_nodes.py` (`Program`, `VarDecl`, `Assign`, `Print`, `If`, `While`,
`BinOp`, `UnaryOp`, `Num`, `Var`).

### 5.3 Intermediate Representation (`compiler/intermediate_code.py`)
The AST is lowered into **Three-Address Code**: a flat list of
`Instruction` objects, each of the form `dest = arg1 op arg2` (or the
simpler `assign`/`label`/`goto`/`if_false_goto`/`print` forms). Every
optimization pass and the genetic algorithm operate exclusively on this
shared representation -- that's what makes the passes composable and
freely reorderable. Example:

```
int a = 10;
int c = a + 5;
```
lowers to:
```
a = 10
t1 = a + 5
c = t1
```

`if`/`while` are lowered with the standard label + conditional-jump
pattern (`if_false_goto`), e.g. a `while` loop becomes:
```
L1:
t1 = <condition>
if_false t1 goto L2
<body>
goto L1
L2:
```

### 5.4 The Correctness Oracle (`compiler/interpreter.py`)
Because there is no I/O in this toy language other than `print(...)`,
we can define program *semantics* precisely as "the sequence of values
passed to `print`". A small step-by-step TAC interpreter executes any
instruction list and returns that sequence. This interpreter is what
the fitness function uses to verify that an optimized program still
computes the same thing as the original -- see Section 7.

## 6. Optimization Passes (`optimizations/`)

Every pass is a small class with `apply(instructions) -> instructions`,
independently unit-tested in `tests/test_optimizer.py`. Six passes,
no more -- deliberately kept to the classic textbook set.

| Pass | File | What it does |
|---|---|---|
| **Constant Folding** | `constant_folding.py` | Evaluates a `binop` at compile time when both operands are already constants (`5 + 10` -> `15`). |
| **Constant Propagation** | `constant_propagation.py` | Tracks which variables currently hold a known constant and substitutes that constant into later instructions that read them. |
| **Copy Propagation** | `copy_propagation.py` | Tracks plain variable-to-variable copies (`a = b`) and replaces later uses of the copy with the original variable, exposing more dead code. |
| **Common Subexpression Elimination** | `common_subexpression.py` | If `a + b` was already computed in the current basic block and neither operand has changed since, reuse the earlier result instead of recomputing it (handles commutative operators and self-referential updates like `a = a + b` correctly). |
| **Dead Code Elimination** | `dead_code_elimination.py` | Iteratively removes any instruction whose result is never used anywhere in the remaining program (fixed-point, so it cascades). |
| **Strength Reduction** | `strength_reduction.py` | Replaces an expensive operation with a cheaper equivalent, e.g. `x * 2` -> `x + x`, `x * 1` -> `x`, `x * 0` -> `0`, `x / 1` -> `x`. |

All label-crossing dataflow facts (known constants, known copies,
available expressions) are conservatively cleared at every `label`,
since a label may be a join point reached from more than one place
(e.g. a loop back-edge) -- this is what keeps every pass safe in the
presence of `if`/`while`.

A **fixed traditional sequence** is also defined
(`optimizations/TRADITIONAL_SEQUENCE`) as the "hand-picked textbook
order" baseline the evolutionary search is compared against:

```
ConstantPropagation -> ConstantFolding -> CopyPropagation ->
CommonSubexpressionElimination -> StrengthReduction -> DeadCodeElimination
```

## 7. The Evolutionary Search Engine (`evolutionary/`)

### 7.1 Why evolutionary search?
Applying all six passes once, in *some* order, is not enough:
propagation can expose new folding opportunities, folding can expose
new dead code, removing dead code can expose new common subexpressions,
and so on. A single fixed pass only "sees" what came before it in that
one pass through the list. Running the *right* passes, in the *right*
order, sometimes more than once, is what actually reaches a good fixed
point for a given program -- and the right order is different for
different programs. Rather than hand-tune this per program, we let a
Genetic Algorithm search for it.

### 7.2 Chromosome representation (`evolutionary/chromosome.py`)
A chromosome is a **fixed-length** list of 6 pass names -- a candidate
"optimization strategy":

```python
["ConstantFolding", "ConstantPropagation", "CopyPropagation",
 "DeadCodeElimination", "ConstantFolding", "StrengthReduction"]
```

Every chromosome is exactly `CHROMOSOME_LENGTH = 6` genes long, and a
pass name may repeat (running `ConstantPropagation` twice, as above, is
a perfectly valid strategy -- and Section 8's example shows exactly why
that can help). Keeping every chromosome the same length is what keeps
crossover and mutation trivial to implement and explain: there is no
"what if the two parents are different lengths" case to handle
anywhere in the code.

### 7.3 Fitness function (`evolutionary/fitness.py`)

**Step 1 -- correctness gate ("did we break the program?").** The
candidate sequence is applied to the program's TAC, and the
*optimized* TAC is executed by the interpreter from Section 5.4. Its
`print()` output is compared against the *original* program's output.
If they differ (or applying the sequence raises any error, or the code
fails to run), the candidate is rejected outright: **fitness = 0**.
This is a hard constraint, not a soft penalty -- it is the guarantee
that the search can never converge on a sequence that "optimizes" a
program into a different, smaller, but *wrong* program.

**Step 2 -- weighted improvement score ("how much smaller/cheaper?"),**
for sequences that pass the gate:

```
fitness = 100 * (0.7 * instruction_reduction + 0.3 * cost_reduction)
```

| Term | Meaning |
|---|---|
| `instruction_reduction` | `(instructions before - instructions after) / instructions before` -- the main signal: fewer TAC instructions after optimization. |
| `cost_reduction` | Same idea, but using `estimate_cost`, which counts every arithmetic/comparison instruction (`binop`) as costing 2 units and everything else as costing 1. This lets a sequence still score a little higher even when it doesn't change the instruction *count* but does replace some computation with a cheaper form. |

Instruction count gets the larger weight (0.7) because it is the
number a viva examiner can point at directly on screen; cost is a
smaller (0.3) tie-breaker layered on top. Both ratios are clamped to
`[0, 1]`, so a sequence can never score below 0 on either term. That's
the entire formula -- two terms, two round weights, fully readable in
`evolutionary/fitness.py`.

### 7.4 Genetic operators (`evolutionary/genetic_algorithm.py`)

- **Initial population**: 30 chromosomes, each 6 random genes (default).
- **Selection**: tournament selection (3 random individuals compete,
  the fittest wins) -- simple, and avoids the premature convergence
  that pure fitness-proportionate ("roulette") selection can cause.
- **Crossover**: single-point crossover (probability 0.8 by default)
  -- pick one random cut point, swap the gene-list tails between two
  parents. Because every chromosome is the same fixed length, the two
  children are automatically the same length too; no clamping or
  padding logic is needed anywhere.
- **Mutation**: point mutation (probability 0.2 by default) -- each
  gene independently has a chance to be replaced by a randomly chosen
  pass name. Nothing more exotic than that.
- **Elitism**: the top 2 fittest individuals are copied unchanged into
  the next generation, which guarantees the best fitness seen so far
  can never regress across generations (verified in
  `tests/test_optimizer.py`).
- **Termination**: after a fixed number of generations (40 by
  default); the best chromosome ever seen across all generations is
  returned, along with the full per-generation history (best fitness,
  average fitness, best sequence-so-far) for the dashboard's evolution
  chart.

## 8. Results Comparison

For each analyzed program, the dashboard shows, side by side:

1. **Original code** -- exactly what the user typed.
2. **Intermediate code before optimization** -- the generated TAC.
3. **Traditional fixed-order optimization** -- `TRADITIONAL_SEQUENCE`
   applied once, with its resulting code and metrics.
4. **Evolutionary optimization** -- the GA's best discovered sequence,
   its resulting code, and metrics.
5. **Performance comparison dashboard** -- instruction counts before /
   after each strategy, percentage reduction, fitness scores, and a
   direct verdict on whether the evolutionary search beat the fixed
   order.

### Example (see the "Basic / CSE" example in the UI)

Input:
```c
int a = 10;
int b = 20;
int c = a + b;
int d = a + b;
int unused = 100;
int e = 5 + 10;
print(c);
print(d);
print(e);
```

| Metric | Original | Traditional | Evolutionary |
|---|---|---|---|
| Instructions | 12 | 6 | **3** |
| Reduction | - | 50% | **75%** |
| Fitness | - | ~53 | **~77** |
| `print()` output | `[30, 30, 15]` | `[30, 30, 15]` | `[30, 30, 15]` |

The traditional single-pass-each order gets stuck at
`t1 = 30; t2 = 30; t3 = 15; print(t1); print(t2); print(t3);` because
its one `ConstantPropagation` pass runs *before* the temporaries are
folded into the `print` statements, and Dead Code Elimination only runs
once, at the very end. The GA discovers that running
`ConstantPropagation` a **second time** (after folding) propagates the
now-constant temporaries directly into the `print` calls, after which
Dead Code Elimination removes all three temporary assignments entirely
-- collapsing the program straight down to three `print` statements.
This is a concrete, reproducible demonstration of the phase-ordering
problem, and of the evolutionary search solving it better than a fixed
order.

## 9. Project Structure

```
automated-evolutionary-compiler-optimizer/
├── app.py                             Flask app / JSON API
├── requirements.txt
├── README.md
├── compiler/
│   ├── __init__.py
│   ├── lexer.py                       Phase 1: tokenizer
│   ├── parser.py                      Phase 2: recursive-descent parser
│   ├── ast_nodes.py                   AST node classes
│   ├── intermediate_code.py           Phase 3: TAC Instruction + IR generator
│   └── interpreter.py                 TAC interpreter (correctness oracle)
├── optimizations/
│   ├── __init__.py                    PASS_REGISTRY, TRADITIONAL_SEQUENCE
│   ├── constant_folding.py
│   ├── constant_propagation.py
│   ├── copy_propagation.py
│   ├── common_subexpression.py
│   ├── dead_code_elimination.py
│   └── strength_reduction.py
├── evolutionary/
│   ├── __init__.py
│   ├── chromosome.py                  Fixed-length chromosome representation
│   ├── fitness.py                     2-factor fitness function
│   └── genetic_algorithm.py           GA: selection/crossover/mutation/elitism
├── templates/
│   └── index.html
├── static/
│   ├── css/style.css
│   └── js/script.js
└── tests/
    └── test_optimizer.py              29 unit/integration tests
```

## 10. Installation & How to Run

Requires Python 3.9+ and pip. No database, no external compiler
toolchain, and no Graphviz install required -- the AST is rendered as
an interactive HTML tree directly in the browser.

```bash
# 1. Clone / open the project folder, then create a virtual environment
python -m venv venv

# 2. Activate it
#    Windows:
venv\Scripts\activate
#    macOS / Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app
python app.py

# 5. Open your browser at:
http://127.0.0.1:5000/
```

### Windows quick-start (exact commands)

```powershell
cd path\to\automated-evolutionary-compiler-optimizer
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000/` in your browser.

### Running the tests

```bash
python -m pytest tests/
# or
python -m unittest discover -s tests -t .
```

### Deploying to Vercel

A `vercel.json` is included, so the Flask app deploys as-is:

1. Push this repo to GitHub (already done if you're reading this on GitHub).
2. Go to [vercel.com](https://vercel.com), sign in, and click **Add New... -> Project**.
3. Import this repository. Vercel auto-detects `vercel.json` and builds `app.py`
   with the `@vercel/python` runtime -- no extra configuration needed.
4. Click **Deploy**. Vercel installs `requirements.txt` and serves the app;
   `templates/` and `static/` are picked up automatically.

## 11. Example Input / Output

Three ready-made examples are built into the UI ("Load example"
buttons):

- **Basic / CSE** -- constant folding, constant propagation, common
  subexpression elimination and dead code elimination all have
  something to do (see Section 8 for the full walkthrough).
- **If / Else** -- exercises branch lowering (`if_false_goto`, labels)
  and shows that optimizations remain safe across control flow.
- **While Loop** -- exercises loop lowering and Strength Reduction
  (`i * 2` inside the loop body becomes `i + i`).

Each example can be analyzed directly from the "Analyze & Optimize
Code" button; the dashboard fills in with tokens, the AST, the TAC,
both optimization results, the GA's generation-by-generation fitness
chart, and the final comparison table.

## 12. Academic Q&A (for viva / evaluation)

**Why do traditional compilers use optimization passes instead of one
big pass?** Splitting optimization into small, focused passes (each
responsible for one transformation) keeps each pass simple, correct,
and independently testable -- exactly the same reason this project's
`optimizations/` package is organized as six small classes rather than
one monolithic function. Real compilers (GCC, LLVM) use dozens of such
passes.

**Why does the order of optimization passes matter?** Passes expose
opportunities for each other. Constant Propagation can turn a variable
reference into a constant that Constant Folding can then evaluate;
that folding can turn a variable's only use into a constant, making
the variable dead, which Dead Code Elimination can then remove. Run
the passes in a different order and some of these opportunities are
never exposed. Section 8's example shows this concretely: reordering
(and repeating) two passes takes the same program from 6 optimized
instructions down to 3.

**What is the phase-ordering problem?** It is the open question, for
any given program, of which sequence (including which repetitions) of
a compiler's optimization passes produces the best result. It is known
to be a genuinely hard combinatorial search problem -- there is no
single ordering that is optimal for every program, and exhaustively
trying every possible ordering is computationally infeasible for
compilers with dozens of passes.

**How do evolutionary algorithms help solve it?** A Genetic Algorithm
treats "which sequence of passes to run" as the thing being optimized.
Instead of exhaustively trying every possible ordering (infeasible) or
committing to one fixed guess (suboptimal), it maintains a *population*
of candidate orderings, measures how good each one actually is on the
program at hand (the fitness function), and breeds better candidates
from the best-performing ones over many generations -- a heuristic
search that scales far better than brute force while still exploring
combinations a human wouldn't think to try (like repeating a pass).

**How do chromosomes represent optimization sequences?** Each gene in
a chromosome is the name of one optimization pass; the chromosome's
gene list, in order, *is* the sequence of passes to apply. Every
chromosome is a fixed length of 6 genes (repeats allowed), so two
chromosomes with the same passes in a different order represent
genuinely different optimization strategies -- see
`evolutionary/chromosome.py`.

**How does the fitness function evaluate optimized code?** First it
enforces correctness: it actually *executes* both the original and
optimized TAC with the interpreter in `compiler/interpreter.py` and
requires their `print()` output to match exactly, or the sequence
scores zero. Only then does it compute `0.7 * instruction_reduction +
0.3 * cost_reduction` (full formula in Section 7.3 and in the
`evolutionary/fitness.py` docstring) -- deliberately just two terms
with round weights, so it can be stated and defended in one sentence.

**Why is this project relevant to Compiler Design?** It touches every
classical phase of a compiler (lexing, parsing, IR generation,
optimization) while making the *hardest*, least mechanical part of
optimization -- deciding what to run when -- the actual subject of the
project, using a well-known metaheuristic (genetic algorithms) that is
genuinely used in real compiler research (e.g. auto-tuning `-O` flag
combinations, superoptimization, and iterative compilation research)
to attack exactly this problem.

## 13. Future Improvements

These are explicitly *not* built, by design -- the project stays small
enough to explain confidently rather than chasing every possible
extension:

- Full control-flow-graph-based (rather than linear-scan) liveness
  analysis, enabling unreachable-code elimination.
- Additional passes such as Loop-Invariant Code Motion or loop
  unrolling.
- A Graphviz-rendered AST/CFG diagram as an alternative to the current
  HTML tree view.
- Support for functions/procedures and arrays.
- Variable-length chromosomes (letting the GA also search over
  *how many* passes to run, not just their order) -- deliberately
  left out here to keep the genetic algorithm textbook-simple.

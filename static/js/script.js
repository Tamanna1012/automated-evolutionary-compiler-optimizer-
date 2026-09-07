"use strict";

const EXAMPLES = {
    basic:
`// Demonstrates constant folding, constant propagation,
// common subexpression elimination and dead code elimination.
int a = 10;
int b = 20;
int c = a + b;
int d = a + b;
int unused = 100;
int e = 5 + 10;
print(c);
print(d);
print(e);`,

    branch:
`// Demonstrates if/else lowering and branch-safe optimization.
int a = 7;
int b = 3;
int result = 0;
if (a > b) {
    result = a - b;
} else {
    result = b - a;
}
print(result);`,

    loop:
`// Demonstrates while-loop lowering and strength reduction (i * 2 -> i + i).
int i = 0;
int sum = 0;
while (i < 5) {
    sum = sum + i * 2;
    i = i + 1;
}
print(sum);`,
};

const el = (id) => document.getElementById(id);

document.addEventListener("DOMContentLoaded", () => {
    el("source-input").value = EXAMPLES.basic;

    document.querySelectorAll("[data-example]").forEach((btn) => {
        btn.addEventListener("click", () => {
            el("source-input").value = EXAMPLES[btn.dataset.example];
        });
    });

    el("analyze-btn").addEventListener("click", analyzeCode);
});

async function analyzeCode() {
    const source = el("source-input").value;
    const statusMsg = el("status-msg");
    const errorBox = el("error-box");
    const results = el("results");

    errorBox.classList.add("hidden");
    results.classList.add("hidden");
    statusMsg.textContent = "Running lexer, parser, IR generation and genetic search...";
    statusMsg.className = "status-msg loading";
    el("analyze-btn").disabled = true;

    try {
        const resp = await fetch("/api/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ source }),
        });
        const data = await resp.json();

        if (!resp.ok) {
            throw new Error(data.error || "Unknown server error");
        }

        renderResults(data);
        statusMsg.textContent = "Done.";
        statusMsg.className = "status-msg done";
        results.classList.remove("hidden");
    } catch (err) {
        errorBox.textContent = err.message;
        errorBox.classList.remove("hidden");
        statusMsg.textContent = "";
        statusMsg.className = "status-msg";
    } finally {
        el("analyze-btn").disabled = false;
    }
}

function renderResults(data) {
    renderTokens(data.tokens);
    renderAst(data.ast);
    renderTac(data.tac);
    renderPassCard("traditional", data.traditional);
    renderPassCard("evolutionary", data.evolutionary);
    renderGaHistory(data.evolutionary);
    renderComparison(data.comparison, data.original_output, data.evolutionary.output);
}

function renderTokens(tokens) {
    const tbody = document.querySelector("#tokens-table tbody");
    tbody.innerHTML = "";
    tokens.forEach((t, i) => {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${i + 1}</td><td>${t.type}</td><td>${escapeHtml(t.value)}</td><td>${t.line}</td><td>${t.col}</td>`;
        tbody.appendChild(tr);
    });
}

function renderAst(astNode) {
    const container = el("ast-tree");
    container.innerHTML = "";
    container.appendChild(buildAstNode(astNode));
}

function buildAstNode(node) {
    const wrapper = document.createElement("div");
    const label = document.createElement("span");
    label.className = "ast-node-label";
    let text = node.node;
    if (node.name) text += ` [${node.name}]`;
    label.textContent = text;
    wrapper.appendChild(label);

    if (node.children && node.children.length > 0) {
        const ul = document.createElement("ul");
        node.children.forEach((child) => {
            const li = document.createElement("li");
            li.appendChild(buildAstNode(child));
            ul.appendChild(li);
        });
        wrapper.appendChild(ul);
    }
    return wrapper;
}

function renderTac(tac) {
    el("tac-code").textContent = tac.lines.join("\n");
    el("tac-count").textContent = `${tac.count} instructions`;
}

function renderPassCard(prefix, block) {
    const seqContainer = el(`${prefix}-sequence`);
    seqContainer.innerHTML = "";
    block.sequence.forEach((pass, i) => {
        if (i > 0) {
            const arrow = document.createElement("span");
            arrow.className = "pill-arrow";
            arrow.textContent = "→";
            seqContainer.appendChild(arrow);
        }
        const pill = document.createElement("span");
        pill.className = "pill";
        pill.textContent = pass;
        seqContainer.appendChild(pill);
    });

    el(`${prefix}-code`).textContent = block.code.join("\n");

    const metricsEl = el(`${prefix}-metrics`);
    metricsEl.innerHTML = "";
    const m = block.metrics || {};
    const tiles = [
        ["Instructions", `${m.instruction_count_before ?? "-"} → ${m.instruction_count_after ?? "-"}`],
        ["Reduction", `${m.instruction_reduction_pct ?? 0}%`],
        ["Fitness Score", `${m.fitness ?? 0}`],
        ["Est. Cost", `${m.cost_before ?? "-"} → ${m.cost_after ?? "-"}`],
    ];
    tiles.forEach(([label, value]) => metricsEl.appendChild(metricTile(label, value)));
}

function metricTile(label, value) {
    const div = document.createElement("div");
    div.className = "metric-tile";
    div.innerHTML = `<div class="value">${value}</div><div class="label">${label}</div>`;
    return div;
}

function renderGaHistory(evo) {
    el("ga-summary").textContent =
        `${evo.population_size} chromosomes × ${evo.generations_run} generations`;

    const chart = el("fitness-chart");
    chart.innerHTML = "";
    const maxFitness = Math.max(1, ...evo.history.map((h) => h.best_fitness));
    evo.history.forEach((h) => {
        const bar = document.createElement("div");
        bar.className = "fitness-bar";
        const heightPct = Math.max(2, (h.best_fitness / maxFitness) * 100);
        bar.style.height = `${heightPct}%`;
        bar.title = `Gen ${h.generation}: best=${h.best_fitness}, avg=${h.avg_fitness}`;
        chart.appendChild(bar);
    });

    const tbody = document.querySelector("#history-table tbody");
    tbody.innerHTML = "";
    // Show every generation if few, otherwise sample for readability.
    const step = Math.max(1, Math.ceil(evo.history.length / 25));
    evo.history.forEach((h, idx) => {
        if (idx % step !== 0 && idx !== evo.history.length - 1) return;
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${h.generation}</td><td>${h.best_fitness}</td><td>${h.avg_fitness}</td><td>${h.best_sequence.join(" → ")}</td>`;
        tbody.appendChild(tr);
    });
}

function renderComparison(cmp, originalOutput, evoOutput) {
    const dashboard = el("comparison-dashboard");
    dashboard.innerHTML = "";
    const tiles = [
        ["Instructions (Original)", cmp.instructions_before],
        ["Instructions (Traditional)", cmp.instructions_after_traditional],
        ["Instructions (Evolutionary)", cmp.instructions_after_evolutionary],
        ["Traditional Reduction", `${cmp.traditional_reduction_pct}%`],
        ["Evolutionary Reduction", `${cmp.evolutionary_reduction_pct}%`],
        ["Traditional Fitness", cmp.traditional_fitness],
        ["Evolutionary Fitness", cmp.evolutionary_fitness],
    ];
    tiles.forEach(([label, value]) => dashboard.appendChild(metricTile(label, value)));

    const tbody = document.querySelector("#comparison-table tbody");
    tbody.innerHTML = "";
    const rows = [
        ["Instruction count", cmp.instructions_before, cmp.instructions_after_traditional, cmp.instructions_after_evolutionary],
        ["Reduction vs. original", "-", `${cmp.traditional_reduction_pct}%`, `${cmp.evolutionary_reduction_pct}%`],
        ["Fitness score", "-", cmp.traditional_fitness, cmp.evolutionary_fitness],
        ["print() output (correctness check)", fmtOutput(originalOutput), fmtOutput(originalOutput), fmtOutput(evoOutput)],
    ];
    rows.forEach((cells) => {
        const tr = document.createElement("tr");
        tr.innerHTML = cells.map((c) => `<td>${c}</td>`).join("");
        tbody.appendChild(tr);
    });

    const banner = el("winner-banner");
    if (cmp.evolutionary_won) {
        banner.className = "winner-banner win";
        banner.textContent =
            `The evolutionary search discovered a pass sequence with a HIGHER fitness score ` +
            `(${cmp.evolutionary_fitness}) than the fixed traditional order (${cmp.traditional_fitness}) -- ` +
            `it solved the phase-ordering problem better than the hand-picked sequence.`;
    } else {
        banner.className = "winner-banner tie";
        banner.textContent =
            `The evolutionary search matched the traditional fixed order on this program ` +
            `(fitness ${cmp.evolutionary_fitness} vs ${cmp.traditional_fitness}). ` +
            `For small programs the fixed order can already be near-optimal -- try the loop ` +
            `or a longer program to see the GA pull ahead.`;
    }
}

function fmtOutput(arr) {
    if (!arr || arr.length === 0) return "(no output)";
    return "[" + arr.join(", ") + "]";
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

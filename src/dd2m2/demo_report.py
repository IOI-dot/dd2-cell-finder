"""Local presentation figures and reports for the saved-library demo."""

from collections import deque
import csv
from html import escape
from pathlib import Path

from dd2.aig import read_aiger


def _comparison(row, metric, unit, digits):
    before = float(row[f"baseline_{metric}"])
    after = float(row[f"extended_{metric}"])
    delta = round(after - before, digits)
    change = f"{abs(delta):,.{digits}f} {unit} {'less' if delta < 0 else 'more'}" if delta else "Unchanged"
    color = "#117264" if delta < 0 else "#9b471b" if delta > 0 else "#516375"
    return f"{before:,.{digits}f} → {after:,.{digits}f} {unit}", change, color


def _summary_png(design, rows, output):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    fig = plt.figure(figsize=(11.2, 4.2), facecolor="#f2f6fa")
    ax = fig.add_axes([0, 0, 1, 1], xlim=(0, 1), ylim=(0, 1), frameon=False)
    ax.axis("off")
    ax.text(.05, .86, design, fontsize=25, fontweight="bold", color="#132940")
    ax.text(.05, .765, "BASELINE HD  →  HD + CHARACTERIZED GB4 CELLS", fontsize=11, color="#516375")
    for x, row in zip((.05, .52), rows):
        ax.add_patch(FancyBboxPatch((x, .17), .43, .53, boxstyle="round,pad=0.012",
                                   facecolor="white", edgecolor="#d7e2ec"))
        ax.text(x+.022, .62, f"Script {row['script']}", fontsize=15, fontweight="bold", color="#132940")
        for y, title, key, unit, digits in (
            (.50, "Cell area", "um2", "µm²", 2),
            (.34, "Worst arrival", "delay_ns", "ns", 3),
        ):
            values, change, color = _comparison(row, key, unit, digits)
            ax.text(x+.022, y+.05, title, fontsize=9, color="#516375")
            ax.text(x+.022, y, values, fontsize=12, fontweight="bold", color="#132940")
            ax.text(x+.022, y-.054, change, fontsize=10, color=color)
        ax.text(x+.022, .203, f"CEC pass on both mappings   ·   GB4 cells used  {row['new_cell_instances']}",
                fontsize=9, color="#516375")
    ax.text(.05, .065, "Smaller area and lower worst arrival are favorable. Area and timing can trade off.",
            fontsize=10, color="#516375")
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _tradeoff_png(rows, output):
    import matplotlib.pyplot as plt

    labels, changes = [], []
    for row in rows:
        for metric, title in (("um2", "Area"), ("delay_ns", "Delay")):
            before = float(row[f"baseline_{metric}"])
            after = float(row[f"extended_{metric}"])
            labels.append(f"Script {row['script']} · {title}")
            changes.append(round(100 * (after - before) / before, 2) if before else None)

    fig, ax = plt.subplots(figsize=(9, 3.3), layout="constrained", facecolor="#f2f6fa")
    values = [change or 0 for change in changes]
    span = max(1, *map(abs, values))
    bars = ax.barh(labels, values, height=.55,
                   color=["#117264" if value < 0 else "#a34b17" for value in values])
    ax.bar_label(bars, labels=["N/A" if change is None else f"{change:+.2f}%" if change else "0%"
                               for change in changes], padding=5, color="#132940")
    ax.set_xlim(min(0, *values) - span*.22, max(0, *values) + span*.22)
    ax.set_xlabel("Change from baseline (%)  ·  smaller is better", color="#516375")
    ax.axvline(0, color="#526174", linewidth=1)
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=.2)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _aig_counts_png(cuts, output):
    import matplotlib.pyplot as plt
    from matplotlib.ticker import StrMethodFormatter

    fig, axes = plt.subplots(1, 2, figsize=(9, 2.65), layout="constrained", facecolor="#f2f6fa")
    stages = ("Before ABC", "After ABC")
    for ax, (key, title) in zip(axes, (("ands", "AND nodes"), ("checked", "Cuts checked"))):
        counts = [row[key] for row in cuts]
        bars = ax.barh(stages, counts, height=.48, color=["#55728c", "#117264"])
        ax.bar_label(bars, labels=[f"{count:,}" for count in counts], padding=5, color="#132940")
        ax.set_xlim(0, max(1, *counts) * 1.27)
        ax.xaxis.set_major_formatter(StrMethodFormatter("{x:,.0f}"))
        ax.set_title(title, color="#132940", loc="left")
        ax.invert_yaxis()
        ax.grid(axis="x", alpha=.2)
        ax.set_axisbelow(True)
        ax.spines[["top", "right", "left"]].set_visible(False)
    fig.savefig(output, dpi=160)
    plt.close(fig)


def _cone(fanins, literal, depth_limit):
    root = literal >> 1
    levels = {root: 0}
    edges = [(root, None, literal & 1)]
    queue = deque([root])
    while queue:
        gate = queue.popleft()
        depth = levels[gate]
        if depth >= depth_limit:
            continue
        for operand in fanins.get(gate, ()):
            node = operand >> 1
            edges.append((node, gate, operand & 1))
            if node not in levels:
                levels[node] = depth + 1
                queue.append(node)
    return levels, edges


def _aig_png(discovery, output):
    import matplotlib.pyplot as plt

    graphs = [read_aiger(discovery / f"{stage}.aig") for stage in ("synth", "restructured")]
    fanins = [graph.fanins() for graph in graphs]
    outputs = [graph.all_outputs() for graph in graphs]
    count = min(map(len, outputs))
    if not count:
        return None
    depth_limit = 3
    # Prefer an output with visible logic in both graphs. Ties favor lower indices.
    index = max(range(count), key=lambda i: min(
        len(_cone(f, pins[i], depth_limit)[0]) for f, pins in zip(fanins, outputs)
    ))
    fig, axes = plt.subplots(1, 2, figsize=(11.2, 4.5), layout="constrained", facecolor="#f2f6fa")
    fig.suptitle(f"Same primary output in both AIGs  ·  output[{index}]", color="#132940", weight="bold")
    for ax, graph, fanin, pins, stage in zip(
        axes, graphs, fanins, outputs, ("Yosys synthesized", "ABC restructured")
    ):
        levels, edges = _cone(fanin, pins[index], depth_limit)
        inputs = {literal >> 1: i for i, literal in enumerate(graph.inputs)}
        states = {literal >> 1: i for i, (literal, _, _) in enumerate(graph.latches)}
        pos = {None: (.5, 0)}
        for depth in range(depth_limit + 1):
            nodes = [node for node, level in levels.items() if level == depth]
            pos.update({node: ((i+1)/(len(nodes)+1), -depth-1) for i, node in enumerate(nodes)})
        for src, dst, inverted in edges:
            ax.annotate("", pos[dst], pos[src], arrowprops={
                "arrowstyle": "->", "color": "#a64f26" if inverted else "#7e91a6",
                "linestyle": "--" if inverted else "-", "lw": 1.3, "shrinkA": 13, "shrinkB": 13,
            })
        for node, (x, y) in pos.items():
            if node is None:
                label, fill = "Output", "#d9eee7"
            elif node in fanin:
                label = "AND …" if levels[node] == depth_limit else "AND"
                fill = "#e0ecfa"
            elif node in inputs:
                label, fill = f"In {inputs[node]}", "white"
            elif node in states:
                label, fill = f"FF {states[node]}", "white"
            else:
                label, fill = "0", "white"
            ax.text(x, y, label, ha="center", va="center", fontsize=8.5, color="#132940",
                    bbox={"boxstyle": "round,pad=.24", "facecolor": fill, "edgecolor": "#95a9bf"})
        ax.set(xlim=(0, 1), ylim=(-depth_limit-1.45, .45))
        ax.set_title(f"{stage}  ·  {graph.A:,} total ANDs", color="#132940", fontsize=11)
        ax.axis("off")
    fig.supxlabel("Dashed orange edge = inverted signal   ·   AND … = deeper logic omitted   ·   FF = flip-flop",
                  color="#516375", fontsize=9)
    fig.savefig(output, dpi=160)
    plt.close(fig)
    return index


_CSS = """
:root{color-scheme:light;font:16px system-ui,sans-serif;color:#152b42;background:#edf3f9}
*{box-sizing:border-box}
main{max-width:1100px;margin:auto;padding:clamp(1rem,4vw,3rem)}
header{background:#12304a;color:white;border-radius:20px;padding:clamp(1.25rem,4vw,2.8rem)}
h1{font-size:clamp(1.8rem,5vw,3.2rem);margin:.35rem 0}
h2{margin:0 0 .8rem}
p{line-height:1.5}
figure{margin:1rem 0}
figcaption{color:#516375;margin-top:.45rem;font-size:.9rem}
.eyebrow{color:#bee3df;letter-spacing:.13em;font-weight:700;font-size:.8rem}
section{background:white;border:1px solid #d6e2ee;border-radius:15px;padding:1.25rem;margin-top:1rem}
nav{display:flex;flex-wrap:wrap;gap:.7rem;margin:1rem 0}
a{color:#155e75}
nav a{padding:.4rem .7rem;background:#fff;border:1px solid #d6e2ee;border-radius:8px}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:.7rem .65rem;border-bottom:1px solid #e4ebf2}
th{color:#42576a;font-size:.86rem}
td small{display:block;margin-top:.22rem;font-weight:650}
img{display:block;width:100%;height:auto;border-radius:10px}
.scroll{overflow-x:auto}
.good{color:#117264;font-weight:700}
.bad{color:#993d24;font-weight:700}
.muted{color:#516375}
"""


def _page(path, title, subtitle, body):
    path.write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(title)} | GB4 demo</title><style>{_CSS}</style></head>
<body><main><header><div class="eyebrow">GB4 / SAVED-LIBRARY DEMO</div>
<h1>{escape(title)}</h1><p>{escape(subtitle)}</p></header>{body}</main></body></html>
""", encoding="utf-8")


def case_report(design, rows, cuts, out):
    _summary_png(design.name, rows, out / "summary.png")
    _tradeoff_png(rows, out / "mapping-change.png")
    _aig_counts_png(cuts, out / "aig-counts.png")
    index = _aig_png(out / "discovery", out / "aig-comparison.png")
    metrics = []
    for row in rows:
        area, area_delta, area_color = _comparison(row, "um2", "µm²", 2)
        delay, delay_delta, delay_color = _comparison(row, "delay_ns", "ns", 3)
        metrics.append(
            f"<tr><th>Script {escape(row['script'])}</th>"
            f"<td>{area}<small style='color:{area_color}'>{area_delta}</small></td>"
            f"<td>{delay}<small style='color:{delay_color}'>{delay_delta}</small></td>"
            f"<td>{int(row['new_cell_instances'])}</td><td class='good'>Pass / pass</td></tr>"
        )
    stages = {"synth": "Yosys synthesized", "restructured": "ABC restructured"}
    graph_rows = "".join(
        f"<tr><th>{stages[row['variant']]}</th><td>{row['ands']:,}</td>"
        f"<td>{row['checked']:,}</td><td>{row['pn_classes']:,}</td>"
        f"<td>{row['failures']:,}</td></tr>" for row in cuts
    )
    cone = (
        f'<img src="aig-comparison.png" alt="Before and after AIG logic driving output {index}">'
        if index is not None else '<p class="muted">This AIG has no comparable primary output cone.</p>'
    )
    page = out / "index.html"
    _page(page, design.name, f"Top module {design.top} · Baseline HD → HD + characterized GB4 cells", f"""
<nav><a href="summary.png">Mapping figure</a><a href="table5_real.csv">Mapping CSV</a>
<a href="aig_cuts.csv">AIG and cuts CSV</a></nav>
<section><h2>Mapping results</h2><div class="scroll"><table>
<thead><tr><th>Mapping</th><th>Cell area ↓</th><th>Worst arrival ↓</th>
<th>GB4 cells used</th><th>Equivalence</th></tr></thead><tbody>{''.join(metrics)}</tbody></table></div>
<p class="muted">Each arrow reads baseline → extended. Equivalence checks compare each mapped netlist with the original logic.</p>
<figure><img src="mapping-change.png" alt="Percent change in area and delay for Scripts A and B">
<figcaption>Values left of zero mean smaller area or lower delay. N/A means the baseline is zero.</figcaption></figure></section>
<section><h2>AIG before and after restructuring</h2>{cone}
<figure><img src="aig-counts.png" alt="AND-node and checked-cut counts before and after ABC">
<figcaption>Counts cover the full AIG. The logic drawing shows only the selected output cone.</figcaption></figure>
<div class="scroll"><table><thead><tr><th>AIG</th><th>AND nodes</th><th>Cuts checked</th>
<th>PN classes</th><th>Cut failures</th></tr></thead><tbody>{graph_rows}</tbody></table></div>
<p><a href="discovery/synth.aig">Synthesized AIG</a> · <a href="discovery/restructured.aig">Restructured AIG</a></p></section>
""")
    return page


def suite_report(out, cases):
    rows = []
    for name, (result, detail) in cases.items():
        if result == "Pass":
            report = Path(detail)
            link = f'<a href="{escape(report.relative_to(out).as_posix(), quote=True)}">View mapping and AIGs</a>'
            with (report.parent / "table5_real.csv").open() as stream:
                mappings = list(csv.DictReader(stream))
            cells = []
            for key, unit, digits in (("um2", "µm²", 2), ("delay_ns", "ns", 3)):
                best = {
                    f"{side}_{key}": min(float(row[f"{side}_{key}"]) for row in mappings)
                    for side in ("baseline", "extended")
                }
                values, change, color = _comparison(best, key, unit, digits)
                cells.append(f"<td>{values}<small style='color:{color}'>{change}</small></td>")
            comparison = "".join(cells)
            status = "good"
        else:
            link = escape(detail)
            comparison = "<td>—</td><td>—</td>"
            status = "bad"
        rows.append(
            f"<tr><th>{escape(name)}</th><td class='{status}'>{result}</td>{comparison}<td>{link}</td></tr>"
        )
    passed = sum(result == "Pass" for result, _ in cases.values())
    page = out / "index.html"
    _page(page, "M3 benchmark suite", f"{passed} of {len(cases)} cases passed · Select a case to inspect its live results", f"""
<section><h2>Test cases</h2><div class="scroll"><table><thead><tr><th>Design</th><th>Status</th>
<th>Best area ↓</th><th>Best worst arrival ↓</th><th>Evidence</th>
</tr></thead><tbody>{''.join(rows)}</tbody></table></div>
<p class="muted">Each comparison uses the better of Scripts A and B for that metric, on each library separately.</p></section>
""")
    return page


def open_dashboard(path):
    import shutil
    import subprocess
    import webbrowser

    try:
        if shutil.which("explorer.exe") and shutil.which("wslpath"):
            windows_path = subprocess.check_output(["wslpath", "-w", str(path)], text=True).strip()
            subprocess.Popen(["explorer.exe", windows_path])
        elif not webbrowser.open(path.as_uri()):
            print(f"Open the dashboard in your browser: {path}", flush=True)
    except (OSError, subprocess.SubprocessError):
        print(f"Open the dashboard in your browser: {path}", flush=True)

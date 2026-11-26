"""Reporting: text tables, ASCII bar charts, CSV files and PNG charts.

PNG charts need matplotlib. If it is not installed the program still runs:
it prints ASCII charts, saves the CSV files and logs a warning.
"""

import csv
from pathlib import Path

from .logger import PROJECT_ROOT, get_logger

log = get_logger("reporting")

OUTPUT_DIR = PROJECT_ROOT / "output"
CHART_DIR = OUTPUT_DIR / "charts"
CSV_DIR = OUTPUT_DIR / "csv"
TRACE_DIR = OUTPUT_DIR / "traces"


def ensure_dirs(base=None):
    base = Path(base) if base else OUTPUT_DIR
    for d in (base, base / "charts", base / "csv", base / "traces"):
        d.mkdir(parents=True, exist_ok=True)
    return base


def table(headers, rows, title=None):
    """Return an aligned text table."""
    rows = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(str(h)), *(len(r[i]) for r in rows)) if rows else len(str(h))
              for i, h in enumerate(headers)]
    line = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = []
    if title:
        out.append(title)
    out.append(line)
    out.append("| " + " | ".join(str(h).ljust(w) for h, w in zip(headers, widths)) + " |")
    out.append(line)
    # a column is right-aligned when every value in it is a number ("-" and blanks allowed)
    right = [all(_numeric(r[i]) or r[i] in ("", "-") for r in rows) and any(_numeric(r[i]) for r in rows)
             for i in range(len(headers))]
    for r in rows:
        out.append("| " + " | ".join(v.rjust(w) if right[i] else v.ljust(w)
                                     for i, (v, w) in enumerate(zip(r, widths))) + " |")
    out.append(line)
    return "\n".join(out)


def _numeric(text):
    try:
        float(text)
        return True
    except ValueError:
        return False


def ascii_bars(title, labels, values, unit="", width=40):
    """Horizontal ASCII bar chart; the best (lowest) value is marked."""
    if not values:
        return title + "\n(no data)"
    top = max(values) or 1
    best = min(values)
    pad = max(len(str(l)) for l in labels)
    out = [title]
    for label, value in zip(labels, values):
        bar = "#" * max(1, round(width * value / top)) if value > 0 else ""
        mark = "  <- lowest" if value == best else ""
        out.append(f"  {str(label).ljust(pad)} | {bar} {value}{unit}{mark}")
    return "\n".join(out)


def save_csv(path, headers, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
    log.info("Saved %s", path.name)
    return path


def save_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _safe_chart(func):
    """A chart that fails must never stop the program: log it and carry on."""
    import functools

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            log.error("Chart %s failed: %s", func.__name__, exc)
            return None
    return wrapper


def _plt():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        return plt
    except Exception as exc:  # ImportError or a broken backend
        log.warning("matplotlib not available (%s): PNG charts skipped", exc)
        return None


@_safe_chart
def bar_chart(path, title, categories, series, ylabel, xlabel=""):
    """Grouped bar chart. series = {"Avg waiting": [..], "Avg turnaround": [..]}"""
    plt = _plt()
    if plt is None:
        return None
    n = len(series)
    width = 0.8 / n
    fig, ax = plt.subplots(figsize=(9, 4.8))
    colors = ["#2a6f97", "#e07a5f", "#81b29a", "#f2cc8f", "#6d597a"]
    for k, (name, values) in enumerate(series.items()):
        xs = [i + (k - (n - 1) / 2) * width for i in range(len(categories))]
        bars = ax.bar(xs, values, width, label=name, color=colors[k % len(colors)])
        for bar, value in zip(bars, values):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height(), f"{value:g}",
                    ha="center", va="bottom", fontsize=8)
    ax.set_xticks(range(len(categories)))
    ax.set_xticklabels(categories)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    ax.grid(axis="y", alpha=0.3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    if n > 1:
        ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved chart %s", Path(path).name)
    return path


@_safe_chart
def line_chart(path, title, xvalues, series, xlabel, ylabel):
    plt = _plt()
    if plt is None:
        return None
    fig, ax = plt.subplots(figsize=(9, 4.8))
    markers = ["o", "s", "^", "D", "v"]
    for k, (name, values) in enumerate(series.items()):
        ax.plot(xvalues, values, marker=markers[k % len(markers)], label=name, linewidth=2)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_xticks(xvalues)
    ax.grid(alpha=0.3)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved chart %s", Path(path).name)
    return path


@_safe_chart
def gantt_chart(path, title, gantt):
    """Draw a Gantt chart as a horizontal timeline."""
    plt = _plt()
    if plt is None:
        return None
    labels = [g[0] for g in gantt if g[0] != "IDLE"]
    palette = ["#2a6f97", "#e07a5f", "#81b29a", "#f2cc8f", "#6d597a", "#3d405b", "#a8dadc", "#b5838d"]
    colors = {pid: palette[i % len(palette)] for i, pid in enumerate(dict.fromkeys(labels))}
    fig, ax = plt.subplots(figsize=(10, 1.9))
    for label, s, e in gantt:
        color = "#dddddd" if label == "IDLE" else colors[label]
        ax.barh(0, e - s, left=s, color=color, edgecolor="white", height=0.6)
        light = label == "IDLE" or color in ("#f2cc8f", "#a8dadc", "#81b29a")
        ax.text((s + e) / 2, 0, label, ha="center", va="center", fontsize=8,
                color="black" if light else "white")
    ticks = sorted({g[1] for g in gantt} | {g[2] for g in gantt})
    ax.set_xticks(ticks)
    ax.tick_params(axis="x", labelsize=7)
    ax.set_yticks([])
    ax.set_title(title, fontsize=11, fontweight="bold")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


@_safe_chart
def disk_path_chart(path, title, results):
    """Head position against service order for each disk algorithm."""
    plt = _plt()
    if plt is None:
        return None
    count = len(results)
    cols = 3
    rows = (count + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(11, 3.2 * rows), sharey=True)
    axes = axes.flatten() if count > 1 else [axes]
    for ax, r in zip(axes, results):
        ax.plot(range(len(r.path)), r.path, marker="o", color="#2a6f97", linewidth=1.6, markersize=4)
        ax.set_title(f"{r.algorithm}: {r.total} cylinders", fontsize=10)
        ax.set_xlabel("Step")
        ax.grid(alpha=0.3)
    for ax in axes[count:]:
        ax.axis("off")
    axes[0].set_ylabel("Cylinder")
    fig.suptitle(title, fontsize=12, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    log.info("Saved chart %s", Path(path).name)
    return path

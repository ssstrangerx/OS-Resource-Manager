"""Draws docs/architecture.png and docs/workflow.png (run: python3 docs/make_diagrams.py)."""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

HERE = Path(__file__).resolve().parent
BLUE, ORANGE, GREEN, GREY, PURPLE = "#d6e6f2", "#fbe3d6", "#dcefe3", "#eeeeee", "#e8e0f0"
EDGE = "#3d405b"


def box(ax, x, y, w, h, title, sub="", color=BLUE):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                facecolor=color, edgecolor=EDGE, linewidth=1))
    ax.text(x + w / 2, y + h / 2 + (0.13 if sub else 0), title, ha="center", va="center",
            fontsize=10, fontweight="bold", color="#1f2a44")
    if sub:
        ax.text(x + w / 2, y + h / 2 - 0.17, sub, ha="center", va="center", fontsize=7.5, color="#333333")


def arrow(ax, x1, y1, x2, y2, label=""):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color=EDGE, lw=1.1))
    if label:
        ax.text((x1 + x2) / 2 + 0.05, (y1 + y2) / 2, label, fontsize=7, color="#555555", va="center")


def architecture():
    fig, ax = plt.subplots(figsize=(11, 7.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 7.2)
    ax.axis("off")
    ax.text(5.5, 6.95, "OS Resource Manager: architecture", ha="center", fontsize=13, fontweight="bold")

    box(ax, 0.3, 5.7, 2.0, 0.8, "User", "terminal (Ubuntu / WSL)", GREY)
    box(ax, 2.8, 5.7, 2.1, 0.8, "run.sh", "Bash launcher", ORANGE)
    box(ax, 5.4, 5.7, 2.4, 0.8, "main.py", "menu + --analyze CLI", BLUE)
    box(ax, 8.4, 5.7, 2.4, 0.8, "scripts/*.sh", "sysinfo + ps_to_dataset", ORANGE)
    arrow(ax, 2.3, 6.1, 2.8, 6.1)
    arrow(ax, 4.9, 6.1, 5.4, 6.1)
    arrow(ax, 7.8, 6.1, 8.4, 6.1)
    ax.text(8.1, 6.58, "subprocess", fontsize=7, color="#555555", ha="center")

    ax.add_patch(FancyBboxPatch((0.3, 2.75), 10.5, 2.55, boxstyle="round,pad=0.02,rounding_size=0.1",
                                facecolor="white", edgecolor="#999999", linestyle="--"))
    ax.text(0.5, 5.08, "osrm package (Python)", fontsize=9, fontweight="bold", color="#555555")
    mods = [("scheduling.py", "FCFS SJF SRTF\nPriority NP/P  RR"),
            ("memory.py", "FIFO LRU Optimal\nfirst / best / worst fit"),
            ("deadlock.py", "Banker's safety + request\ndetection + recovery"),
            ("storage.py", "FCFS SSTF SCAN\nC-SCAN LOOK C-LOOK")]
    for i, (t, s) in enumerate(mods):
        box(ax, 0.6 + i * 2.55, 3.85, 2.3, 1.0, t, s, GREEN)
        arrow(ax, 6.6, 5.7, 1.75 + i * 2.55, 4.85)
    box(ax, 0.6, 2.95, 3.0, 0.65, "validation.py", "checks every input", PURPLE)
    box(ax, 3.95, 2.95, 3.0, 0.65, "datasets.py", "loads data/*.json", PURPLE)
    box(ax, 7.3, 2.95, 3.2, 0.65, "logger.py", "logs/activity.log", PURPLE)

    box(ax, 2.0, 1.45, 3.3, 0.9, "analysis.py", "runs all modules, compares", BLUE)
    box(ax, 5.9, 1.45, 3.3, 0.9, "reporting.py", "tables, ASCII + PNG charts, CSV", BLUE)
    arrow(ax, 5.3, 1.9, 5.9, 1.9)
    arrow(ax, 3.65, 2.75, 3.65, 2.35, "imports")
    arrow(ax, 9.9, 2.95, 9.9, 1.0, "writes")

    box(ax, 0.3, 0.2, 3.3, 0.8, "data/", "scheduling, memory, deadlock,\nstorage .json", GREY)
    box(ax, 4.0, 0.2, 3.3, 0.8, "output/", "charts, csv, traces,\nanalysis_report.md", GREY)
    box(ax, 7.7, 0.2, 3.1, 0.8, "logs/", "activity.log (Python + Bash)", GREY)
    arrow(ax, 1.95, 1.0, 2.6, 1.45)
    arrow(ax, 7.55, 1.45, 5.65, 1.0)
    fig.savefig(HERE / "architecture.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def workflow():
    fig, ax = plt.subplots(figsize=(11, 2.4))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 2.4)
    ax.axis("off")
    steps = [("Input", "JSON dataset, manual\nentry or live ps", GREY),
             ("Validate", "ValidationError\non bad input", PURPLE),
             ("Simulate", "algorithm engine\nper module", GREEN),
             ("Measure", "WT TAT RT, faults,\nsafe seq, head moves", GREEN),
             ("Compare", "tables, ASCII +\nPNG charts", BLUE),
             ("Report", "CSV, traces,\nanalysis_report.md", GREY)]
    w = 1.55
    for i, (t, s, c) in enumerate(steps):
        x = 0.2 + i * 1.8
        box(ax, x, 0.7, w, 1.1, t, s, c)
        if i:
            arrow(ax, x - 0.25, 1.25, x, 1.25)
    ax.text(5.5, 0.3, "Every step writes to logs/activity.log; errors are shown and logged, and the menu keeps running.",
            ha="center", fontsize=8.5, color="#444444")
    fig.savefig(HERE / "workflow.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    workflow()
    print("Saved docs/architecture.png and docs/workflow.png")

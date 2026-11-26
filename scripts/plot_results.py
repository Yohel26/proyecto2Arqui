#!/usr/bin/env python3
"""Generador automático de gráficos para E1, E2 y E4 a partir de los CSV.

Lee los CSV generados por scripts/parse_stats.py y produce figuras listas para
el informe IEEE y la presentación de avance en report/figures/.

Uso:
    python3 scripts/plot_results.py                 # Genera todos los disponibles
    python3 scripts/plot_results.py --exp e1        # Solo E1
    python3 scripts/plot_results.py --exp e2 --out-dir report/figures
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

# Estilo limpio y legible para informe IEEE y diapositivas
plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "legend.fontsize": 9,
        "axes.grid": True,
        "grid.alpha": 0.3,
    }
)


# ---------------------------------------------------------------------------
# Bloque 1: Gráficos de E1 (Línea base: TimingSimple, Minor, O3)
# ---------------------------------------------------------------------------
def plot_e1(csv_path: Path, out_dir: Path) -> None:
    """Genera gráficos de IPC y tasas de fallo L1D/L2 para E1."""
    df = pd.read_csv(csv_path)

    # Extrae nombre de CPU y tamaño N desde la columna config (ej. ArmO3CPU_N128)
    parsed = df["config"].str.extract(r"^(?P<cpu>.+)_N(?P<N>\d+)$")
    df["cpu"] = parsed["cpu"]
    df["N"] = parsed["N"].astype(int)

    cpu_order = ["ArmTimingSimpleCPU", "ArmMinorCPU", "ArmO3CPU"]
    cpu_labels = {"ArmTimingSimpleCPU": "TimingSimple", "ArmMinorCPU": "Minor", "ArmO3CPU": "O3"}
    sizes = sorted(df["N"].unique())

    # Figura 1: IPC por modelo de CPU y tamaño N
    fig, ax = plt.subplots(figsize=(7, 4.2))
    x = range(len(cpu_order))
    width = 0.35

    for idx, n in enumerate(sizes):
        sub = df[df["N"] == n].set_index("cpu").reindex(cpu_order)
        offsets = [pos + (idx - (len(sizes) - 1) / 2) * width for pos in x]
        bars = ax.bar(offsets, sub["ipc_avg"], width=width, label=f"N = {n}")
        for bar in bars:
            h = bar.get_height()
            if pd.notna(h):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    h,
                    f"{h:.2f}",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )

    ax.set_xticks(list(x))
    ax.set_xticklabels([cpu_labels.get(c, c) for c in cpu_order])
    ax.set_ylabel("IPC (instrucciones / ciclo)")
    ax.set_title("E1: Línea base de 1 núcleo — IPC por modelo de CPU")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "e1_ipc.png")
    plt.close(fig)

    # Figura 2: Tasas de fallo L1D y L2 (%)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.0), sharey=False)
    for ax_idx, (col, title) in enumerate(
        [("dcache_miss_rate", "Tasa de fallo L1D (%)"), ("l2_miss_rate", "Tasa de fallo L2 (%)")]
    ):
        ax = axes[ax_idx]
        for idx, n in enumerate(sizes):
            sub = df[df["N"] == n].set_index("cpu").reindex(cpu_order)
            offsets = [pos + (idx - (len(sizes) - 1) / 2) * width for pos in x]
            ax.bar(offsets, sub[col] * 100.0, width=width, label=f"N = {n}")
        ax.set_xticks(list(x))
        ax.set_xticklabels([cpu_labels.get(c, c) for c in cpu_order])
        ax.set_ylabel("Fallos (%)")
        ax.set_title(title)
        ax.legend()

    fig.suptitle("E1: Tasas de fallo de caché por modelo de CPU")
    fig.tight_layout()
    fig.savefig(out_dir / "e1_cache_miss.png")
    plt.close(fig)
    print(f"[plot] E1 guardado en {out_dir}")


# ---------------------------------------------------------------------------
# Bloque 2: Gráficos de E2 (Superescalar: ancho 1..8 x ROB 32, 64, 192)
# ---------------------------------------------------------------------------
def plot_e2(csv_path: Path, out_dir: Path) -> None:
    """Genera gráficos de saturación de IPC y cuellos de botella (IQ/ROB/BP) para E2."""
    df = pd.read_csv(csv_path)

    # Extrae ancho (w) y ROB desde config (ej. w4_rob64_N128)
    parsed = df["config"].str.extract(r"^w(?P<width>\d+)_rob(?P<rob>\d+)_N(?P<N>\d+)$")
    df["width"] = parsed["width"].astype(int)
    df["rob"] = parsed["rob"].astype(int)
    df = df.sort_values(["rob", "width"])

    robs = sorted(df["rob"].unique())
    widths = sorted(df["width"].unique())

    # Figura 1: IPC vs ancho superescalar para cada tamaño de ROB
    fig, ax = plt.subplots(figsize=(7, 4.3))
    for rob in robs:
        sub = df[df["rob"] == rob]
        ax.plot(sub["width"], sub["ipc_avg"], marker="o", linewidth=2, label=f"ROB = {rob}")

    ax.set_xticks(widths)
    ax.set_xlabel("Ancho superescalar (fetch/decode/rename/issue/commit)")
    ax.set_ylabel("IPC (instrucciones / ciclo)")
    ax.set_title("E2: Escalabilidad superescalar — IPC vs. ancho y ROB")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_dir / "e2_ipc_superscalar.png")
    plt.close(fig)

    # Figura 2: Eventos de saturación (IQ full, ROB full, fallos de predicción)
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.0))
    panels = [
        ("rename_iq_full", "Bloqueos por IQ lleno (rename)", "Eventos"),
        ("rename_rob_full", "Bloqueos por ROB lleno (rename)", "Eventos"),
        ("bp_mispred_rate", "Tasa de fallo de predicción (%)", "%"),
    ]

    for ax, (col, title, ylabel) in zip(axes, panels):
        for rob in robs:
            sub = df[df["rob"] == rob]
            y = sub[col] * 100.0 if col == "bp_mispred_rate" else sub[col]
            ax.plot(sub["width"], y, marker="s", label=f"ROB = {rob}")
        ax.set_xticks(widths)
        ax.set_xlabel("Ancho")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.legend()

    fig.suptitle("E2: Causas de saturación del ILP en ArmO3CPU")
    fig.tight_layout()
    fig.savefig(out_dir / "e2_bottlenecks.png")
    plt.close(fig)
    print(f"[plot] E2 guardado en {out_dir}")


# ---------------------------------------------------------------------------
# Bloque 3: Gráficos de E4 (Multiprocesador: Speedup, Eficiencia y Ley de Amdahl)
# ---------------------------------------------------------------------------
def estimate_amdahl_serial_fraction(cores: pd.Series, speedup: pd.Series) -> float:
    """Estima la fracción serial f de la ley de Amdahl usando los puntos con p > 1."""
    # Despeje de S(p) = 1 / (f + (1 - f)/p)  =>  f = (1/S(p) - 1/p) / (1 - 1/p)
    mask = cores > 1
    if not mask.any():
        return 0.0
    p = cores[mask].astype(float)
    s = speedup[mask].astype(float)
    f_vals = ((1.0 / s) - (1.0 / p)) / (1.0 - (1.0 / p))
    # Se acota entre 0 y 1 por si hay ruido o efecto superlineal de caché
    return float(f_vals.clip(0.0, 1.0).mean())


def plot_e4(csv_path: Path, out_dir: Path) -> None:
    """Genera gráficos de speedup vs. ideal, ley de Amdahl y eficiencia para E4."""
    df = pd.read_csv(csv_path)

    parsed = df["config"].str.extract(r"^n(?P<cores>\d+)_N(?P<N>\d+)$")
    df["cores"] = parsed["cores"].astype(int)
    df = df.sort_values("cores")

    # Tiempo base con 1 núcleo (en ciclos de la ROI)
    t1_row = df[df["cores"] == 1]
    if t1_row.empty:
        raise ValueError("e4.csv debe incluir la corrida de 1 núcleo (n1_N...) como línea base.")
    t1 = float(t1_row["numCycles"].iloc[0])

    df["speedup"] = t1 / df["numCycles"].astype(float)
    df["efficiency_pct"] = (df["speedup"] / df["cores"].astype(float)) * 100.0

    f_serial = estimate_amdahl_serial_fraction(df["cores"], df["speedup"])
    p_grid = sorted(df["cores"].unique())
    amdahl_curve = [1.0 / (f_serial + (1.0 - f_serial) / p) for p in p_grid]

    fig, axes = plt.subplots(1, 2, figsize=(10.5, 4.2))

    # Panel izquierdo: Speedup medido vs. ideal vs. Amdahl
    ax0 = axes[0]
    ax0.plot(df["cores"], df["speedup"], marker="o", linewidth=2, label="Speedup medido")
    ax0.plot(p_grid, p_grid, linestyle="--", color="gray", label="Speedup ideal (S = p)")
    ax0.plot(
        p_grid,
        amdahl_curve,
        linestyle=":",
        linewidth=2,
        label=f"Amdahl (f_serial ≈ {f_serial:.3f})",
    )
    ax0.set_xticks(p_grid)
    ax0.set_xlabel("Número de núcleos (ArmO3CPU ancho 2)")
    ax0.set_ylabel("Speedup respecto a 1 núcleo")
    ax0.set_title("E4: Speedup vs. número de núcleos")
    ax0.legend()

    # Panel derecho: Eficiencia (%) y fallos de L2
    ax1 = axes[1]
    ax1.plot(df["cores"], df["efficiency_pct"], marker="s", linewidth=2, color="tab:green")
    ax1.set_xticks(p_grid)
    ax1.set_ylim(0, 110)
    ax1.set_xlabel("Número de núcleos")
    ax1.set_ylabel("Eficiencia paralela (%)")
    ax1.set_title("E4: Eficiencia paralela (Speedup / p)")

    fig.tight_layout()
    fig.savefig(out_dir / "e4_speedup_efficiency.png")
    plt.close(fig)
    print(f"[plot] E4 guardado en {out_dir} (f_serial estimado = {f_serial:.4f})")


# ---------------------------------------------------------------------------
# Bloque 4: Punto de entrada CLI
# ---------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genera gráficos de E1, E2 y E4 desde los CSV de results/."
    )
    parser.add_argument(
        "--exp",
        choices=["e1", "e2", "e4", "all"],
        default="all",
        help="Experimento a graficar (por defecto: all).",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results"),
        help="Carpeta raíz de resultados (por defecto: results).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("report/figures"),
        help="Carpeta donde se guardan las figuras PNG (por defecto: report/figures).",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    tasks = {
        "e1": (args.results_dir / "e1" / "e1.csv", plot_e1),
        "e2": (args.results_dir / "e2" / "e2.csv", plot_e2),
        "e4": (args.results_dir / "e4" / "e4.csv", plot_e4),
    }

    selected = list(tasks.keys()) if args.exp == "all" else [args.exp]
    for exp_name in selected:
        csv_path, fn = tasks[exp_name]
        if not csv_path.is_file():
            print(f"[skip] No existe aún {csv_path}; se omite {exp_name.upper()}.")
            continue
        fn(csv_path, args.out_dir)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

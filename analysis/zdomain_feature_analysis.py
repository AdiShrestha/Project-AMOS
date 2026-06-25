"""
zdomain_feature_analysis.py — Z-domain post-hoc analysis (Section 24).

Applies Project 1's frozen-time Z-domain analysis methodology to the real,
logged alpha[n] and W[n] traces produced by AdaptiveFeatureWindowOp during
an actual run against the Taobao replay — NOT a synthetic signal.

This is what makes the Z-domain section an empirical contribution: the same
frozen-time machinery (pole-zero, magnitude/phase, group delay, time-varying
frequency-response heatmap), pointed at real logged data from a real system
under real backpressure.

Experiment 6 output: Pearson correlation between N_alpha[n] and W[n],
reported honestly regardless of magnitude (Decision 3, Section 6 point 1).

Usage:
    python zdomain_feature_analysis.py \\
        --trace results/raw/trace_adaptive_seed0.csv \\
        --out-heatmap results/figures/passband_narrowing_heatmap.png \\
        [--out-corr results/figures/wa_correlation.png]
"""

import argparse
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")  # non-interactive backend for headless runs
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from scipy.signal import freqz


# ── Z-domain machinery (identical to Project 1's frozen-time analysis) ────────

def single_pole_response(alpha: float, n_freqs: int = 512):
    """
    H(z) = alpha / (1 - (1-alpha) z^{-1})
    Pole at z = 1 - alpha. Returns (omega, |H|, unwrapped_phase).
    Identical transfer function to Project 1's load_adaptive_iir analysis.
    """
    b = [alpha]
    a = [1.0, -(1.0 - alpha)]
    w, h = freqz(b, a, worN=n_freqs)
    return w, np.abs(h), np.unwrap(np.angle(h))


def group_delay_analytic(alpha: float, w: np.ndarray) -> np.ndarray:
    """
    Closed-form group delay for a single real pole p = 1 - alpha:
      tau_g(omega) = p(p - cos(omega)) / (1 - 2p cos(omega) + p^2)
    """
    p = 1.0 - alpha
    return p * (p - np.cos(w)) / (1.0 - 2.0 * p * np.cos(w) + p**2)


def build_time_varying_heatmap(alpha_trace: np.ndarray, n_freqs: int = 256) -> np.ndarray:
    """
    IMPORTANT MATHEMATICAL CAVEAT (cite in paper, Section 7):
    BPFeat's Mechanism B implements a Linear Time-Variant (LTV) filter because
    alpha[n] changes per-event. Frozen-time Z-domain analysis (treating alpha
    as constant over short windows to compute H(z) = alpha / (1-(1-alpha)z^-1))
    is a known APPROXIMATION for LTV systems — the frozen-time transfer function
    cannot capture the recursive nature of the LTV difference equation (Park &
    Nguyen, UT Austin). This analysis is used strictly as a POST-HOC DIAGNOSTIC
    to visualize how the filter's frequency response varies with measured system
    load (i.e., does high occupancy correlate with a narrowed passband?). It is
    NOT used to design the system or prove stability guarantees. Reviewers with
    DSP backgrounds should be directed to this explicit caveat.
    Reference: S. Park, "Recursive Synthesis of Linear Time-Variant Digital
    Filters via Chebyshev Approximation," UT Austin CVRC.
    
    Stitches one frequency-response column per logged alpha[n] sample.
    Drives from REAL controller output, not a synthetic sweep grid.
    """
    heatmap = np.zeros((n_freqs, len(alpha_trace)))
    for i, a in enumerate(alpha_trace):
        a = max(a, 1e-4)
        _, mag, _ = single_pole_response(a, n_freqs)
        heatmap[:, i] = 20.0 * np.log10(np.maximum(mag, 1e-6))
    return heatmap


def ewma_equivalent_span(alpha_trace: np.ndarray) -> np.ndarray:
    """N = 2/alpha - 1 (Section 7.3 identity)."""
    return 2.0 / np.clip(alpha_trace, 1e-4, None) - 1.0


# ── Plotting ──────────────────────────────────────────────────────────────────

def plot_passband_heatmap(alpha_trace, occupancy_trace, w_trace, heatmap, out_path):
    fig = plt.figure(figsize=(12, 7))
    gs  = gridspec.GridSpec(2, 1, height_ratios=[1, 3], hspace=0.05)

    ax_top  = fig.add_subplot(gs[0])
    ax_main = fig.add_subplot(gs[1], sharex=ax_top)

    # Top panel: occupancy + normalized alpha
    ax_top.plot(occupancy_trace, color="tab:red",   linewidth=0.8, label="Queue occupancy EMA")
    ax_top.plot(alpha_trace / (alpha_trace.max() + 1e-9),
                color="tab:blue", linewidth=0.8, label="α[n] (normalized)")
    ax_top.set_ylabel("Normalized", fontsize=9)
    ax_top.set_ylim(0, 1.2)
    ax_top.legend(loc="upper right", fontsize=8)
    ax_top.grid(alpha=0.3)
    plt.setp(ax_top.get_xticklabels(), visible=False)

    # Main panel: time-varying frequency-response heatmap
    n_freqs = heatmap.shape[0]
    im = ax_main.imshow(
        heatmap, aspect="auto", origin="lower", cmap="magma",
        vmin=-40, vmax=5,
        extent=[0, len(alpha_trace), 0, np.pi])
    ax_main.set_ylabel("Frequency (rad/sample)", fontsize=9)
    ax_main.set_xlabel("Controller sample index n", fontsize=9)
    cbar = fig.colorbar(im, ax=ax_main, pad=0.01)
    cbar.set_label("|H(e^{jω})| (dB)", fontsize=9)

    fig.suptitle(
        "Feature filter passband narrowing under real backpressure\n"
        "(BPFeat — Adaptive architecture — Taobao replay)",
        fontsize=11, fontweight="bold")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[zdomain] Heatmap → {out_path}")


def plot_wa_correlation(n_alpha_trace, w_trace, corr, out_path):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # Time series
    ax = axes[0]
    t  = np.arange(len(w_trace))
    ax.plot(t, w_trace,        color="tab:blue",   linewidth=0.8, label="W[n] (window size)")
    ax.plot(t, n_alpha_trace,  color="tab:orange", linewidth=0.8, label="N_α[n] = 2/α-1")
    ax.set_xlabel("Controller sample index n"); ax.set_ylabel("Events")
    ax.legend(fontsize=9); ax.grid(alpha=0.3)
    ax.set_title("W[n] vs. N_α[n] over time")

    # Scatter
    ax = axes[1]
    ax.scatter(n_alpha_trace, w_trace, alpha=0.3, s=4, color="tab:purple")
    ax.set_xlabel("N_α[n] (EWMA equivalent span)"); ax.set_ylabel("W[n]")
    ax.set_title(f"Pearson r = {corr:.4f}\n"
                 "(Report this value regardless of magnitude — Section 27 Exp. 6)")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[zdomain] W↔α correlation plot → {out_path}")


# ── Pole-zero sweep for Section 7 theory figure ───────────────────────────────

def plot_pole_zero_sweep(out_path: str,
                         alpha_range=(0.02, 0.10, 0.20, 0.30),
                         n_freqs: int = 512):
    """
    Multi-panel frequency response over representative α values.
    Mirrors Project 1's standalone frozen-time sweep figure.
    """
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    colors = plt.cm.plasma(np.linspace(0.1, 0.9, len(alpha_range)))

    w_rad = np.linspace(0, np.pi, n_freqs)
    for ax_idx, (ax, ylabel) in enumerate(zip(axes, ["Magnitude (dB)", "Phase (rad)", "Group delay (samples)"])):
        for alpha, col in zip(alpha_range, colors):
            w, mag, phase = single_pole_response(alpha, n_freqs)
            gd  = group_delay_analytic(alpha, w)
            mag_db = 20.0 * np.log10(np.maximum(mag, 1e-6))
            data = [mag_db, phase, gd][ax_idx]
            ax.plot(w, data, color=col, linewidth=1.2, label=f"α={alpha:.2f}")
        ax.set_xlabel("ω (rad/sample)"); ax.set_ylabel(ylabel)
        ax.legend(fontsize=8); ax.grid(alpha=0.3)
        ax.set_xlim(0, np.pi)

    axes[0].set_title("Magnitude response")
    axes[1].set_title("Phase response")
    axes[2].set_title("Group delay")
    fig.suptitle("Single-pole EMA frequency response (frozen-time analysis)", fontweight="bold")
    fig.tight_layout()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[zdomain] Pole-zero sweep → {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace",       required=True,
                    help="Controller trace CSV: wall_ns,w,alpha,occupancy")
    ap.add_argument("--out-heatmap", required=True)
    ap.add_argument("--out-corr",    default="")
    ap.add_argument("--out-sweep",   default="")
    args = ap.parse_args()

    trace = np.genfromtxt(args.trace, delimiter=",", names=True, dtype=None, encoding="utf-8")

    alpha_trace     = trace["alpha"].astype(np.float64)
    occupancy_trace = trace["occupancy"].astype(np.float64)
    w_trace         = trace["w"].astype(np.float64)

    print(f"[zdomain] Loaded {len(alpha_trace):,} trace samples")
    print(f"  alpha range: [{alpha_trace.min():.4f}, {alpha_trace.max():.4f}]")
    print(f"  W range:     [{int(w_trace.min())}, {int(w_trace.max())}]")

    heatmap = build_time_varying_heatmap(alpha_trace)
    plot_passband_heatmap(alpha_trace, occupancy_trace, w_trace, heatmap, args.out_heatmap)

    # Experiment 6: W↔α Pearson correlation
    n_alpha_trace = ewma_equivalent_span(alpha_trace)
    corr = np.corrcoef(n_alpha_trace, w_trace)[0, 1]
    print(f"\n[zdomain] Experiment 6 — W↔α empirical equivalence:")
    print(f"  Pearson correlation(N_alpha[n], W[n]) = {corr:.4f}")
    print("  NOTE: Report this value honestly in the paper regardless of magnitude.")
    print("  A weak correlation is a legitimate finding, not a result to suppress.")

    n_alpha_sanity_calm   = 2.0 / 0.02 - 1.0   # α_min → N=99
    n_alpha_sanity_stress = 2.0 / 0.30 - 1.0   # α_max → N≈5.67
    print(f"\n  Sanity check (Section 7.5):")
    print(f"    Calm    (α=0.02): N_α = {n_alpha_sanity_calm:.1f}  events of effective memory")
    print(f"    Stressed(α=0.30): N_α = {n_alpha_sanity_stress:.2f} events of effective memory")
    print(f"    W calm  (W_max=256) shrinks to W_min=8 → factor {256/8:.0f}×")
    print(f"    N_α shrinks {n_alpha_sanity_calm/n_alpha_sanity_stress:.1f}× — static mismatch stated upfront (Section 7.5)")

    if args.out_corr:
        plot_wa_correlation(n_alpha_trace, w_trace, corr, args.out_corr)

    if args.out_sweep:
        plot_pole_zero_sweep(args.out_sweep)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Generate a lightweight SVG snapshot of measured accuracy and latency metrics."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CNN_METRICS = ROOT / "build" / "training_metrics_cnn.json"
EMBEDDED_CNN_METRICS = ROOT / "build" / "training_metrics_cnn_embedded.json"
SERIAL_LOG = ROOT / "build" / "serial.log"
COMMITTED_METRICS = ROOT / "docs" / "assets" / "metrics_data.json"
OUT_DIR = ROOT / "docs" / "assets"
OUT_SVG = OUT_DIR / "metrics_snapshot.svg"
OUT_LATENCY_SVG = OUT_DIR / "latency_snapshot.svg"

CPU_HZ_ESTIMATE = 8_000_000


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def parse_bench(log_text: str) -> dict:
    lines = [l.strip() for l in log_text.splitlines() if l.startswith("ML_BENCH ")]
    if not lines:
        return {}

    samples = 0
    correct = 0
    avg_ticks_vals = []

    for line in lines:
        fields = dict(re.findall(r"(\w+)=([0-9]+)", line))
        s = int(fields.get("samples", "0"))
        c = int(fields.get("correct", "0"))
        t = int(fields.get("avg_ticks", "0"))
        samples += s
        correct += c
        avg_ticks_vals.append(t)

    avg_ticks = sum(avg_ticks_vals) / len(avg_ticks_vals)
    acc = (correct / samples) * 100.0 if samples else 0.0
    per_inf_ms = (avg_ticks / CPU_HZ_ESTIMATE) * 1000.0
    samples_per_bench = samples / len(lines)
    batch_ms = per_inf_ms * samples_per_bench

    return {
        "samples": samples,
        "correct": correct,
        "accuracy_pct": acc,
        "avg_ticks": avg_ticks,
        "per_inf_ms": per_inf_ms,
        "batch_ms": batch_ms,
    }


def svg_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def main() -> None:
    committed = load_json(COMMITTED_METRICS)
    cnn = load_json(CNN_METRICS) or committed.get("cnn", {})
    embedded = load_json(EMBEDDED_CNN_METRICS) or committed.get("cnn", {})
    bench = parse_bench(SERIAL_LOG.read_text() if SERIAL_LOG.exists() else "") or committed.get("bench", {})

    lines = [
        "QEMU Cortex-M Edge-ML Metrics Snapshot",
        "Measured on: 2026-03-26",
        f"TensorFlow CNN accuracy: {cnn.get('test_accuracy', 0.0) * 100:.2f}%",
        f"TensorFlow CNN export accuracy: {embedded.get('test_accuracy', 0.0) * 100:.2f}%",
        f"On-target accuracy: {bench.get('accuracy_pct', 0.0):.2f}% ({bench.get('correct', 0)}/{bench.get('samples', 0)})",
        f"Avg inference latency (est): {bench.get('per_inf_ms', 0.0):.2f} ms",
        f"Avg batch latency (est, 100 samples): {bench.get('batch_ms', 0.0):.2f} ms",
    ]

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    width = 920
    height = 280
    y0 = 48
    dy = 30

    text_nodes = []
    for i, line in enumerate(lines):
        y = y0 + i * dy
        weight = "700" if i == 0 else "400"
        size = 24 if i == 0 else 20
        text_nodes.append(
            f'<text x="32" y="{y}" font-family="Menlo, Consolas, monospace" font-size="{size}" font-weight="{weight}" fill="#111">{svg_escape(line)}</text>'
        )

    svg = "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
            '  <rect x="0" y="0" width="100%" height="100%" fill="#f5f7fb"/>',
            '  <rect x="16" y="16" width="888" height="248" rx="10" fill="#ffffff" stroke="#d0d7de"/>',
            *["  " + t for t in text_nodes],
            "</svg>",
        ]
    )

    OUT_SVG.write_text(svg)

    latency_lines = [
        "QEMU Cortex-M Edge-ML Latency Snapshot",
        "Measured on: 2026-03-26",
        f"Avg inference latency (est): {bench.get('per_inf_ms', 0.0):.2f} ms",
        f"Avg batch latency (est, 100 samples): {bench.get('batch_ms', 0.0):.2f} ms",
        f"Avg ticks per inference: {bench.get('avg_ticks', 0.0):.2f}",
        f"Validated samples: {bench.get('samples', 0)}",
    ]

    latency_nodes = []
    for i, line in enumerate(latency_lines):
        y = y0 + i * dy
        weight = "700" if i == 0 else "400"
        size = 24 if i == 0 else 20
        latency_nodes.append(
            f'<text x="32" y="{y}" font-family="Menlo, Consolas, monospace" font-size="{size}" font-weight="{weight}" fill="#111">{svg_escape(line)}</text>'
        )

    latency_svg = "\n".join(
        [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}">',
            '  <rect x="0" y="0" width="100%" height="100%" fill="#f5f7fb"/>',
            '  <rect x="16" y="16" width="888" height="248" rx="10" fill="#ffffff" stroke="#d0d7de"/>',
            *["  " + t for t in latency_nodes],
            "</svg>",
        ]
    )

    OUT_LATENCY_SVG.write_text(latency_svg)
    print(f"Wrote {OUT_SVG}")
    print(f"Wrote {OUT_LATENCY_SVG}")


if __name__ == "__main__":
    main()

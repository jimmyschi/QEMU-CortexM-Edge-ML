#!/usr/bin/env python3
"""Train a small MNIST CNN and export C header + metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import numpy as np
import tensorflow as tf


INPUT_H = 28
INPUT_W = 28
INPUT_C = 1
INPUT_SIZE = INPUT_H * INPUT_W
CONV_K = 3
CONV_OC = 8
CONV_OUT_H = INPUT_H - CONV_K + 1
CONV_OUT_W = INPUT_W - CONV_K + 1
POOL = 2
POOL_OUT_H = CONV_OUT_H // POOL
POOL_OUT_W = CONV_OUT_W // POOL
FLAT = POOL_OUT_H * POOL_OUT_W * CONV_OC
OUT = 10
DEFAULT_EXPORT_SAMPLES = 100


def format_c_array(values: Iterable[float], values_per_line: int = 8) -> str:
    vals = list(values)
    lines = []
    for i in range(0, len(vals), values_per_line):
        chunk = vals[i : i + values_per_line]
        lines.append(", ".join(f"{v:.8e}f" for v in chunk))
    return ",\n    ".join(lines)


def format_u8_array(values: Iterable[int], values_per_line: int = 16) -> str:
    vals = list(values)
    lines = []
    for i in range(0, len(vals), values_per_line):
        chunk = vals[i : i + values_per_line]
        lines.append(", ".join(str(int(v)) for v in chunk))
    return ",\n    ".join(lines)


def build_model() -> tf.keras.Model:
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(INPUT_H, INPUT_W, INPUT_C)),
            tf.keras.layers.Conv2D(CONV_OC, (CONV_K, CONV_K), activation="relu", padding="valid"),
            tf.keras.layers.MaxPooling2D((POOL, POOL)),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(OUT),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )
    return model


def select_eval_subset(y_true: np.ndarray, n_samples: int) -> np.ndarray:
    # Use a fixed leading slice for deterministic, unbiased benchmarking.
    return np.arange(min(n_samples, y_true.shape[0]))


def export_header(
    out_path: Path,
    conv_w: np.ndarray,
    conv_b: np.ndarray,
    fc_w: np.ndarray,
    fc_b: np.ndarray,
    sample_images_u8: np.ndarray,
    sample_labels: np.ndarray,
) -> None:
    # Keras conv kernel layout is [kh, kw, in_c, out_c].
    # Conv2DLayerSingleIn expects [out_c, kh, kw] for in_c=1.
    conv_w_export = np.transpose(conv_w[:, :, 0, :], (2, 0, 1)).reshape(-1)
    conv_b_export = conv_b.reshape(-1)
    fc_w_export = fc_w.reshape(-1)
    fc_b_export = fc_b.reshape(-1)
    imgs_export = sample_images_u8.reshape(-1)
    labels_export = sample_labels.reshape(-1)

    content = f"""#ifndef MNIST_WEIGHTS_GENERATED_H
#define MNIST_WEIGHTS_GENERATED_H

#include <stdint.h>

#define MNIST_INPUT_H {INPUT_H}
#define MNIST_INPUT_W {INPUT_W}
#define MNIST_INPUT_SIZE {INPUT_SIZE}
#define MNIST_CONV_K {CONV_K}
#define MNIST_CONV_OC {CONV_OC}
#define MNIST_POOL {POOL}
#define MNIST_FLAT {FLAT}
#define MNIST_OUT {OUT}
#define MNIST_EVAL_SAMPLES {sample_images_u8.shape[0]}

static const float g_conv_w[{conv_w_export.size}] = {{
    {format_c_array(conv_w_export)}
}};

static const float g_conv_b[{conv_b_export.size}] = {{
    {format_c_array(conv_b_export)}
}};

static const float g_fc_w[{fc_w_export.size}] = {{
    {format_c_array(fc_w_export)}
}};

static const float g_fc_b[{fc_b_export.size}] = {{
    {format_c_array(fc_b_export)}
}};

static const uint8_t g_eval_images_u8[{imgs_export.size}] = {{
    {format_u8_array(imgs_export)}
}};

static const uint8_t g_eval_labels[{labels_export.size}] = {{
    {format_u8_array(labels_export)}
}};

#endif
"""
    out_path.write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and export MNIST CNN to C header")
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--batch-size", type=int, default=128, help="Batch size")
    parser.add_argument(
        "--export-samples",
        type=int,
        default=DEFAULT_EXPORT_SAMPLES,
        help="How many test samples to export for on-device validation",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("src/ml/mnist_weights_generated.h"),
        help="Output C header path",
    )
    parser.add_argument(
        "--metrics-output",
        type=Path,
        default=Path("build/training_metrics_cnn_embedded.json"),
        help="Output JSON file for training metrics",
    )
    args = parser.parse_args()

    tf.random.set_seed(42)
    np.random.seed(42)

    (x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
    x_train_f = (x_train.astype(np.float32) / 255.0)[..., np.newaxis]
    x_test_f = (x_test.astype(np.float32) / 255.0)[..., np.newaxis]

    model = build_model()
    model.fit(
        x_train_f,
        y_train,
        epochs=args.epochs,
        batch_size=args.batch_size,
        validation_split=0.1,
        verbose=2,
    )

    test_loss, test_acc = model.evaluate(x_test_f, y_test, verbose=0)
    print(f"Test loss: {test_loss:.4f}")
    print(f"Test accuracy: {test_acc * 100:.2f}%")
    print(f"Parameter count: {model.count_params()}")

    conv_layer = model.layers[0]
    dense_layer = model.layers[3]

    conv_w, conv_b = conv_layer.get_weights()
    fc_w, fc_b = dense_layer.get_weights()

    logits = model.predict(x_test_f, verbose=0)
    sample_indices = select_eval_subset(y_test, args.export_samples)
    sample_images_u8 = x_test[sample_indices].astype(np.uint8)
    sample_labels = y_test[sample_indices].astype(np.uint8)
    subset_preds = np.argmax(logits[sample_indices], axis=1)
    subset_acc = float(np.mean(subset_preds == sample_labels))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    export_header(
        args.output,
        conv_w=conv_w,
        conv_b=conv_b,
        fc_w=fc_w,
        fc_b=fc_b,
        sample_images_u8=sample_images_u8,
        sample_labels=sample_labels,
    )

    metrics = {
        "model": "mnist_cnn_28x28x1_conv8_pool2_fc10",
        "test_accuracy": float(test_acc),
        "test_loss": float(test_loss),
        "parameter_count": int(model.count_params()),
        "exported_samples": int(sample_indices.shape[0]),
        "exported_subset_accuracy": subset_acc,
    }
    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(metrics, indent=2))

    print(f"Exported weights header: {args.output}")
    print(f"Exported samples: {sample_indices.shape[0]}")
    print(f"Exported subset accuracy: {subset_acc * 100:.2f}%")
    print(f"Saved metrics: {args.metrics_output}")


if __name__ == "__main__":
    main()

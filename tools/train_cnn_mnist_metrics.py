#!/usr/bin/env python3
"""Train a compact CNN on MNIST and emit standalone TensorFlow metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import tensorflow as tf


def build_model() -> tf.keras.Model:
    model = tf.keras.Sequential(
        [
            tf.keras.layers.Input(shape=(28, 28, 1)),
            tf.keras.layers.Conv2D(8, (3, 3), activation="relu", padding="valid"),
            tf.keras.layers.MaxPooling2D((2, 2)),
            tf.keras.layers.Flatten(),
            tf.keras.layers.Dense(10),
        ]
    )
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-3),
        loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=["accuracy"],
    )
    return model


def main() -> None:
    parser = argparse.ArgumentParser(description="Train CNN MNIST and save metrics")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--metrics-output", type=Path, default=Path("build/training_metrics_cnn.json"))
    args = parser.parse_args()

    tf.random.set_seed(42)
    np.random.seed(42)

    (x_train, y_train), (x_test, y_test) = tf.keras.datasets.mnist.load_data()
    x_train = np.expand_dims(x_train.astype(np.float32) / 255.0, axis=-1)
    x_test = np.expand_dims(x_test.astype(np.float32) / 255.0, axis=-1)

    model = build_model()
    model.fit(
        x_train,
        y_train,
        epochs=args.epochs,
        batch_size=args.batch_size,
        validation_split=0.1,
        verbose=2,
    )

    test_loss, test_acc = model.evaluate(x_test, y_test, verbose=0)
    metrics = {
        "model": "mnist_cnn_conv8_pool_dense10",
        "test_accuracy": float(test_acc),
        "test_loss": float(test_loss),
        "parameter_count": int(model.count_params()),
    }

    args.metrics_output.parent.mkdir(parents=True, exist_ok=True)
    args.metrics_output.write_text(json.dumps(metrics, indent=2))

    print(f"Test accuracy: {test_acc * 100:.2f}%")
    print(f"Parameter count: {model.count_params()}")
    print(f"Saved metrics: {args.metrics_output}")


if __name__ == "__main__":
    main()

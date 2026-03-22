#!/usr/bin/env python3
"""
QMP Automated Test Harness
Connects to a running QEMU ARM Cortex-M3 instance via QMP socket,
queries machine state, and validates firmware execution.
"""

import socket
import json
import time
import sys

QMP_SOCK = "build/qmp.sock"
SERIAL_LOG = "build/serial.log"
CPU_HZ_ESTIMATE = 8_000_000

def qmp_connect(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    s.settimeout(5.0)
    return s

def qmp_recv(s):
    buf = b""
    while True:
        try:
            chunk = s.recv(4096)
            if not chunk:
                break
            buf += chunk
            # QMP messages are newline-terminated JSON
            if b"\n" in buf:
                break
        except socket.timeout:
            break
    return buf.decode("utf-8").strip()

def qmp_send(s, cmd):
    msg = json.dumps(cmd) + "\n"
    s.sendall(msg.encode("utf-8"))
    return qmp_recv(s)

def read_serial_log(path):
    with open(path, "r") as f:
        return f.read()

def check_firmware_health(log):
    lines = log.strip().splitlines()
    results = {}

    # Check boot banner
    results["boot_ok"] = any("BOOT OK" in l for l in lines)
    results["identity"] = any("James Schiavo" in l for l in lines)
    results["version"] = any(
        ("QMP Emulation Harness" in l) or ("QMP + ML Inference Harness" in l)
        for l in lines
    )

    # Check heartbeat is incrementing
    heartbeats = [l for l in lines if l.startswith("HEARTBEAT")]
    results["heartbeat_count"] = len(heartbeats)
    results["firmware_running"] = len(heartbeats) > 0

    # Verify monotonically increasing (no missed counts)
    if len(heartbeats) >= 2:
        counts = []
        for h in heartbeats:
            try:
                counts.append(int(h.split()[1]))
            except:
                pass
        if counts:
            expected = list(range(counts[0], counts[0] + len(counts)))
            results["heartbeat_sequential"] = (counts == expected)
        else:
            results["heartbeat_sequential"] = False
    else:
        results["heartbeat_sequential"] = False

    return results


def check_ml_telemetry(log):
    lines = log.strip().splitlines()
    bench_lines = [l for l in lines if l.startswith("ML_BENCH ")]

    results = {
        "bench_count": len(bench_lines),
        "samples": 0,
        "correct": 0,
        "accuracy_pct": 0.0,
        "avg_ticks": 0,
        "avg_latency_ms_est": 0.0,
        "min_ticks": 0,
        "max_ticks": 0,
    }

    if not bench_lines:
        return results

    ticks = []
    samples_total = 0
    correct_total = 0

    for line in bench_lines:
        parts = line.split()
        fields = {}
        for p in parts[1:]:
            if "=" not in p:
                continue
            key, value = p.split("=", 1)
            fields[key] = value

        try:
            samples = int(fields.get("samples", "0"))
            correct = int(fields.get("correct", "0"))
            avg_ticks = int(fields.get("avg_ticks", "0"))
            samples_total += samples
            correct_total += correct
            ticks.append(avg_ticks)
        except ValueError:
            continue

    if ticks:
        results["avg_ticks"] = sum(ticks) / len(ticks)
        results["min_ticks"] = min(ticks)
        results["max_ticks"] = max(ticks)

    results["samples"] = samples_total
    results["correct"] = correct_total
    if samples_total > 0:
        results["accuracy_pct"] = (correct_total / samples_total) * 100.0
    if results["avg_ticks"] > 0:
        results["avg_latency_ms_est"] = (results["avg_ticks"] / CPU_HZ_ESTIMATE) * 1000.0

    return results

def run_qmp_tests(sock):
    results = {}

    # Step 1: Receive greeting banner
    greeting = qmp_recv(sock)
    try:
        g = json.loads(greeting)
        results["qmp_connected"] = "QMP" in str(g)
        qemu_ver = g.get("QMP", {}).get("version", {}).get("qemu", {})
        results["qemu_version"] = f"{qemu_ver.get('major','?')}.{qemu_ver.get('minor','?')}.{qemu_ver.get('micro','?')}"
    except:
        results["qmp_connected"] = False
        results["qemu_version"] = "unknown"

    # Step 2: Enter capabilities negotiation mode
    resp = qmp_send(sock, {"execute": "qmp_capabilities"})
    try:
        results["qmp_capabilities"] = json.loads(resp) == {"return": {}}
    except:
        results["qmp_capabilities"] = False

    # Step 3: Query machine status
    resp = qmp_send(sock, {"execute": "query-status"})
    try:
        status = json.loads(resp)
        vm_status = status.get("return", {}).get("status", "unknown")
        results["vm_status"] = vm_status
        results["vm_running"] = (vm_status == "running")
    except:
        results["vm_status"] = "error"
        results["vm_running"] = False

    # Step 4: Query CPU architecture info
    resp = qmp_send(sock, {"execute": "query-target"})
    try:
        target = json.loads(resp)
        arch = target.get("return", {}).get("arch", "unknown")
        results["cpu_arch"] = arch
        results["is_arm"] = (arch == "arm")
    except:
        results["cpu_arch"] = "unknown"
        results["is_arm"] = False

    # Step 5: Query memory info
    resp = qmp_send(sock, {"execute": "query-memory-size-summary"})
    try:
        mem = json.loads(resp)
        base_mem = mem.get("return", {}).get("base-memory", 0)
        results["memory_bytes"] = base_mem
        results["memory_kb"] = base_mem // 1024
    except:
        results["memory_bytes"] = 0
        results["memory_kb"] = 0

    return results

def print_report(qmp_results, fw_results, ml_results):
    print("=" * 55)
    print("  ARM Cortex-M3 Emulation QMP Test Report")
    print("  James Schiavo | lm3s6965evb | QEMU")
    print("=" * 55)

    print("\n[QMP HOST-GUEST COMMUNICATION]")
    print(f"  QMP socket connected   : {'PASS' if qmp_results.get('qmp_connected') else 'FAIL'}")
    print(f"  QEMU version           : {qmp_results.get('qemu_version', 'N/A')}")
    print(f"  Capabilities exchange  : {'PASS' if qmp_results.get('qmp_capabilities') else 'FAIL'}")

    print("\n[EMULATED MACHINE STATE]")
    print(f"  VM status              : {qmp_results.get('vm_status', 'N/A').upper()}")
    print(f"  VM running             : {'PASS' if qmp_results.get('vm_running') else 'FAIL'}")
    print(f"  CPU architecture       : {qmp_results.get('cpu_arch', 'N/A').upper()}")
    print(f"  ARM target confirmed   : {'PASS' if qmp_results.get('is_arm') else 'FAIL'}")
    print(f"  RAM allocated          : {qmp_results.get('memory_kb', 0)} KB")

    print("\n[FIRMWARE VALIDATION]")
    print(f"  Boot banner received   : {'PASS' if fw_results.get('boot_ok') else 'FAIL'}")
    print(f"  Identity string found  : {'PASS' if fw_results.get('identity') else 'FAIL'}")
    print(f"  Version string found   : {'PASS' if fw_results.get('version') else 'FAIL'}")
    print(f"  Firmware executing     : {'PASS' if fw_results.get('firmware_running') else 'FAIL'}")
    print(f"  Heartbeat count        : {fw_results.get('heartbeat_count', 0)}")
    print(f"  Sequential heartbeats  : {'PASS' if fw_results.get('heartbeat_sequential') else 'FAIL'}")

    print("\n[EDGE ML INFERENCE TELEMETRY]")
    print(f"  Benchmark lines parsed : {ml_results.get('bench_count', 0)}")
    print(f"  Samples validated      : {ml_results.get('samples', 0)}")
    print(f"  Correct predictions    : {ml_results.get('correct', 0)}")
    print(f"  Accuracy               : {ml_results.get('accuracy_pct', 0.0):.2f}%")
    print(f"  Avg inference ticks    : {ml_results.get('avg_ticks', 0):.2f}")
    print(f"  Avg latency (est)      : {ml_results.get('avg_latency_ms_est', 0.0):.2f} ms")
    print(f"  Min/Max ticks          : {ml_results.get('min_ticks', 0)}/{ml_results.get('max_ticks', 0)}")

    # Overall result
    all_tests = [
        qmp_results.get("qmp_connected"),
        qmp_results.get("qmp_capabilities"),
        qmp_results.get("vm_running"),
        qmp_results.get("is_arm"),
        fw_results.get("boot_ok"),
        fw_results.get("version"),
        fw_results.get("firmware_running"),
        fw_results.get("heartbeat_sequential"),
        ml_results.get("bench_count", 0) > 0,
        ml_results.get("samples", 0) >= 100,
        ml_results.get("accuracy_pct", 0.0) >= 95.0,
    ]
    passed = sum(1 for t in all_tests if t)
    total = len(all_tests)
    print(f"\n  RESULT: {passed}/{total} tests passed", end=" ")
    print("✓ ALL PASS" if passed == total else "✗ SOME FAILED")
    print("=" * 55)

if __name__ == "__main__":
    print(f"\nConnecting to QMP socket: {QMP_SOCK}")
    try:
        sock = qmp_connect(QMP_SOCK)
    except Exception as e:
        print(f"ERROR: Could not connect to QMP socket: {e}")
        sys.exit(1)

    print("Reading serial log...")
    serial_log = read_serial_log(SERIAL_LOG)

    print("Running QMP queries...")
    qmp_results = run_qmp_tests(sock)
    sock.close()

    print("Validating firmware output...")
    fw_results = check_firmware_health(serial_log)
    ml_results = check_ml_telemetry(serial_log)

    print_report(qmp_results, fw_results, ml_results)

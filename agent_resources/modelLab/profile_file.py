# https://github.com/microsoft/onnxruntime/blob/main/onnxruntime/python/tools/onnxruntime_test.py

from __future__ import annotations

import os

import sys
from timeit import default_timer as timer
import json

import numpy as np
import time

from modelLab import ExitErrorCodes, logger


# Temp result files
# session_options.profile_file_prefix
ONNX_PROFILE_RESULT_PREFIX = "onnxruntime_profile_"
QNN_OP_RESULT = "onnxruntime_qnn_profile.csv"
# Our result files
PROFILING_RESULT = "profiling_result.json"
PROFILING_OP_RESULT_CSV = "profiling_result_op.csv"
PROFILING_OP_RESULT_JSON = "profiling_result_op.json"
# Special op types
EP_ADDED_OP_TYPE = "EP_ADDED_OP"
NOT_IN_MODEL_OP_TYPE = "NOT_IN_MODEL"
GROUP_OP_TYPE = "GROUP_OP"
# EPs
CPUEP = "CPUExecutionProvider"
QNNEP = "QNNExecutionProvider"
POLICY_EP = "POLICY_SET_EP"

# Run

float_dict = {
    "tensor(float16)": "float16",
    "tensor(float)": "float32",
    "tensor(double)": "float64",
}

integer_dict = {
    "tensor(int32)": "int32",
    "tensor(int8)": "int8",
    "tensor(uint8)": "uint8",
    "tensor(int16)": "int16",
    "tensor(uint16)": "uint16",
    "tensor(int64)": "int64",
    "tensor(uint64)": "uint64",
}


def generate_feeds(sess, symbolic_dims: dict | None = None) -> dict:
    feeds = {}
    symbolic_dims = symbolic_dims or {}
    for input_meta in sess.get_inputs():
        # replace any symbolic dimensions
        shape = []
        for dim in input_meta.shape:
            if not dim:
                # unknown dim
                shape.append(1)
            elif isinstance(dim, str):
                # symbolic dim. see if we have a value otherwise use 1
                if dim in symbolic_dims:
                    shape.append(int(symbolic_dims[dim]))
                else:
                    shape.append(1)
            else:
                shape.append(dim)

        if input_meta.type in float_dict:
            feeds[input_meta.name] = np.random.rand(*shape).astype(
                float_dict[input_meta.type]
            )
        elif input_meta.type in integer_dict:
            feeds[input_meta.name] = np.random.uniform(
                high=1000, size=tuple(shape)
            ).astype(integer_dict[input_meta.type])
        elif input_meta.type == "tensor(bool)":
            feeds[input_meta.name] = np.random.randint(2, size=tuple(shape)).astype(
                "bool"
            )
        else:
            logger.error(
                f"unsupported input type {input_meta.type} for input {input_meta.name}"
            )
            sys.exit(ExitErrorCodes.UNSUPPORTED_INPUT_TYPE)
    return feeds


def add_ep_for_device(session_options, ep_name: str, device_type: str, ep_options: dict | None = None):
    import onnxruntime as onnxrt
    ep_devices = onnxrt.get_ep_devices()
    for ep_device in ep_devices:
        if ep_device.ep_name == ep_name and ep_device.device.type == device_type:
            logger.info(f"Adding {ep_name} for {device_type}")
            session_options.add_provider_for_devices(
                [ep_device], {} if ep_options is None else ep_options
            )
            break


def run_one(sess, symbolic_dims: dict | None, override_initializers: bool) -> tuple[int, float]:
    """Run a single inference and return timing information.

    Args:
        sess: ONNX Runtime inference session.
        symbolic_dims: Dictionary mapping symbolic dimension names to values.
        override_initializers: Whether to override model initializers with random values.

    Returns:
        A tuple of (start_time_us, duration_us) where start_time_us is the UTC
        timestamp in microseconds when the inference started and duration_us is
        the inference duration in microseconds.
    """
    feeds = generate_feeds(sess, symbolic_dims)

    if override_initializers:
        # Starting with IR4 some initializers provide default values
        # and can be overridden (available in IR4). For IR < 4 models
        # the list would be empty
        for initializer in sess.get_overridable_initializers():
            shape = [dim if dim else 1 for dim in initializer.shape]
            if initializer.type in float_dict:
                feeds[initializer.name] = np.random.rand(*shape).astype(
                    float_dict[initializer.type]
                )
            elif initializer.type in integer_dict:
                feeds[initializer.name] = np.random.uniform(
                    high=1000, size=tuple(shape)
                ).astype(integer_dict[initializer.type])
            elif initializer.type == "tensor(bool)":
                feeds[initializer.name] = np.random.randint(
                    2, size=tuple(shape)
                ).astype("bool")
            else:
                logger.error(
                    f"unsupported initializer type {initializer.type} for initializer {initializer.name}"
                )
                sys.exit(ExitErrorCodes.UNSUPPORTED_INITIALIZER_TYPE)

    start_time = int(time.time() * 1000 * 1000)  # Convert to microseconds
    start = timer()
    sess.run([], feeds)
    end = timer()
    return (start_time, (end - start) * 1000 * 1000)  # Convert to microseconds


def run_duration(duration: int, sess, symbolic_dims: dict | None, override_initializers: bool) -> list[tuple[int, float]]:
    results: list[tuple[int, float]] = []
    start = timer()
    while True:
        results.append(run_one(sess, symbolic_dims, override_initializers))
        end = timer()
        if end - start >= duration:
            break
    return results


def calculate_percentiles(latencies: list[float]) -> dict:
    return {
        "p50": np.percentile(latencies, 50),
        "p90": np.percentile(latencies, 90),
        "p95": np.percentile(latencies, 95),
        "p99": np.percentile(latencies, 99),
        "min": np.min(latencies),
        "max": np.max(latencies),
        "avg": np.mean(latencies),
    }


def create_session_options(ep: str | None, device: str | None, policy: str | None, ep_options: dict | None = None):
    import onnxruntime as onnxrt
    sess_options = onnxrt.SessionOptions()
    if ep is not None and device is not None:
        device_type = None
        if device.lower() == "npu":
            device_type = onnxrt.OrtHardwareDeviceType.NPU
        elif device.lower() == "cpu":
            device_type = onnxrt.OrtHardwareDeviceType.CPU
        elif device.lower() == "gpu":
            device_type = onnxrt.OrtHardwareDeviceType.GPU
        if device_type is not None:
            add_ep_for_device(sess_options, ep, device_type, ep_options)
    elif policy is not None:
        ort_policy = None
        if policy == "OrtExecutionProviderDevicePolicy.MAX_EFFICIENCY":
            ort_policy = onnxrt.OrtExecutionProviderDevicePolicy.MAX_EFFICIENCY
        elif policy == "OrtExecutionProviderDevicePolicy.MAX_PERFORMANCE":
            ort_policy = onnxrt.OrtExecutionProviderDevicePolicy.MAX_PERFORMANCE
        elif policy == "OrtExecutionProviderDevicePolicy.MIN_OVERALL_POWER":
            ort_policy = onnxrt.OrtExecutionProviderDevicePolicy.MIN_OVERALL_POWER
        if ort_policy is not None:
            logger.info(f"Set policy {ort_policy}")
            sess_options.set_provider_selection_policy(ort_policy)
    assert sess_options.has_providers(), (
        f"Could not find provider for EP {ep}, device {device}, policy {policy}"
    )
    return sess_options


# OP

def load_model_op(model_path: str, ep: str | None, device: str | None, policy: str | None):
    import onnxruntime as onnxrt
    
    ep_options = None
    if ep == QNNEP and device == "npu":
        ep_options = {
            "profiling_level": "detailed",
            "profiling_file_path": QNN_OP_RESULT
        }
    elif ep == CPUEP and device == "cpu":
        ep_options = {
        }
    assert ep_options is not None, f"{ep} on {device} does not support op profiling now."
    ep_options.update(get_ep_options(ep, device) if ep and device else {})
    sess_options = create_session_options(ep, device, policy, ep_options)
    sess_options.enable_profiling = True
    logger.info(f"Start to load model {model_path} for op profiling with {ep_options}...")
    sess = onnxrt.InferenceSession(
        model_path,
        sess_options=sess_options,
    )
    return sess


def run_model_op(
        sess,
        op_times,
        symbolic_dims=None,
        override_initializers=False,
):
    logger.info(f"Start running op profiling for {op_times} times...")
    for i in range(op_times):
        run_one(sess, symbolic_dims, override_initializers)


class OpProfileRecord:
    def __init__(self, op_name: str, op_type: str, ep: str):
        self.op_name = op_name
        self.op_type = op_type
        self.ep = ep
        # microseconds
        self.results = []


class QnnProfileRecord:
    def __init__(self, op_name: str, time: float, ep_added: bool):
        self.op_name = op_name
        self.time = time
        self.ep_added = ep_added


def summarize_qnn_optrace(optrace_path: str, name_to_type: dict[str, str]) -> list[list[QnnProfileRecord]]:
    import csv
    import re

    ROW_FIELD_EVENT_LEVEL = "Event Level"
    ROW_FIELD_EVENT_IDENTIFIER = "Event Identifier"
    ROW_FIELD_TIME = "Time"
    ROW_FIELD_UNIT = "Unit of Measurement"
    HVX_THREADS = "Number of HVX threads used"
    TIME_CYCLES = "Accelerator (execute) time (cycles)"
    TIME_US = "Accelerator (execute) time"

    results: list[list[QnnProfileRecord]] = []
    if not os.path.exists(optrace_path):
        return results
    with open(optrace_path, "r") as f:
        reader = csv.DictReader(f)
        ep_begin = False
        result: list[QnnProfileRecord] = []
        # Track op_name to index mapping to preserve order
        name_to_index: dict[str, int] = {}
        acc_time: float | None = None
        acc_cycles: float | None = None
        for row in reader:
            if row[ROW_FIELD_EVENT_LEVEL] == "ROOT":
                if row[ROW_FIELD_EVENT_IDENTIFIER] == HVX_THREADS:
                    ep_begin = True
                    result = []
                    name_to_index = {}
                    acc_time = None
                    acc_cycles = None
                elif row[ROW_FIELD_EVENT_IDENTIFIER] == TIME_CYCLES:
                    if not ep_begin:
                        raise ValueError(f"{TIME_CYCLES} must appear after {HVX_THREADS}")
                    #if row[ROW_FIELD_UNIT] != "CYCLES":
                    #    raise ValueError("Accelerator (execute) time (cycles) must be in CYCLES")
                    acc_cycles = float(row[ROW_FIELD_TIME])
                elif row[ROW_FIELD_EVENT_IDENTIFIER] == TIME_US:
                    if not ep_begin:
                        raise ValueError(f"{TIME_US} must appear after {HVX_THREADS}")
                    if row[ROW_FIELD_UNIT] != "US":
                        raise ValueError(f"{TIME_US} must be in US")
                    if acc_cycles is None:
                        raise ValueError(f"{TIME_CYCLES} must appear before {TIME_US}")
                    ep_begin = False
                    acc_time = float(row[ROW_FIELD_TIME]) / acc_cycles
                    for r in result:
                        r.time = r.time * acc_time
                    results.append(result)
            elif row[ROW_FIELD_EVENT_LEVEL] == "SUB-EVENT":
                id = row[ROW_FIELD_EVENT_IDENTIFIER]
                if id.endswith(" (cycles)") and "OpId_" in id:
                    if not ep_begin:
                        raise ValueError(f"OpId_xxx (cycles) must appear after {HVX_THREADS}")
                    ep_added = True
                    if ":" in id:
                        op_name = id.rsplit(":", 1)[0]
                        if op_name in name_to_type:
                            ep_added = False
                        else:
                            # TODO it appends this sometimes
                            # if updated one not exist in model, keep as it is
                            new_op_name = re.sub(r'_token_\d+$', '', op_name)
                            if new_op_name in name_to_type:
                                op_name = new_op_name
                                ep_added = False
                    else:
                        # Input, Output
                        op_name = id.split(" ")[0]
                    cycles = float(row[ROW_FIELD_TIME])
                    
                    # Aggregate by op_name while preserving order because sometimes it adds both one and one with _token_xxx
                    if op_name in name_to_index:
                        # Add to existing record
                        result[name_to_index[op_name]].time += cycles
                    else:
                        # Create new record
                        record = QnnProfileRecord(op_name, cycles, ep_added)
                        name_to_index[op_name] = len(result)
                        result.append(record)
    return results


# TODO observed name cases
# - the op is QDQ, use node name and it could be either
#     - pixel_values_QuantizeLinear_kernel_time
#     - /resnet/embedder/embedder/convolution/Conv_token_1_kernel_time: _token_xxx is added
# - the op is optimized (?), use output name like below. Also nodes could be fused like Conv+Relu, so op_name should be used
#     - fire2/squeeze1x1_2_nchwc_kernel_time: _nchwc is added
def resolve_node_name(name_to_type: dict[str, str], output_to_name: dict[str, str], name: str) -> str:
    import re

    if name in name_to_type:
        return name
    # TODO some output names are like op_output_0_nchwc
    if name.endswith("_nchwc"):
        new_name = name[: -len("_nchwc")]
        if new_name in output_to_name:
            return output_to_name[new_name]
    new_name = re.sub(r'_token_\d+$', '', name)
    if new_name in name_to_type:
        return new_name
    # if updated one not exist in model, keep as it is
    return name


def resolve_node_type(name_to_type: dict[str, str], name: str, onnx_line: dict) -> str:
    if "args" in onnx_line and "op_name" in onnx_line["args"]:
        return onnx_line["args"]["op_name"]
    return name_to_type.get(name, NOT_IN_MODEL_OP_TYPE)


def summarize_op_profiling(model_path: str, onnx_profile_path: str, ep: str, op_warmup: int, op_times: int, output_folder: str) -> list[OpProfileRecord]:
    import onnx

    # load onnx model
    name_to_type: dict[str, str] = {}
    output_to_name: dict[str, str] = {}
    model = onnx.load(model_path, load_external_data=False)
    for node in model.graph.node:
        name_to_type[node.name] = node.op_type
        for output in node.output:
            output_to_name[output] = node.name
    del model
    # prepare
    with open(onnx_profile_path, "r") as json_file:
        onnx_profile = json.load(json_file)
    optrace_id = 0
    optraces = {}
    if ep == QNNEP:
        optraces = summarize_qnn_optrace(os.path.join(output_folder, QNN_OP_RESULT), name_to_type)
    name_to_record: dict[str, OpProfileRecord] = {}
    result: list[OpProfileRecord] = []
    # process
    for onnx_line in onnx_profile:
        if not onnx_line["name"].endswith("_kernel_time"):
            continue
        op_name: str = onnx_line["name"][: -len("_kernel_time")]
        if op_name.startswith("QNNExecutionProvider_QNN_"):
            # To get 112_50 from QNNExecutionProvider_QNN_7471962374096941510_112_50_kernel_time
            # Add suffix to distinguish Input, Output from multiple QNN EP nodes
            name_suffix = "_" + op_name.split("_", 3)[-1]
            for qnn_record in optraces[optrace_id]:
                qnn_record_op_name = qnn_record.op_name
                if qnn_record.ep_added:
                    qnn_record_op_name += name_suffix
                if qnn_record_op_name in name_to_record:
                    record = name_to_record[qnn_record_op_name]
                    record.results.append(qnn_record.time)
                elif qnn_record_op_name in name_to_type:
                    op_type = name_to_type[qnn_record_op_name]
                    record = OpProfileRecord(qnn_record_op_name, op_type, ep)
                    record.results.append(qnn_record.time)
                    name_to_record[qnn_record_op_name] = record
                    result.append(record)
                else:
                    record = OpProfileRecord(qnn_record_op_name, EP_ADDED_OP_TYPE, ep)
                    record.results.append(qnn_record.time)
                    name_to_record[qnn_record_op_name] = record
                    result.append(record)
            optrace_id += 1
            continue
        op_name = resolve_node_name(name_to_type, output_to_name, op_name)
        if op_name in name_to_record:
            name_to_record[op_name].results.append(onnx_line["dur"])
        else:
            op_type = resolve_node_type(name_to_type, op_name, onnx_line)
            record = OpProfileRecord(op_name, op_type, CPUEP)
            record.results.append(onnx_line["dur"])
            name_to_record[op_name] = record
            result.append(record)
    for record in result:
        assert len(record.results) == op_warmup + op_times, f"op {record.op_name} has {len(record.results)} results, expected {op_warmup + op_times}"
        record.results = record.results[op_warmup:]  # remove warmup
    return result


def output_op_csv(file: str, records: list[OpProfileRecord]):
    import csv

    with open(file, "w", newline='', encoding="utf-8") as csvfile:
        fieldnames = ["id", "op_name", "op_type", "ep", "avg_us", "avg_percent", "p90_us", "results_us"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        id = 0
        avgs = []
        for record in records:
            avg =  np.mean(record.results)
            avgs.append(avg)
        avg_sum = np.sum(avgs)
        for i, record in enumerate(records):
            p90 = np.percentile(record.results, 90)
            writer.writerow({
                "id": id,
                "op_name": record.op_name,
                "op_type": record.op_type,
                "ep": record.ep,
                "avg_us": avgs[i],
                "avg_percent": avgs[i] / avg_sum * 100 if avg_sum > 0 else 0,
                "p90_us": p90,
                "results_us": ";".join(str(x) for x in record.results),
            })
            id += 1


def create_op_in_json(op_name: str, op_type: str, ts_ns: int, pid: int, dur_ns: int = 0, ep: str = CPUEP) -> dict:
    base = {
        "name": op_name,
        "ph": "X",
        "ts": ts_ns / 1000.0,
        "dur": dur_ns / 1000.0,
        "pid": pid,
    }
    if op_type == GROUP_OP_TYPE:
        base["cat"] = "Group"
    else:
        base["cat"] = "Node"
        base["args"] = {"op_name": op_type, "ep": ep}
    return base


def get_current_groups(name: str) -> set[str]:
    current_names: set[str] = set()
    if name.startswith("/") and not name.endswith("/"):
        all_parts = name.split("/")[1:]  # first is empty
        current_name = ""
        for part in all_parts[:-1]: # Exclude last part (leaf node)
            current_name += "/" + part
            current_names.add(current_name)
    return current_names


def add_update_groups(all_ops: list[dict], group_stack: list[OpProfileRecord], current_names: set[str], ts: int, avg: int, pid: int):
    for name in sorted(current_names):
        group = next((g for g in group_stack if g.op_name == name), None)
        if group:
            group.results.append(avg)
        else:
            new_record = OpProfileRecord(name, GROUP_OP_TYPE, CPUEP)
            new_record.results.append(avg)
            group_stack.append(new_record)
            all_ops.append(create_op_in_json(new_record.op_name, new_record.op_type, ts, pid))


def pop_ended_groups(all_ops: list[dict], group_stack: list[OpProfileRecord], current_names: set[str] = set()):
    while group_stack and group_stack[-1].op_name not in current_names:
        ended_record = group_stack.pop()
        # Remove the event that was added without children
        for i in range(len(all_ops) - 1, -1, -1):
            if all_ops[i].get("name") == ended_record.op_name and all_ops[i].get("cat") == "Group":
                if len(ended_record.results) > 1:
                    all_ops[i]["dur"] = np.sum(ended_record.results) / 1000.0
                else:
                    all_ops.pop(i)
                break
            
                
# Could not use B + E because perfetto doesn't support format like this
# [
#{"name": "A", "cat": "Group", "ts": 1, "ph": "B", "tid": 1},
#{"name": "B", "cat": "Group", "ts": 1, "ph": "B", "tid": 1},
#{"name": "C1", "tid": 1, "cat": "Node", "ts": 1, "dur": 1, "ph": "X"},
#{"name": "B", "tid": 1, "cat": "Group", "ts": 2, "ph": "E"},
#{"name": "C2", "tid": 1, "cat": "Node", "ts": 2, "dur": 1, "ph": "X"},
#{"name": "A", "tid": 1, "cat": "Group", "ts": 3, "ph": "E"}
#]
def generate_op_json(records: list[OpProfileRecord], pid: int | None = None) -> list[dict]:
    # Add pid so different results could be simply merged into one file
    pid = pid or os.getpid()
    group_stack: list[OpProfileRecord] = []  # Track open groups
    all_ops: list[dict] = []
    # ns
    ts = 0
    for record in records:
        avg =  int(np.mean(record.results) * 1000)  # convert to ns
        # TODO group for special name format
        current_names = get_current_groups(record.op_name)
        pop_ended_groups(all_ops, group_stack, current_names)
        add_update_groups(all_ops, group_stack, current_names, ts, avg, pid)
        # Add the actual node
        all_ops.append(create_op_in_json(record.op_name, record.op_type, ts, pid, avg, record.ep))
        ts += avg
    pop_ended_groups(all_ops, group_stack)
    has_group = any(op.get("cat") == "Group" for op in all_ops)
    if not has_group:
        logger.info(f"Could not find hierarchy information, skip generating {PROFILING_OP_RESULT_JSON}.")
        return []
    return all_ops


def write_op_json(file: str, all_ops: list[dict]):
    with open(file, "w", encoding="utf-8") as f:
        f.write("[\n")
        n = len(all_ops)
        for i, obj in enumerate(all_ops):
            s = json.dumps(obj, ensure_ascii=False)
            # add comma for all but last element
            if i < n - 1:
                f.write(s + ",\n")
            else:
                f.write(s + "\n")
        f.write("]\n")


def finish_op(model_path: str, ep: str, op_warmup: int, op_times: int, output: str):
    import glob

    files = glob.glob(os.path.join(output, f"{ONNX_PROFILE_RESULT_PREFIX}*"))
    if len(files) == 0:
        logger.warning("No onnxruntime profile file found!")
        return
    merged_result = summarize_op_profiling(model_path, files[0], ep, op_warmup, op_times, output)
    output_op_csv(os.path.join(output, PROFILING_OP_RESULT_CSV), merged_result)
    op_json = generate_op_json(merged_result)
    if op_json:
        write_op_json(os.path.join(output, PROFILING_OP_RESULT_JSON), op_json)
    logger.info("Finished generating op profiling results.")


def get_ep_options(ep: str, device: str) -> dict:
    ep_options = {}
    if ep == QNNEP and device == "npu":
        ep_options["htp_performance_mode"] = "high_performance"
    return ep_options


def run_model(
    args,
):
    logger.info(f"PID: {os.getpid()} Registering execution providers...")
    
    from modelLab import register_execution_providers_to_onnxruntime
    import onnxruntime as onnxrt

    model_path: str = args.model_path
    warmup_seconds = args.warmup
    duration: int = args.duration
    ep: str | None = args.ep
    device: str | None = args.device
    policy: str | None = args.policy
    op_warmup: int = args.op_warmup
    op_times: int = args.op_times
    symbolic_dims: dict | None = args.symbolic_dims
    override_initializers=False

    start = timer()
    register_execution_providers_to_onnxruntime()
    time.sleep(
        max(0, 5 - (timer() - start))
    )  # Ensure at least 5 seconds before running to wait for profiling agent

    symbolic_dims = symbolic_dims or {}
    ep_options = get_ep_options(ep, device) if ep and device else None
    sess_options = create_session_options(ep, device, policy, ep_options)

    logger.info(f"Start to load model {model_path}...")
    sess = onnxrt.InferenceSession(
        model_path,
        sess_options=sess_options,
    )
    op_sess = load_model_op(model_path, ep, device, policy) if op_times > 0 else None
    
    logger.info(f"Start warming up for {warmup_seconds} seconds...")
    run_duration(warmup_seconds, sess, symbolic_dims, override_initializers)  # warm up
    logger.info(f"Start running for {duration} seconds...")
    results = run_duration(duration, sess, symbolic_dims, override_initializers)
    if op_sess:
        run_model_op(
            op_sess,
            op_times + op_warmup,
            symbolic_dims,
            override_initializers,
        )
        del op_sess
    results_duration = [r[1] for r in results]
    stats = calculate_percentiles(results_duration)

    logger.info(f"Run {len(results)} times during duration {duration} seconds")
    logger.info(f"Avg latency: {stats['avg'] / 1000} ms")

    with open(os.path.join(args.output, PROFILING_RESULT), "w") as f:
        output = {
            "model_path": model_path,
            "duration": duration,
            "ep": ep,
            "device": device,
            "policy": policy,
            "symbolic_dims": symbolic_dims,
            "stats_us": stats,
            "results": [ { "ts": r[0], "duration_us": r[1] } for r in results],
        }
        json.dump(output, f, indent=4)
    
    if op_times > 0:
        # TODO currently we will not use policy and also no way to get ep from policy now
        finish_op(model_path, ep if ep else POLICY_EP, op_warmup, op_times, args.output)

    time.sleep(2)  # Ensure profiling agent can receive the events 


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Simple ONNX Runtime Test Tool.")
    parser.add_argument("--model_path", help="model path")
    parser.add_argument("--warmup", type=int, default=5, help="warmup duration in seconds. default=5")
    parser.add_argument(
        "--duration",
        nargs="?",
        type=int,
        default=10,
        help="model run duration in seconds. default=10",
    )
    parser.add_argument("--ep", type=str, help="execution provider.")
    parser.add_argument("--device", type=str, help="device of execution provider.")
    parser.add_argument("--policy", type=str, help="device policy.")
    parser.add_argument(
        "--symbolic_dims",
        default={},
        type=lambda s: dict(x.split("=") for x in s.split(",")),
        help="Comma separated name=value pairs for any symbolic dimensions in the model input. "
        "e.g. --symbolic_dims batch=1,seqlen=5. "
        "If not provided, the value of 1 will be used for all symbolic dimensions.",
    )
    parser.add_argument("--op_warmup", default=5, type=int, help="run x times to profile op warmup")
    parser.add_argument("--op_times", default=0, type=int, help="run x times to profile op")
    parser.add_argument("--output", type=str, help="output folder")
    parser.add_argument("--runtime", help="runtime arg placeholder")

    args = parser.parse_args()
    if not args.output:
        args.output = os.getcwd()

    # TODO temp solution to notify profiling agent of current pid
    with open(os.path.join(args.output, PROFILING_RESULT), "w") as f:
        f.write(str(os.getpid()))

    run_model(args)


if __name__ == "__main__":
    main()

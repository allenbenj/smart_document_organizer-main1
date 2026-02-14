import argparse
import os
from pathlib import Path
from typing import cast
from modelLab import logger


def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="path to input config file")
    parser.add_argument("--model_config", required=True, help="path to input model config file")
    parser.add_argument("--built-in", action="store_true", help="use built-in evaluator")
    parser.add_argument("--runtime", required=True, help="runtime")
    return parser.parse_args()


def main():
    args = parse_arguments()

    p = Path(args.model_config)
    if not p.exists():
        raise FileNotFoundError(f"Model config file {p} does not exist.")
    
    logger.info(f"Process ({os.getpid()}): loading model and configuration ...")

    if args.built_in:
        from modelLab import register_execution_providers_to_onnxruntime_genai
        register_execution_providers_to_onnxruntime_genai()
        built_in_evaluator(args)
        return

    from modelLab import register_execution_providers_to_onnxruntime
    register_execution_providers_to_onnxruntime()

    from olive.evaluator.metric_result import MetricResult
    from olive.model.config import ModelConfig
    from olive.resource_path import create_resource_path, LocalFile
    from olive.systems.accelerator_creator import create_accelerator
    from olive.systems.olive_system import OliveSystem
    from olive.workflows.run.config import RunConfig

    run_config = cast(RunConfig, RunConfig.parse_file_or_obj(args.config))

    engine = run_config.engine.create_engine(
        olive_config=run_config,
        workflow_id=run_config.workflow_id,
    )
    engine.initialize()

    accelerator_spec = create_accelerator(
        engine.target_config,
        skip_supported_eps_check=True,
        is_ep_required=True,
    )

    target: OliveSystem = engine.target_config.create_system()

    model_config_file: LocalFile = cast(LocalFile, create_resource_path(p))
    model_config = cast(
        ModelConfig,
        ModelConfig.parse_file_or_obj(model_config_file.get_path()),
    )
    # Workaround https://github.com/microsoft/Olive/blob/0497aa6a7ed24b60503ed8693ffd69e713fde8ae/olive/model/handler/onnx.py#L152C9-L152C95
    inference_settings = model_config.config.get("inference_settings")
    if inference_settings:
        inference_settings.pop("execution_provider", None)

    logger.info("Evaluating model ...")
    result: MetricResult = target.evaluate_model(
        model_config=model_config,
        evaluator_config=engine.evaluator_config,
        accelerator=accelerator_spec,
    )

    output_file = Path(args.config).parent / "metrics.json"
    resultStr = str(result)
    with open(output_file, 'w') as file:
        file.write(resultStr)
    logger.info("Model lab succeeded for evaluation.\n%s", resultStr)


# https://github.com/microsoft/onnxruntime-genai/blob/main/benchmark/python/benchmark_e2e.py

def built_in_get_input_tokens(prompts, tokenizer, prompt_length: int, prompt_index: int, text_template: str):
    prompt = prompts[str(prompt_length)][prompt_index % len(prompts[str(prompt_length)])]
    prompt = text_template.replace("{Content}", prompt)
    return tokenizer.encode(prompt)


def built_in_run_one(model, params, input_tokens, generation_length, tokenizer = None):
    import onnxruntime_genai as og
    import time

    search_options = {}
    search_options["max_length"] = len(input_tokens) + generation_length
    params.set_search_options(**search_options)

    latencies = []    
    generator = og.Generator(model, params)

    prompt_start_time = time.perf_counter()
    generator.append_tokens(input_tokens)
    prompt_time = time.perf_counter() - prompt_start_time

    ftlTime = time.perf_counter()
    generator.generate_next_token()
    generator_done = generator.is_done()
    ftl = time.perf_counter() - ftlTime

    # AMD NPU del generator will crash when generator not done 
    while not generator_done:
        geneStart = time.perf_counter()
        generator.generate_next_token()
        generator_done = generator.is_done()
        latencies.append(time.perf_counter() - geneStart)

    if tokenizer:
        logger.info(tokenizer.decode(generator.get_sequence(0)))
    del generator
    return latencies, ftl, prompt_time


def latency_avg(latencies: list[float]) -> float:
    return round(sum(latencies) / len(latencies) * 1000, 5)


def get_results(latencies: list[list[float]], ftls: list[float], prompt_times: list[float]) -> dict:
    import json
    logger.info("First token (sampling) latencies (ms): %s", json.dumps([round(float(x) * 1000, 1) for x in ftls]))
    logger.info("Prompt processing latencies (ms): %s", json.dumps([round(float(x) * 1000, 1) for x in prompt_times]))

    metrics_res = {}
    flatten_latencies = [item for sublist in latencies for item in sublist]
    metrics_res["latency-avg"] = latency_avg(flatten_latencies)
    metrics_res["throughput-avg"] = round(1 / metrics_res["latency-avg"] * 1000, 5)
    metrics_res["FTL-avg"] = latency_avg(ftls)
    metrics_res["prompt-processing-avg"] = latency_avg(prompt_times)
    return metrics_res


def get_device_from_olive_config(olive_config):
    # Get the target system key from olive_config
    target_key = olive_config.get("target")
    if not target_key:
        return None
    
    # Get the specific system using the target key
    systems = olive_config.get("systems", {})
    target_system = systems.get(target_key)
    if not target_system:
        return None
    
    # Get accelerators and return the device from the first one
    accelerators = target_system.get("accelerators", [])
    if accelerators and "device" in accelerators[0]:
        return accelerators[0]["device"].upper()
    return None


def update_device_type_in_json(data, device_type) -> bool:
    """
    Update the device_type in any provider_options item that contains a device_type field.

    This function mutates the provided data dictionary in-place and returns True if any
    device_type value was changed, or False otherwise. It does not perform any file I/O;
    callers are responsible for persisting the updated data structure if needed.
    """
    # Navigate to provider_options array
    provider_options = (
        data.get("model", {})
            .get("decoder", {})
            .get("session_options", {})
            .get("provider_options", [])
    )

    updated = False
    for item in provider_options:
        # Each item is a dict, e.g. {"OpenVINO": {...}}
        for provider, opts in item.items():
            if "device_type" in opts:
                if opts["device_type"] != device_type:
                    opts["device_type"] = device_type
                    updated = True

    return updated


def syncDeviceTypeToGenaiConfig(olive_config, model_folder):
    """
    Usually for Intel OpenVINO EP, we need to update device_type in genai_config.json because it could support multiple devices.
    """
    genai_config_path = model_folder / "genai_config.json"
    if not genai_config_path.exists():
        return
    device_type = get_device_from_olive_config(olive_config)
    if not device_type:
        return
    
    import json
    with open(genai_config_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if update_device_type_in_json(data, device_type):
        logger.info(f"Updated device_type to {device_type} in {genai_config_path}")
        with open(genai_config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)


def built_in_evaluator(args):
    import onnxruntime_genai as og
    import json
    import shutil

    # Get configurations
    inferenceModeConfig = "inference_model.json"
    inferenceModelDir = "model"
    warmup = 5
    repetitions = 10

    history_model_folder = Path(args.model_config).parent
    # before olive 0.10.0, model_config is sibling of model folder
    # on and after olive 0.10.0, model_config is in model folder
    if not (history_model_folder / inferenceModelDir).exists():
        history_model_folder = history_model_folder.parent

    project_folder = history_model_folder.parent.parent

    historyInferenceModelPath = history_model_folder / inferenceModelDir / inferenceModeConfig
    if not historyInferenceModelPath.exists():
        projInferenceModelPath = project_folder / inferenceModeConfig
        if not projInferenceModelPath.exists():
            logger.warning(f"Model config file {inferenceModeConfig} does not exist. The evaluation result may be inaccurate.")
        else:
            shutil.copyfile(projInferenceModelPath, historyInferenceModelPath)

    if historyInferenceModelPath.exists():
        with open(historyInferenceModelPath, "r", encoding="utf-8") as file:
            inference_config = json.load(file)
            text_template = inference_config["PromptTemplate"]["prompt"]
    else:
        text_template = "{Content}"

    with open(args.config, "r", encoding="utf-8") as file:
        olive_config = json.load(file)
    evaluator_config = olive_config["evaluators"]["modelLab_llm_evaluator"]
    prompt_length = evaluator_config["prompt_length"]
    generation_length = evaluator_config["generation_length"]

    # Create model
    model_folder = history_model_folder / inferenceModelDir

    syncDeviceTypeToGenaiConfig(olive_config, model_folder)

    model = og.Model(str(model_folder))
    tokenizer = og.Tokenizer(model)
    
    params = og.GeneratorParams(model)

    logger.info("Evaluating model ...")

    # not exactly same length
    with open(Path(__file__).parent / "built_in_prompts.json", "r", encoding="utf-8") as file:
        import json
        prompts = json.load(file)

    for i in range(warmup):
        input_tokens = built_in_get_input_tokens(prompts, tokenizer, prompt_length, i, text_template)
        built_in_run_one(model, params, input_tokens, generation_length, tokenizer)

    result = []
    ftls = []
    prompt_times = []
    for i in range(repetitions):
        input_tokens = built_in_get_input_tokens(prompts, tokenizer, prompt_length, i + warmup, text_template)
        latencies, ftl, prompt_time = built_in_run_one(model, params, input_tokens, generation_length, tokenizer)
        logger.info("Token generation latencies (ms): %s", json.dumps([round(float(x) * 1000, 1) for x in latencies]))
        result.append(latencies)
        ftls.append(ftl)
        prompt_times.append(prompt_time)

    # Output metrics
    metrics = get_results(result, ftls, prompt_times)
    output_file = Path(args.config).parent / "metrics.json"
    resultStr = json.dumps(metrics, indent=4)
    with open(output_file, 'w') as file:
        file.write(resultStr)
    logger.info("Model lab succeeded for evaluation.\n%s", resultStr)


if __name__ == "__main__":
    main()

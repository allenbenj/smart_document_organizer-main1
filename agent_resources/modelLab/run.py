import argparse
import json
from pathlib import Path
from modelLab import logger

def is_winml_runtime(runtime):
    return runtime == "WCR" or runtime == "WCR_CUDA" or runtime == "QNN_LLM"

def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="path to input config file")
    parser.add_argument("--runtime", required=True, help="runtime")
    parser.add_argument("--aitk_version", type=str, help="AITK version")
    return parser.parse_args()


def add_aitk_version(history_folder: Path, aitk_version: str):
    import onnx
    from olive.passes.onnx.common import model_proto_to_file

    onnx_files = list((history_folder).glob("**/*.onnx"))
    metadata = {"aitk_version": aitk_version}
    for file in onnx_files:
        onnx_model = onnx.load_model(file, load_external_data=False)
        new_metadata_props = {entry.key: entry.value for entry in onnx_model.metadata_props}
        new_metadata_props.update(metadata)
        onnx.helper.set_model_props(onnx_model, new_metadata_props)
        # Look like it is better
        model_proto_to_file(onnx_model, file)
        logger.info("Added AITK version %s to ONNX model %s.", aitk_version, file.name)


def fix_qnn_gpu_llm_config(history_folder: Path):
    config_file = history_folder / "model" / "genai_config.json"
    if not config_file.exists():
        return
    with open(config_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        provider_options = (
            data.get("model", {})
                .get("decoder", {})
                .get("session_options", {})
                .get("provider_options", [])
        )
        if not provider_options:
            return
    for item in provider_options:
        # Each item is a dict, e.g. {"qnn": {...}}
        for provider, opts in item.items():
            if provider.lower() == "qnn":
                if opts.get("backend_type") == "gpu":
                    opts["device_filtering_options"] = {
                        "hardware_device_type": "GPU"
                    }
                    with open(config_file, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=4)
                    logger.info("Update genai_config.json due to https://github.com/microsoft/onnxruntime-genai/issues/1963.")
                    return


def main():
    args = parse_arguments()

    aitk_python = None
    with open(args.config, 'r', encoding='utf-8') as file:
        oliveJson = json.load(file)
        # TODO disable evaluator
        oliveJson.pop("evaluator", None)
        oliveJson.pop("evaluators", None)
        aitk_pass = oliveJson.get("passes", {}).get("aitkpython")
        if aitk_pass and aitk_pass.get("type") == "AitkPython":
            aitk_python = aitk_pass.get("user_script")

    if aitk_python:
        import subprocess
        import sys
        subprocess.run([sys.executable, aitk_python, "--config", args.config, "--runtime", args.runtime],
                        check=True)
        # create a dummy model file to indicate success
        (Path(args.config).parent / "model" / "model_config.json").touch()
    else:
        if is_winml_runtime(args.runtime):
            from modelLab import register_execution_providers_to_onnxruntime
            register_execution_providers_to_onnxruntime()
        import olive
        import olive.workflows

        output = olive.workflows.run(oliveJson)
        if output is None or not output.has_output_model():
            error = "Model file is not generated"
            logger.error(error)
            raise Exception(error)

    if args.aitk_version:
        add_aitk_version(Path(args.config).parent, args.aitk_version)
    fix_qnn_gpu_llm_config(Path(args.config).parent)
    logger.info("Model lab succeeded for conversion.")

if __name__ == "__main__":
    main()

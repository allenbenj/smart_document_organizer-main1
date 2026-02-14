import json
import sys
from pathlib import Path
from huggingface_hub import ModelCard, repo_info, hf_hub_download, list_repo_tree
from datasets import load_dataset


def fetch_model_card(model_id: str, output_dir: str) -> dict:
    """Input is model id (HuggingFace model identifier) and workspace directory.
    Saves model card text to one file, and samples to another file.
    Returns:
        dict: A dictionary containing:

            - ``model_card_file`` (str): Absolute path to the text file containing
              the model card for ``model_id``.
            - ``samples_file`` (str): Absolute path to the JSON file containing
              widget data and example dataset samples associated with the model.
            - ``json_config_files`` (List[str]): List of absolute paths to small
              JSON configuration files (< 10KB) downloaded from the model
              repository. The list may be empty if no such files are found.
    """
    card = ModelCard.load(model_id)
    datasets = getattr(card.data, "datasets", list()) or list()

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    model_card_filename = f"{model_id.replace('/', '_')}_model_card.txt"
    model_card_path = output_dir / model_card_filename
    model_card_path.write_text(card.text, encoding="utf-8")

    info = {
        "model_id": model_id,
        "widget_data": [],
        "dataset_samples": [],
    }
    for dataset in datasets:
        dataset_entry = {
            "name": dataset,
            "sample": None,
        }
        try:
            ds = load_dataset(
                dataset, split="train", streaming=True, trust_remote_code=False
            )
            dataset_entry["sample"] = next(iter(ds))
            info["dataset_samples"].append(dataset_entry)
            break  # only get first successful dataset
        except Exception as e:
            pass

    try:
        model_repo_info = repo_info(model_id, repo_type="model")
        info["widget_data"] = getattr(model_repo_info, "widget_data", None)
    except Exception as e:
        pass

    samples_filename = f"{model_id.replace('/', '_')}_samples.json"
    samples_path = output_dir / samples_filename
    samples_path.write_text(json.dumps(info, indent=2, default=str), encoding="utf-8")

    # Download JSON config files
    size_threshold = 10 * 1024  # 10KB threshold
    json_config_files = []

    repo_tree = list_repo_tree(model_id, recursive=True)

    for item in repo_tree:
        if (
            hasattr(item, "size")
            and item.path.endswith(".json")
            and item.size <= size_threshold
        ):
            try:
                local_path = hf_hub_download(
                    repo_id=model_id,
                    filename=item.path,
                    local_dir=output_dir,
                )
                json_config_files.append(Path(local_path).absolute().as_posix())
            except Exception as e:
                pass

    return {
        "model_card_file": model_card_path.as_posix(),
        "samples_file": samples_path.as_posix(),
        "json_config_files": json_config_files,
    }


if __name__ == "__main__":
    model_id = sys.argv[1]
    output_dir = sys.argv[2]
    result = fetch_model_card(model_id, output_dir)
    print(json.dumps(result))

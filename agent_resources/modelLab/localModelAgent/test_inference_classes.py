import json
import sys
import os
import argparse
from onnx_task_model import ONNXTaskModel

def get_widget_samples(samples_json_path):
    if samples_json_path:
        with open(samples_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('widget_data', [])
    else:
        return []

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Test inference classes with ONNX model')
    parser.add_argument('--model-path', type=str, required=True,
                        help='Path to the ONNX model file')
    parser.add_argument('--samples-json', type=str, required=False,
                        help='Path to the JSON file containing samples')
    args = parser.parse_args()
    onnx_model_path = args.model_path

    widget_samples = get_widget_samples(args.samples_json)

    sys.path.append(os.getcwd())
    from inference_classes import *

    for cls in ONNXTaskModel.__subclasses__():
        model = cls()
        assert model.demo_sample is not None or widget_samples, "No demo_sample or widget_data samples available for testing."
        if widget_samples:
            for sample in widget_samples:
                model.inference_demo(onnx_model_path, sample)
        if model.demo_sample is not None:
            model.inference_demo(onnx_model_path, model.demo_sample)
import sys
import json
from pathlib import Path
import onnx


def fetch_onnx_file_info(model_path_or_dir: str, output_dir: str) -> dict:
    """
    Extract ONNX file info, save it to a sidecar file, and return file paths.

    The function can handle either a single ONNX file or a directory containing
    ONNX files. It extracts I/O metadata and writes to ``<model_filename>.info.txt``
    files in ``output_dir``.

    Args:
        model_path_or_dir: Absolute path to an ONNX model file or directory containing ONNX files.
        output_dir: Directory where the ``.info.txt`` files will be written.

    Returns:
        dict: A dictionary where each key is an ONNX filename and the value is the
              POSIX-style path to its corresponding ``.info.txt`` file.
    """
    path = Path(model_path_or_dir)
    result = {}

    if path.is_file():
        # Single ONNX file
        model = onnx.load(str(path))
        info_text = get_onnx_file_info(model)
        info_path = Path(output_dir) / (path.name + ".info.txt")
        info_path.write_text(info_text, encoding="utf-8")
        result[path.name] = info_path.as_posix()
    elif path.is_dir():
        # Directory containing ONNX files
        onnx_files = list(path.glob("*.onnx"))
        for onnx_file in onnx_files:
            model = onnx.load(str(onnx_file))
            info_text = get_onnx_file_info(model)
            info_path = Path(output_dir) / (onnx_file.name + ".info.txt")
            info_path.write_text(info_text, encoding="utf-8")
            result[onnx_file.name] = info_path.as_posix()
    else:
        raise ValueError(f"Path does not exist or is not a file/directory: {model_path_or_dir}")

    return result


def get_onnx_file_info(model):
    """
    Load an ONNX file and return its I/O metadata as a formatted string.
    """
    lines = ["Inputs:"]
    for t in model.graph.input:
        elem_type = t.type.tensor_type.elem_type
        shape = friendly_shape(t.type.tensor_type)
        lines.append(
            f"  {t.name}: "
            f"dtype={onnx.TensorProto.DataType.Name(elem_type)}, "
            f"shape={shape}"
        )

    lines += ["", "Outputs:"]
    for t in model.graph.output:
        elem_type = t.type.tensor_type.elem_type
        shape = friendly_shape(t.type.tensor_type)
        lines.append(
            f"  {t.name}: "
            f"dtype={onnx.TensorProto.DataType.Name(elem_type)}, "
            f"shape={shape}"
        )

    return "\n".join(lines)


def friendly_shape(tensor_type):
    """
    Return a list of dimension sizes where dynamic dimensions are
    represented by their symbolic names instead of None.
    """
    dims = []
    for d in tensor_type.shape.dim:
        if d.dim_value:  # Non-zero static dimension
            dims.append(d.dim_value)
        elif d.dim_param:  # Dynamic dimension with symbolic name
            dims.append(d.dim_param)
        else:  # Completely unknown dimension
            dims.append(None)
    return dims


if __name__ == "__main__":
    model_path_or_dir = sys.argv[1]
    output_dir = sys.argv[2]
    result = fetch_onnx_file_info(model_path_or_dir, output_dir)
    print(json.dumps(result))

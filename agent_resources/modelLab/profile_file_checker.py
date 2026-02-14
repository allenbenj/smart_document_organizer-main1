import onnx

from modelLab import logger, ExitErrorCodes

def check_model_file(model: onnx.ModelProto):
    all_names = set()
    for node in model.graph.node:
        if not node.name:
            logger.error("Not all nodes have names.")
            return ExitErrorCodes.ONNX_FILE_BAD_NAME
        if node.name in all_names:
            logger.error(f"Node name {node.name} is duplicated.")
            return ExitErrorCodes.ONNX_FILE_BAD_NAME
        all_names.add(node.name)
    return 0


def fix_model_file(model: onnx.ModelProto):
    all_names = set()
    op_id: dict[str, int] = {}
    for node in model.graph.node:
        if not node.name:
            id = op_id.get(node.op_type, 0)
            node.name = f"{node.op_type}_{id}"
            while node.name in all_names:
                id += 1
                node.name = f"{node.op_type}_{id}"
            op_id[node.op_type] = id + 1
        elif node.name in all_names:
            id = 2
            new_name = f"{node.name}_{id}"
            while new_name in all_names:
                id += 1
                new_name = f"{node.name}_{id}"
            node.name = new_name
        all_names.add(node.name)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Simple ONNX File Check Tool.")
    parser.add_argument("--model_path", default="", help="model path")
    parser.add_argument("--output_path", default="", help="fixed model")
    parser.add_argument("--runtime", help="runtime arg placeholder")

    args = parser.parse_args()
    model = onnx.load(args.model_path, load_external_data=False)
    if args.output_path:
        import os
        fix_model_file(model)
        output_path = args.output_path if os.path.isabs(args.output_path) else os.path.join(os.path.dirname(args.model_path), args.output_path)
        onnx.save(model, output_path)
    else:
        exit(check_model_file(model))

if __name__ == "__main__":
    main()

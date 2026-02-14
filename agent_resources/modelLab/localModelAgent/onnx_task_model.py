from abc import ABC, abstractmethod

class ONNXTaskModel(ABC):
    '''
    in __init__ method, the subclass should define self.output_names, which should be a list as a subset of the model's all output names.
    '''
    demo_sample = None # to specify in subclass, if model card documents include sample code to easily define/obtain a sample input for the model

    @abstractmethod
    def preprocess_input(self, sample):
        '''
        This method should perform the following steps:
        1. If sample is a widget data structure, extract the relevant input data from it
        2. preprocess the input sample to match the input format of the PyTorch model, matching input_names
        3. Convert the above inputs into a dictionary of (input_name, numpy_array) that can be used as input for the ONNX inference session. Note that all float
        '''
        pass

    @abstractmethod
    def show_results(self, result):
        '''
        Show results of the inference, e.g., print prediction or visualize in human-friendly manner, based on model card document; postprocess the output as needed.
        The result is computed from the ONNX inference session.
        '''
        pass

    def inference_demo(self, onnx_model_path, sample):
        '''
        Run inference on a sample input and show the results.
        '''
        import io
        import onnxruntime as ort
        import numpy as np

        sess_options = ort.SessionOptions()
        # workaround
        sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_EXTENDED
        session = ort.InferenceSession(onnx_model_path, sess_options=sess_options)
        preprocessed_sample = self.preprocess_input(sample)
        outputs = session.run(
            self.output_names,
            preprocessed_sample
        )
        results = {name: output for name, output in zip(self.output_names, outputs)}
        # IMPORTANT: Casting float16 arrays to float32 before any post processing to avoid numerical issues.
        for name, output in results.items():
            if isinstance(output, np.ndarray) and output.dtype == np.float16:
                results[name] = output.astype(np.float32)
        self.show_results(results)
import onnxruntime as ort
from modelLab import  register_execution_providers_to_onnxruntime

register_execution_providers_to_onnxruntime()

ep_devices = ort.get_ep_devices()

for ep_device in ep_devices:
    # DO NOT CHANGE THIS. It is used in runtimeSetup
    print(f"----support ep_devices---- {ep_device.ep_name} {ep_device.device.type}")

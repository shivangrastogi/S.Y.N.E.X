import sys

# Completely disable ONNX and ONNXSCRIPT imports
sys.modules['onnx'] = None
sys.modules['onnxscript'] = None
sys.modules['torch.onnx'] = None
sys.modules['torch.onnx._internal'] = None
sys.modules['torch.onnx._internal.fx'] = None
sys.modules['torch.onnx._internal.fx.passes'] = None

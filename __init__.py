# Package initializer for OpenAICompat node
# Expose the NODE mappings so ComfyUI can discover the node class.
from .OpenAICompat import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]

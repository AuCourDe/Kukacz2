"""Whisper Analyzer application package."""

# KRYTYCZNE: Patche muszą być PRZED jakimikolwiek importami!
import functools

# Patch 1: huggingface_hub - pyannote używa starego API 'use_auth_token'
import huggingface_hub.file_download
_original_hf_download = huggingface_hub.file_download.hf_hub_download
@functools.wraps(_original_hf_download)
def _patched_hf_download(*args, **kwargs):
    if 'use_auth_token' in kwargs:
        token_value = kwargs.pop('use_auth_token')
        if token_value and 'token' not in kwargs:
            kwargs['token'] = token_value
    return _original_hf_download(*args, **kwargs)
huggingface_hub.file_download.hf_hub_download = _patched_hf_download

# Patch 2: torch.load - PyTorch 2.x wymaga weights_only=False dla pyannote
import torch
import torch.serialization
torch.serialization._default_to_weights_only = lambda: False
_original_torch_load = torch.load
@functools.wraps(_original_torch_load)
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load
torch.serialization.load = _patched_torch_load

__all__ = []

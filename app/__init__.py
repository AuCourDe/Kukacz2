"""Whisper Analyzer application package."""

# KRYTYCZNE: Patch dla torch.load musi być zastosowany PRZED jakimkolwiek importem torch
# Naprawia błąd "persistent id instruction" w PyTorch 2.x
import functools
import torch
import torch.serialization

_original_torch_load = torch.load

@functools.wraps(_original_torch_load)
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load
torch.serialization.load = _patched_torch_load

__all__ = []

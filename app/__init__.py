"""Whisper Analyzer application package."""

# KRYTYCZNE: Patch dla torch.load - naprawia błąd "persistent id instruction" w PyTorch 2.x
# Musi być wykonany PRZED jakimkolwiek użyciem torch.load
import torch
import torch.serialization

# Metoda 1: Nadpisanie funkcji zwracającej domyślną wartość weights_only
torch.serialization._default_to_weights_only = lambda: False

# Metoda 2: Patch torch.load jako backup
import functools
_original_torch_load = torch.load

@functools.wraps(_original_torch_load)
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)

torch.load = _patched_torch_load
torch.serialization.load = _patched_torch_load

__all__ = []

#!/usr/bin/env python3
"""
Moduł do transkrypcji mowy na tekst
====================================

Zawiera funkcje do:
- Ładowania modelu Whisper
- Transkrypcji plików audio na tekst
- Obsługi błędów i ponownych prób
- Optymalizacji wydajności transkrypcji
"""

import logging
import os
import time
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
import torch
import torch.serialization
from cryptography.fernet import Fernet

# Workaround for PyTorch 2.6+ weights_only=True breaking whisper model loading
# The whisper library uses weights_only=True but the checkpoint contains TorchVersion
# See: https://pytorch.org/docs/stable/generated/torch.load.html
def _patch_torch_load_for_whisper():
    """Patch torch.load to handle weights_only issues in PyTorch 2.6+"""
    _original_torch_load = torch.load
    
    def _patched_load(*args, **kwargs):
        try:
            return _original_torch_load(*args, **kwargs)
        except Exception as e:
            error_msg = str(e)
            # If weights_only causes the error, retry with weights_only=False
            if "weights_only" in error_msg or "WeightsUnpickler" in error_msg:
                kwargs["weights_only"] = False
                return _original_torch_load(*args, **kwargs)
            raise
    
    torch.load = _patched_load

# Apply patch before importing whisper
_patch_torch_load_for_whisper()

import whisper

from .config import (
    MODEL_CACHE_DIR,
    WHISPER_NO_SPEECH_THRESHOLD,
    WHISPER_LOGPROB_THRESHOLD,
    WHISPER_CONDITION_ON_PREVIOUS_TEXT,
    WHISPER_TEMPERATURE,
    WHISPER_FP16,
)

logger = logging.getLogger(__name__)

class WhisperTranscriber:
    """Transkrypcja mowy na tekst za pomocą modelu Whisper"""
    
    def __init__(self):
        self.model = None
        self.device = "cpu"
        self._fp16 = False
        self.encryption_key = Fernet.generate_key()
        self.cipher = Fernet(self.encryption_key)
        logger.info("WhisperTranscriber zainicjalizowany")
    
    def load_model(self, model_name: str = "large-v3") -> None:
        """Ładowanie modelu Whisper do pamięci"""
        try:
            model_cache_dir = MODEL_CACHE_DIR
            model_cache_dir.mkdir(parents=True, exist_ok=True)
            model_file = model_cache_dir / f"{model_name}.pt"

            if not model_file.exists():
                logger.info(
                    "Model Whisper '%s' nie został znaleziony w cache. Pobieranie...",
                    model_name,
                )
            else:
                logger.info("Znaleziono model Whisper '%s' w %s", model_name, model_file)

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self._fp16 = self.device != "cpu"

            logger.info("Ładowanie modelu Whisper: %s (urządzenie: %s)", model_name, self.device)
            self.model = whisper.load_model(
                model_name,
                download_root=str(model_cache_dir),
                device=self.device,
            )
            logger.info(
                "Model Whisper '%s' przygotowany w katalogu %s",
                model_name,
                model_cache_dir,
            )
            if self.device == "cpu":
                logger.info("Nie wykryto karty graficznej - używanie trybu CPU")
            else:
                logger.info("Wykryto GPU - wykorzystanie akceleracji CUDA")
        except Exception as e:
            logger.error(f"Błąd podczas ładowania modelu Whisper: {e}")
            raise
    
    def encrypt_file(self, file_path: Path) -> bytes:
        """Szyfrowanie pliku tymczasowego dla bezpieczeństwa"""
        with open(file_path, 'rb') as f:
            data = f.read()
        return self.cipher.encrypt(data)
    
    def decrypt_file(self, encrypted_data: bytes, output_path: Path) -> None:
        """Deszyfrowanie pliku tymczasowego"""
        decrypted_data = self.cipher.decrypt(encrypted_data)
        with open(output_path, 'wb') as f:
            f.write(decrypted_data)
    
    def transcribe_audio(self, audio_file_path: Path, max_retries: int = 3) -> Optional[Dict]:
        """Transkrypcja pliku audio na tekst z obsługą błędów"""
        
        if not self.model:
            logger.error("Model Whisper nie został załadowany")
            return None
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Transkrypcja pliku: {audio_file_path.name} (próba {attempt + 1}/{max_retries})")
                
                # Szyfrowanie pliku tymczasowego
                encrypted_data = self.encrypt_file(audio_file_path)
                
                # Utworzenie tymczasowego pliku do przetwarzania
                safe_suffix = audio_file_path.suffix if audio_file_path.suffix else ".tmp"
                with tempfile.NamedTemporaryFile(suffix=safe_suffix, delete=False) as temp_file:
                    temp_path = Path(temp_file.name)
                    self.decrypt_file(encrypted_data, temp_path)
                    
                    # Transkrypcja z modelem large-v3 dla najwyższej dokładności
                    # Parametry zoptymalizowane dla obsługi długich pauz w nagraniach
                    result = self.model.transcribe(
                        str(temp_path),
                        language="pl",  # Język polski
                        task="transcribe",
                        fp16=self._fp16 and WHISPER_FP16,
                        no_speech_threshold=WHISPER_NO_SPEECH_THRESHOLD,
                        logprob_threshold=WHISPER_LOGPROB_THRESHOLD,
                        condition_on_previous_text=WHISPER_CONDITION_ON_PREVIOUS_TEXT,
                        temperature=WHISPER_TEMPERATURE,
                    )
                    
                    # Usunięcie tymczasowego pliku
                    temp_path.unlink()
                
                transcribed_text = result["text"].strip()
                logger.info(f"Transkrypcja zakończona pomyślnie: {audio_file_path.name}")
                logger.info(f"Długość tekstu: {len(transcribed_text)} znaków")
                
                return {
                    "text": transcribed_text,
                    "segments": result.get("segments", [])
                }
                
            except Exception as e:
                logger.error(f"Błąd podczas transkrypcji {audio_file_path.name} (próba {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"Wszystkie próby transkrypcji nieudane dla: {audio_file_path.name}")
                    return None
        
        return None 
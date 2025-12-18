#!/usr/bin/env python3
"""
Moduł do weryfikacji dostępności modeli przed uruchomieniem aplikacji
=====================================================================
"""

import logging
import sys
from pathlib import Path
from typing import List, Tuple

logger = logging.getLogger(__name__)


def check_whisper_model(model_name: str, cache_dir: Path) -> Tuple[bool, str]:
    """Sprawdzenie czy model Whisper jest dostępny lokalnie"""
    model_file = cache_dir / f"{model_name}.pt"
    if model_file.exists():
        return True, f"Model Whisper '{model_name}' znaleziony w {model_file}"
    return False, f"Model Whisper '{model_name}' nie został znaleziony w {cache_dir}"


def check_pyannote_model(model_name: str, cache_dir: Path) -> Tuple[bool, str]:
    """Sprawdzenie czy model pyannote jest dostępny lokalnie w folderze models/pyannote"""
    try:
        # Sprawdzenie w models/pyannote (struktura cache HuggingFace)
        pyannote_cache_dir = cache_dir / "pyannote"
        model_cache_name = model_name.replace("/", "--")
        
        # Sprawdzamy w dwóch możliwych lokalizacjach:
        # 1. models/pyannote/hub/models--org--model (standardowa struktura HF)
        # 2. models/pyannote/models--org--model (alternatywna struktura)
        possible_paths = [
            pyannote_cache_dir / "hub" / f"models--{model_cache_name}",
            pyannote_cache_dir / f"models--{model_cache_name}",
        ]
        
        for model_cache_path in possible_paths:
            if model_cache_path.exists():
                # Sprawdzamy czy są pliki modelu (w snapshots, blobs lub bezpośrednio)
                model_exists = (
                    any(model_cache_path.rglob("*.bin")) or
                    any(model_cache_path.rglob("*.safetensors")) or
                    any(model_cache_path.rglob("config.yaml")) or
                    any(model_cache_path.rglob("config.json")) or
                    any(model_cache_path.rglob("*.pt")) or
                    any(model_cache_path.rglob("*.pth")) or
                    (model_cache_path / "blobs").exists() or
                    (model_cache_path / "snapshots").exists()
                )
                
                if model_exists:
                    # Znajdź konkretną ścieżkę do modelu
                    snapshot_dirs = list((model_cache_path / "snapshots").glob("*")) if (model_cache_path / "snapshots").exists() else []
                    if snapshot_dirs:
                        return True, f"Model pyannote '{model_name}' znaleziony w {snapshot_dirs[0]}"
                    return True, f"Model pyannote '{model_name}' znaleziony w {model_cache_path}"
        
        return False, f"Model pyannote '{model_name}' nie został znaleziony w {pyannote_cache_dir}"
    except Exception as e:
        return False, f"Błąd podczas sprawdzania modelu pyannote: {e}"


def check_ollama_model(model_name: str, base_url: str) -> Tuple[bool, str]:
    """Sprawdzenie czy model Ollama jest dostępny na serwerze"""
    try:
        import requests
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get("models", [])
            available_models = [model["name"] for model in models]
            if model_name in available_models:
                return True, f"Model Ollama '{model_name}' jest dostępny na serwerze"
            return False, f"Model Ollama '{model_name}' nie jest dostępny. Dostępne modele: {', '.join(available_models) or 'brak'}"
        return False, f"Nie można połączyć się z serwerem Ollama ({base_url})"
    except Exception as e:
        return False, f"Błąd podczas sprawdzania modelu Ollama: {e}"


def ask_user_continue(missing_models: List[str]) -> bool:
    """Pytanie użytkownika czy kontynuować pomimo brakujących modeli"""
    print("\n" + "=" * 60)
    print("⚠️  UWAGA: Niektóre modele nie są dostępne:")
    print("=" * 60)
    for model_info in missing_models:
        print(f"  ❌ {model_info}")
    print("=" * 60)
    print("\nAplikacja może nie działać poprawnie bez tych modeli.")
    print("Modele zostaną pobrane automatycznie przy pierwszym użyciu.")
    
    while True:
        response = input("\nCzy chcesz kontynuować uruchamianie aplikacji? (tak/nie): ").strip().lower()
        if response in ("tak", "t", "yes", "y"):
            return True
        elif response in ("nie", "n", "no"):
            return False
        else:
            print("Proszę odpowiedzieć 'tak' lub 'nie'")


def check_all_models(
    whisper_model: str,
    whisper_cache_dir: Path,
    enable_speaker_diarization: bool,
    speaker_diarization_model: str,
    speaker_cache_dir: Path,
    enable_ollama_analysis: bool,
    ollama_model: str,
    ollama_base_url: str,
) -> bool:
    """
    Sprawdzenie dostępności wszystkich wymaganych modeli
    
    Returns:
        True jeśli wszystkie modele są dostępne lub użytkownik chce kontynuować
        False jeśli użytkownik chce przerwać
    """
    missing_models = []
    
    # Sprawdzenie modelu Whisper
    logger.info("Sprawdzanie dostępności modelu Whisper...")
    available, message = check_whisper_model(whisper_model, whisper_cache_dir)
    if not available:
        missing_models.append(f"Whisper: {message}")
    else:
        logger.info(f"✓ {message}")
    
    # Sprawdzenie modelu pyannote (jeśli włączone)
    if enable_speaker_diarization:
        logger.info("Sprawdzanie dostępności modelu pyannote...")
        available, message = check_pyannote_model(speaker_diarization_model, speaker_cache_dir)
        if not available:
            missing_models.append(f"pyannote: {message}")
        else:
            logger.info(f"✓ {message}")
    
    # Sprawdzenie modelu Ollama (jeśli włączone)
    if enable_ollama_analysis:
        logger.info("Sprawdzanie dostępności modelu Ollama...")
        available, message = check_ollama_model(ollama_model, ollama_base_url)
        if not available:
            missing_models.append(f"Ollama: {message}")
        else:
            logger.info(f"✓ {message}")
    
    # Jeśli wszystkie modele są dostępne, kontynuuj
    if not missing_models:
        logger.info("✓ Wszystkie wymagane modele są dostępne")
        return True
    
    # Jeśli brakuje modeli, zapytaj użytkownika
    return ask_user_continue(missing_models)


#!/usr/bin/env python3
"""
Wejściowy moduł aplikacji.
"""

import logging
import os
import sys
import time

from .config import (
    WHISPER_MODEL,
    SPEAKER_DIARIZATION_TOKEN,
    SPEAKER_DIARIZATION_MODEL,
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    MODEL_CACHE_DIR,
    LOG_LEVEL,
    LOG_FILE,
    ENABLE_SPEAKER_DIARIZATION,
    ENABLE_OLLAMA_ANALYSIS,
)
from .audio_processor import AudioProcessor
from .model_checker import check_all_models
from .colored_logging import setup_colored_logging, print_colored

# Konfiguracja logowania z obsługą kolorów
setup_colored_logging(
    level=LOG_LEVEL,
    log_file=str(LOG_FILE),
    enable_colors=True
)
logger = logging.getLogger(__name__)

def main():
    """Główna funkcja aplikacji z pełną inicjalizacją i uruchomieniem systemu"""
    try:
        if ENABLE_SPEAKER_DIARIZATION and not SPEAKER_DIARIZATION_TOKEN:
            message = (
                "Brak tokenu Hugging Face dla rozpoznawania mówców.\n"
                "1. Wejdź na https://huggingface.co/pyannote/speaker-diarization-3.1 "
                "i zaakceptuj warunki dostępu.\n"
                "2. Skopiuj swój token (zakładka Settings → Access Tokens).\n"
                "3. Dodaj wartość zmiennej SPEAKER_DIARIZATION_TOKEN do pliku .env "
                "(np. SPEAKER_DIARIZATION_TOKEN=\"hf_xxx\") i uruchom ponownie aplikację."
            )
            logger.error(message)
            print(message, file=sys.stderr)
            sys.exit(1)

        logger.info("=== Uruchamianie aplikacji Whisper Analyzer ===")
        
        # Sprawdzenie dostępności modeli przed uruchomieniem
        logger.info("Sprawdzanie dostępności modeli...")
        continue_launch = check_all_models(
            whisper_model=WHISPER_MODEL,
            whisper_cache_dir=MODEL_CACHE_DIR,
            enable_speaker_diarization=ENABLE_SPEAKER_DIARIZATION,
            speaker_diarization_model=SPEAKER_DIARIZATION_MODEL,
            speaker_cache_dir=MODEL_CACHE_DIR,
            enable_ollama_analysis=ENABLE_OLLAMA_ANALYSIS,
            ollama_model=OLLAMA_MODEL,
            ollama_base_url=OLLAMA_BASE_URL,
        )
        
        if not continue_launch:
            logger.info("Uruchamianie aplikacji przerwane przez użytkownika")
            print("\nUruchamianie aplikacji zostało przerwane.")
            sys.exit(0)
        
        # Inicjalizacja procesora audio
        processor = AudioProcessor(
            enable_speaker_diarization=ENABLE_SPEAKER_DIARIZATION, 
            enable_ollama_analysis=ENABLE_OLLAMA_ANALYSIS
        )
        
        # Inicjalizacja wszystkich komponentów
        processor.initialize_components(
            whisper_model=WHISPER_MODEL,
            speaker_auth_token=SPEAKER_DIARIZATION_TOKEN,
            ollama_model=OLLAMA_MODEL
        )
        
        # Sprawdzenie czy model Ollama został poprawnie zainicjalizowany
        if ENABLE_OLLAMA_ANALYSIS:
            if not processor.content_analyzer or not processor.content_analyzer.initialized:
                try:
                    import requests
                    response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
                    if response.status_code == 200:
                        models = response.json().get("models", [])
                        available_models = [model["name"] for model in models]
                        if OLLAMA_MODEL not in available_models:
                            warning_msg = (
                                f"\n⚠️  OSTRZEŻENIE: Model Ollama '{OLLAMA_MODEL}' nie jest dostępny na serwerze!\n"
                                f"   Dostępne modele: {', '.join(available_models) or 'brak'}\n"
                                f"   Analiza Ollama będzie wyłączona. Aby włączyć analizę, ustaw w .env:\n"
                                f"   OLLAMA_MODEL=jedna_z_dostępnych_nazw_modeli\n"
                            )
                            print_colored(warning_msg, "WARNING", sys.stderr)
                            logger.warning(
                                f"Model Ollama '{OLLAMA_MODEL}' nie jest dostępny. "
                                f"Dostępne modele: {', '.join(available_models)}"
                            )
                except Exception as e:
                    logger.debug(f"Nie udało się sprawdzić dostępności modeli Ollama: {e}")
        
        # Przetwarzanie istniejących plików
        logger.info("Przetwarzanie istniejących plików...")
        processor.process_all_files()
        logger.success("Przetwarzanie wszystkich plików zakończone")

        run_once = os.getenv("APP_RUN_ONCE", "false").lower() == "true"
        if run_once:
            logger.success("Tryb jednorazowy aktywny (APP_RUN_ONCE=1) – kończę po pierwszym przebiegu.")
            return
        
        # Uruchomienie obserwatora folderu
        logger.info("Uruchamianie obserwatora folderu...")
        processor.start_file_watcher()
        
        logger.success("Aplikacja uruchomiona. Oczekiwanie na nowe pliki...")
        logger.info(f"Umieść pliki MP3 w folderze: {processor.file_loader.input_folder}")
        logger.info("Naciśnij Ctrl+C aby zatrzymać")
        
        # Pętla główna aplikacji
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Otrzymano sygnał zatrzymania...")
            processor.stop_file_watcher()
            logger.success("Aplikacja zatrzymana")
        
    except Exception as e:
        logger.critical(f"Błąd krytyczny: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 
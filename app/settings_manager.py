#!/usr/bin/env python3
"""
Moduł do zarządzania ustawieniami aplikacji
===========================================

Zawiera funkcje do:
- Odczytu i zapisu ustawień do pliku .env
- Definicji wszystkich dostępnych ustawień z opisami
- Walidacji wartości ustawień
- Grupowania ustawień w kategorie/zakładki
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import BASE_DIR

logger = logging.getLogger(__name__)

# Ścieżka do pliku .env
ENV_FILE_PATH = BASE_DIR / ".env"


# Definicje wszystkich ustawień z opisami i wartościami domyślnymi
# Struktura: {nazwa: {default, type, description, alternatives, category}}
SETTINGS_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    # ============================================
    # KATEGORIA: Modele AI
    # ============================================
    "WHISPER_MODEL": {
        "default": "base",
        "type": "select",
        "options": ["tiny", "base", "small", "medium", "large", "large-v2", "large-v3"],
        "description": "Model Whisper do transkrypcji mowy",
        "alternatives": "small (szybsze na CPU), large-v3 (lepsza jakość, wolniejsze)",
        "category": "models",
    },
    "OLLAMA_MODEL": {
        "default": "gemma3:12b",
        "type": "text",
        "description": "Model Ollama do analizy treści",
        "alternatives": "gemma3:8b (szybsze), qwen3:8b (alternatywny)",
        "category": "models",
    },
    "OLLAMA_BASE_URL": {
        "default": "http://localhost:11434",
        "type": "text",
        "description": "Adres bazowy serwera Ollama",
        "alternatives": "http://<remote-ip>:11434 (zdalny serwer)",
        "category": "models",
    },
    "SPEAKER_DIARIZATION_MODEL": {
        "default": "pyannote/speaker-diarization-3.1",
        "type": "text",
        "description": "Model do segmentacji rozmów (rozpoznawanie mówców)",
        "alternatives": "pyannote/speaker-diarization-3.0 (starsza wersja)",
        "category": "models",
    },
    "SPEAKER_DIARIZATION_TOKEN": {
        "default": "",
        "type": "password",
        "description": "Token Hugging Face dla pyannote.audio",
        "alternatives": "Puste = wyłącza pyannote",
        "category": "models",
    },
    
    # ============================================
    # KATEGORIA: Parametry Ollama
    # ============================================
    "OLLAMA_TEMPERATURE": {
        "default": "0.7",
        "type": "number",
        "min": 0.0,
        "max": 2.0,
        "step": 0.1,
        "description": "Temperatura generowania (losowość)",
        "alternatives": "0.3 (deterministyczne), 1.0 (kreatywne)",
        "category": "ollama",
    },
    "OLLAMA_TOP_P": {
        "default": "0.9",
        "type": "number",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "description": "Top-p (nucleus sampling)",
        "alternatives": "0.8 (konserwatywne), 1.0 (pełna dystrybucja)",
        "category": "ollama",
    },
    "OLLAMA_TOP_K": {
        "default": "40",
        "type": "number",
        "min": 1,
        "max": 100,
        "step": 1,
        "description": "Top-k (liczba rozważanych tokenów)",
        "alternatives": "20 (szybciej), 80 (większa różnorodność)",
        "category": "ollama",
    },
    "OLLAMA_REPEAT_PENALTY": {
        "default": "1.1",
        "type": "number",
        "min": 1.0,
        "max": 2.0,
        "step": 0.05,
        "description": "Kara za powtórzenia",
        "alternatives": "1.0 (bez kary), 1.3 (silniejsze karanie)",
        "category": "ollama",
    },
    "OLLAMA_NUM_PREDICT": {
        "default": "-1",
        "type": "number",
        "min": -1,
        "max": 8192,
        "step": 256,
        "description": "Maksymalna liczba tokenów w odpowiedzi (-1 = bez limitu)",
        "alternatives": "1024, 2048, 4096",
        "category": "ollama",
    },
    "OLLAMA_CONNECT_TIMEOUT": {
        "default": "10.0",
        "type": "number",
        "min": 1.0,
        "max": 60.0,
        "step": 1.0,
        "description": "Timeout połączenia z Ollama (sekundy)",
        "alternatives": "5.0 (krótszy), 20.0 (dłuższy)",
        "category": "ollama",
    },
    "OLLAMA_REQUEST_TIMEOUT": {
        "default": "180.0",
        "type": "number",
        "min": 30.0,
        "max": 600.0,
        "step": 30.0,
        "description": "Timeout żądania do Ollama (sekundy)",
        "alternatives": "60.0 (krótszy), 300.0 (dłuższy)",
        "category": "ollama",
    },
    "MAX_TRANSCRIPT_LENGTH": {
        "default": "8000",
        "type": "number",
        "min": 1000,
        "max": 32000,
        "step": 1000,
        "description": "Maksymalna długość transkrypcji (znaki)",
        "alternatives": "4000 (mniej), 12000 (więcej)",
        "category": "ollama",
    },
    "OLLAMA_DEBUG_LOGGING": {
        "default": "false",
        "type": "boolean",
        "description": "Włącz szczegółowe logi Ollama",
        "alternatives": "true (pełne logi request/response)",
        "category": "ollama",
    },
    "OLLAMA_STREAM_RESPONSES": {
        "default": "false",
        "type": "boolean",
        "description": "Strumieniowe odbieranie odpowiedzi",
        "alternatives": "true (odbiór strumieniowy z logiem chunków)",
        "category": "ollama",
    },
    
    # ============================================
    # KATEGORIA: Preprocessing Audio
    # ============================================
    "AUDIO_PREPROCESS_ENABLED": {
        "default": "true",
        "type": "boolean",
        "description": "Włącz preprocessing audio przed transkrypcją",
        "alternatives": "false (wyłącza preprocessing)",
        "category": "audio",
    },
    "AUDIO_PREPROCESS_NOISE_REDUCE": {
        "default": "true",
        "type": "boolean",
        "description": "Włącz odszumianie audio",
        "alternatives": "false (wyłącza odszumianie)",
        "category": "audio",
    },
    "AUDIO_PREPROCESS_NORMALIZE": {
        "default": "true",
        "type": "boolean",
        "description": "Włącz normalizację głośności",
        "alternatives": "false (wyłącza normalizację)",
        "category": "audio",
    },
    "AUDIO_PREPROCESS_GAIN_DB": {
        "default": "1.5",
        "type": "number",
        "min": 0.0,
        "max": 10.0,
        "step": 0.5,
        "description": "Wzmocnienie głośności (dB)",
        "alternatives": "0.0 (bez wzmocnienia), 3.0 (silniejsze)",
        "category": "audio",
    },
    "AUDIO_PREPROCESS_COMPRESSOR": {
        "default": "true",
        "type": "boolean",
        "description": "Włącz kompresor dynamiki",
        "alternatives": "false (wyłącza kompresor)",
        "category": "audio",
    },
    "AUDIO_PREPROCESS_EQ": {
        "default": "true",
        "type": "boolean",
        "description": "Włącz EQ (wzmocnienie zakresu mowy)",
        "alternatives": "false (wyłącza EQ)",
        "category": "audio",
    },
    
    # ============================================
    # KATEGORIA: Parametry Whisper
    # ============================================
    "WHISPER_NO_SPEECH_THRESHOLD": {
        "default": "0.2",
        "type": "number",
        "min": 0.0,
        "max": 1.0,
        "step": 0.05,
        "description": "Próg wykrywania ciszy (niższy = mniej przerywania)",
        "alternatives": "0.6 (domyślny Whisper), 0.1 (bardzo czuły)",
        "category": "whisper",
    },
    "WHISPER_LOGPROB_THRESHOLD": {
        "default": "none",
        "type": "text",
        "description": "Próg log-prawdopodobieństwa (none = wyłączony)",
        "alternatives": "-1.0 (standardowy)",
        "category": "whisper",
    },
    "WHISPER_CONDITION_ON_PREVIOUS_TEXT": {
        "default": "false",
        "type": "boolean",
        "description": "Warunkuj na poprzednim tekście",
        "alternatives": "true (może poprawić spójność)",
        "category": "whisper",
    },
    
    # ============================================
    # KATEGORIA: Foldery i ścieżki
    # ============================================
    "INPUT_FOLDER": {
        "default": "input",
        "type": "text",
        "description": "Folder plików wejściowych",
        "alternatives": "MEDIA_FILES (katalog produkcyjny)",
        "category": "paths",
    },
    "OUTPUT_FOLDER": {
        "default": "output",
        "type": "text",
        "description": "Folder wyników (transkrypcje, analizy)",
        "alternatives": "reports (inny katalog)",
        "category": "paths",
    },
    "PROCESSED_FOLDER": {
        "default": "processed",
        "type": "text",
        "description": "Folder przetworzonych plików audio",
        "alternatives": "archive/processed",
        "category": "paths",
    },
    "MODEL_CACHE_DIR": {
        "default": "models",
        "type": "text",
        "description": "Folder cache modeli",
        "alternatives": "/mnt/cache/models",
        "category": "paths",
    },
    "PROMPT_DIR": {
        "default": "prompt",
        "type": "text",
        "description": "Folder z promptami analizy",
        "alternatives": "custom_prompts",
        "category": "paths",
    },
    
    # ============================================
    # KATEGORIA: Funkcjonalności
    # ============================================
    "ENABLE_SPEAKER_DIARIZATION": {
        "default": "true",
        "type": "boolean",
        "description": "Włącz rozpoznawanie mówców",
        "alternatives": "false (wyłącza diarization)",
        "category": "features",
    },
    "ENABLE_OLLAMA_ANALYSIS": {
        "default": "true",
        "type": "boolean",
        "description": "Włącz analizę treści przez Ollama",
        "alternatives": "false (pomija analizy treści)",
        "category": "features",
    },
    "MAX_CONCURRENT_PROCESSES": {
        "default": "1",
        "type": "number",
        "min": 1,
        "max": 8,
        "step": 1,
        "description": "Liczba równoczesnych przetwarzań",
        "alternatives": "2 (większa szybkość), 4 (agresywna równoległość)",
        "category": "features",
    },
    "APP_RUN_ONCE": {
        "default": "false",
        "type": "boolean",
        "description": "Tryb jednorazowy (kończy po jednym przebiegu)",
        "alternatives": "true (dla batch processing)",
        "category": "features",
    },
    
    # ============================================
    # KATEGORIA: Logowanie
    # ============================================
    "LOG_LEVEL": {
        "default": "INFO",
        "type": "select",
        "options": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        "description": "Poziom szczegółowości logów",
        "alternatives": "DEBUG (więcej), WARNING (mniej)",
        "category": "logging",
    },
    "LOG_FILE": {
        "default": "whisper_analyzer.log",
        "type": "text",
        "description": "Ścieżka do pliku logów",
        "alternatives": "logs/whisper.log",
        "category": "logging",
    },
    "MAX_RETRIES": {
        "default": "3",
        "type": "number",
        "min": 1,
        "max": 10,
        "step": 1,
        "description": "Liczba prób transkrypcji",
        "alternatives": "1 (mniej), 5 (więcej)",
        "category": "logging",
    },
    "RETRY_DELAY_BASE": {
        "default": "2",
        "type": "number",
        "min": 1,
        "max": 10,
        "step": 1,
        "description": "Bazowy czas między próbami (sekundy)",
        "alternatives": "1 (krótszy), 4 (dłuższy)",
        "category": "logging",
    },
    
    # ============================================
    # KATEGORIA: Bezpieczeństwo
    # ============================================
    "ENABLE_FILE_ENCRYPTION": {
        "default": "true",
        "type": "boolean",
        "description": "Szyfruj pliki tymczasowe",
        "alternatives": "false (bez szyfrowania)",
        "category": "security",
    },
    "TEMPORARY_FILE_CLEANUP": {
        "default": "true",
        "type": "boolean",
        "description": "Automatycznie usuwaj pliki tymczasowe",
        "alternatives": "false (zostawia do debugowania)",
        "category": "security",
    },
    
    # ============================================
    # KATEGORIA: Interfejs webowy
    # ============================================
    "WEB_HOST": {
        "default": "0.0.0.0",
        "type": "text",
        "description": "Host interfejsu webowego",
        "alternatives": "127.0.0.1 (tylko lokalnie)",
        "category": "web",
    },
    "WEB_PORT": {
        "default": "8080",
        "type": "number",
        "min": 1024,
        "max": 65535,
        "step": 1,
        "description": "Port interfejsu webowego",
        "alternatives": "5000 (Flask domyślny), 443 (HTTPS)",
        "category": "web",
    },
    "WEB_LOGIN": {
        "default": "admin",
        "type": "text",
        "description": "Login do panelu webowego",
        "alternatives": "Dowolna nazwa użytkownika",
        "category": "web",
    },
    "WEB_PASSWORD": {
        "default": "admin",
        "type": "password",
        "description": "Hasło do panelu webowego",
        "alternatives": "Silne hasło",
        "category": "web",
    },
    "WEB_SECRET_KEY": {
        "default": "change_me",
        "type": "text",
        "description": "Klucz sesji Flask (min. 32 znaki)",
        "alternatives": "Wygeneruj: python -c \"import secrets; print(secrets.token_urlsafe(32))\"",
        "category": "web",
    },
}

# Definicje kategorii (zakładek)
SETTINGS_CATEGORIES = {
    "models": {
        "name": "Modele AI",
        "icon": "🤖",
        "description": "Ustawienia modeli Whisper, Ollama i rozpoznawania mówców",
    },
    "ollama": {
        "name": "Parametry Ollama",
        "icon": "⚙️",
        "description": "Szczegółowe parametry generowania odpowiedzi przez Ollama",
    },
    "audio": {
        "name": "Preprocessing Audio",
        "icon": "🔊",
        "description": "Ustawienia poprawy jakości audio przed transkrypcją",
    },
    "whisper": {
        "name": "Parametry Whisper",
        "icon": "🎙️",
        "description": "Szczegółowe parametry transkrypcji Whisper",
    },
    "paths": {
        "name": "Foldery",
        "icon": "📁",
        "description": "Ścieżki do folderów wejściowych, wyjściowych i modeli",
    },
    "features": {
        "name": "Funkcjonalności",
        "icon": "✨",
        "description": "Włączanie/wyłączanie funkcji aplikacji",
    },
    "logging": {
        "name": "Logowanie",
        "icon": "📝",
        "description": "Ustawienia logowania i ponawiania operacji",
    },
    "security": {
        "name": "Bezpieczeństwo",
        "icon": "🔒",
        "description": "Ustawienia szyfrowania i bezpieczeństwa",
    },
    "web": {
        "name": "Interfejs WWW",
        "icon": "🌐",
        "description": "Ustawienia serwera webowego i autoryzacji",
    },
}


class SettingsManager:
    """Zarządzanie ustawieniami aplikacji"""

    def __init__(self, env_path: Optional[Path] = None):
        self.env_path = env_path or ENV_FILE_PATH
        logger.info(f"SettingsManager zainicjalizowany - plik: {self.env_path}")

    def get_all_settings(self) -> Dict[str, Dict[str, Any]]:
        """Pobiera wszystkie ustawienia z ich aktualnymi wartościami."""
        current_values = self._read_env_file()
        
        result = {}
        for key, definition in SETTINGS_DEFINITIONS.items():
            result[key] = {
                **definition,
                "value": current_values.get(key, definition["default"]),
                "is_default": key not in current_values,
            }
        
        return result

    def get_settings_by_category(self) -> Dict[str, Dict[str, Any]]:
        """Pobiera ustawienia pogrupowane według kategorii."""
        all_settings = self.get_all_settings()
        
        categorized = {}
        for category_key, category_info in SETTINGS_CATEGORIES.items():
            categorized[category_key] = {
                **category_info,
                "settings": {},
            }
        
        for key, setting in all_settings.items():
            category = setting.get("category", "features")
            if category in categorized:
                categorized[category]["settings"][key] = setting
        
        return categorized

    def get_setting(self, key: str) -> Optional[str]:
        """Pobiera pojedyncze ustawienie."""
        current_values = self._read_env_file()
        if key in current_values:
            return current_values[key]
        if key in SETTINGS_DEFINITIONS:
            return SETTINGS_DEFINITIONS[key]["default"]
        return None

    def save_settings(self, settings: Dict[str, str]) -> Tuple[bool, str]:
        """Zapisuje ustawienia do pliku .env."""
        try:
            # Walidacja
            for key, value in settings.items():
                if key not in SETTINGS_DEFINITIONS:
                    continue  # Ignoruj nieznane klucze
                
                is_valid, error = self._validate_setting(key, value)
                if not is_valid:
                    return False, f"Błąd walidacji {key}: {error}"
            
            # Odczytaj istniejący plik
            current_values = self._read_env_file()
            
            # Zaktualizuj wartości
            current_values.update(settings)
            
            # Zapisz do pliku
            self._write_env_file(current_values)
            
            logger.info(f"Zapisano {len(settings)} ustawień do {self.env_path}")
            return True, "Ustawienia zapisane pomyślnie"
            
        except Exception as e:
            logger.error(f"Błąd zapisu ustawień: {e}")
            return False, f"Błąd zapisu: {str(e)}"

    def _read_env_file(self) -> Dict[str, str]:
        """Odczytuje plik .env."""
        values = {}
        
        if not self.env_path.exists():
            return values
        
        try:
            with open(self.env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    
                    if "=" in line:
                        key, _, value = line.partition("=")
                        key = key.strip()
                        value = value.strip()
                        
                        # Usuń cudzysłowy jeśli są
                        if (value.startswith('"') and value.endswith('"')) or \
                           (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        
                        values[key] = value
        except Exception as e:
            logger.error(f"Błąd odczytu pliku .env: {e}")
        
        return values

    def _write_env_file(self, values: Dict[str, str]) -> None:
        """Zapisuje plik .env z komentarzami."""
        lines = []
        
        # Grupuj według kategorii
        for category_key, category_info in SETTINGS_CATEGORIES.items():
            category_settings = [
                (k, v) for k, v in values.items()
                if k in SETTINGS_DEFINITIONS and 
                SETTINGS_DEFINITIONS[k].get("category") == category_key
            ]
            
            if category_settings:
                lines.append(f"\n# {category_info['icon']} {category_info['name']}")
                lines.append(f"# {'-' * 50}")
                
                for key, value in sorted(category_settings):
                    definition = SETTINGS_DEFINITIONS.get(key, {})
                    desc = definition.get("description", "")
                    
                    # Dodaj wartość (z cudzysłowami dla tekstu ze spacjami)
                    if " " in str(value) or not value:
                        lines.append(f'{key}="{value}"  # {desc}')
                    else:
                        lines.append(f"{key}={value}  # {desc}")
        
        # Zapisz do pliku
        with open(self.env_path, "w", encoding="utf-8") as f:
            f.write("# Konfiguracja Whisper Analyzer\n")
            f.write("# Wygenerowano automatycznie przez panel ustawień\n")
            f.write("\n".join(lines))
            f.write("\n")

    def _validate_setting(self, key: str, value: str) -> Tuple[bool, str]:
        """Waliduje wartość ustawienia."""
        if key not in SETTINGS_DEFINITIONS:
            return True, ""  # Nieznane klucze są OK
        
        definition = SETTINGS_DEFINITIONS[key]
        setting_type = definition.get("type", "text")
        
        if setting_type == "number":
            try:
                num_value = float(value)
                min_val = definition.get("min")
                max_val = definition.get("max")
                
                if min_val is not None and num_value < min_val:
                    return False, f"Wartość musi być >= {min_val}"
                if max_val is not None and num_value > max_val:
                    return False, f"Wartość musi być <= {max_val}"
            except ValueError:
                return False, "Wartość musi być liczbą"
        
        elif setting_type == "boolean":
            if value.lower() not in ("true", "false", "1", "0", "yes", "no"):
                return False, "Wartość musi być true/false"
        
        elif setting_type == "select":
            options = definition.get("options", [])
            if options and value not in options:
                return False, f"Wartość musi być jedną z: {', '.join(options)}"
        
        return True, ""

    def get_categories(self) -> Dict[str, Dict[str, str]]:
        """Zwraca listę kategorii."""
        return SETTINGS_CATEGORIES


# Singleton
_settings_manager_instance: Optional[SettingsManager] = None


def get_settings_manager() -> SettingsManager:
    """Zwraca singleton SettingsManager."""
    global _settings_manager_instance
    if _settings_manager_instance is None:
        _settings_manager_instance = SettingsManager()
    return _settings_manager_instance


__all__ = [
    "SettingsManager",
    "get_settings_manager",
    "SETTINGS_DEFINITIONS",
    "SETTINGS_CATEGORIES",
]

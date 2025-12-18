#!/usr/bin/env python3
"""
Moduł do wczytywania i walidacji plików audio
==============================================

Zawiera funkcje do:
- Sprawdzania poprawności plików audio w popularnych formatach
- Wczytywania plików z folderu wejściowego
- Filtrowania plików według kryteriów
- Obserwowania zmian w folderze wejściowym
"""

import os
import logging
import time
import threading
from pathlib import Path
from typing import Iterable, List, Optional, Union
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)

SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".acc",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}


class AudioFileValidator:
    """Walidacja plików audio."""

    SUPPORTED_EXTENSIONS = SUPPORTED_AUDIO_EXTENSIONS

    @classmethod
    def is_supported_extension(cls, file_path: Path) -> bool:
        """Sprawdzenie czy rozszerzenie pliku jest obsługiwane."""
        return file_path.suffix.lower() in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def describe_supported_extensions(cls) -> str:
        """Zwraca listę obsługiwanych rozszerzeń w formie tekstowej."""
        return ", ".join(sorted(ext.lstrip(".") for ext in cls.SUPPORTED_EXTENSIONS))

    @classmethod
    def is_valid_audio_file(cls, file_path: Path) -> bool:
        """Sprawdzenie czy plik jest poprawnym i obsługiwanym plikiem audio."""
        if not file_path.exists():
            return False

        if not cls.is_supported_extension(file_path):
            return False

        if file_path.stat().st_size == 0:
            return False

        return True

class AudioFileLoader:
    """Wczytywanie plików audio z folderu wejściowego."""

    def __init__(self, input_folder: Union[str, Path] = "input"):
        self.input_folder = Path(input_folder)
        self.input_folder.mkdir(parents=True, exist_ok=True)
        logger.info(
            "AudioFileLoader zainicjalizowany - folder: %s (formaty: %s)",
            self.input_folder,
            AudioFileValidator.describe_supported_extensions(),
        )

    def _iter_supported_files(self) -> Iterable[Path]:
        for candidate in self.input_folder.iterdir():
            if candidate.is_file() and AudioFileValidator.is_supported_extension(candidate):
                yield candidate

    def get_audio_files(self) -> List[Path]:
        """Pobranie wszystkich obsługiwanych plików audio z folderu wejściowego."""
        candidates = list(self._iter_supported_files())
        valid_files = [f for f in candidates if AudioFileValidator.is_valid_audio_file(f)]

        logger.info(
            "Znaleziono %d poprawnych plików audio (%s)",
            len(valid_files),
            AudioFileValidator.describe_supported_extensions(),
        )
        return valid_files

    def get_unprocessed_files(self, output_folder: Path) -> List[Path]:
        """
        Pobranie plików audio do przetworzenia.

        W aktualnym podejściu zawsze zwracamy wszystkie pliki znajdujące się w folderze
        wejściowym – nawet jeśli wcześniej istniały już wyniki dla tej samej nazwy.
        Dzięki temu użytkownik może świadomie ponownie przetworzyć plik.
        """
        audio_files = self.get_audio_files()
        logger.info(
            "Znaleziono %d plików audio do przetworzenia",
            len(audio_files),
        )
        return audio_files

class FileWatcher(FileSystemEventHandler):
    """Obserwator folderu do automatycznego przetwarzania nowych plików"""
    
    def __init__(self, processor, input_folder: Path):
        self.processor = processor
        self.input_folder = input_folder
        logger.info("FileWatcher zainicjalizowany")
    
    def on_created(self, event):
        """Obsługa zdarzenia utworzenia nowego pliku"""
        if not event.is_directory:
            file_path = Path(event.src_path)
            if AudioFileValidator.is_supported_extension(file_path):
                logger.info("Wykryto nowy plik audio: %s", file_path.name)
                # Krótkie opóźnienie aby plik został w pełni zapisany
                time.sleep(1)
                if AudioFileValidator.is_valid_audio_file(file_path):
                    threading.Thread(
                        target=self.processor.process_audio_file,
                        args=(file_path,),
                    ).start()
                else:
                    logger.warning("Pominięto niepoprawny plik audio: %s", file_path.name)
            else:
                logger.debug("Ignoruję plik z nieobsługiwanym rozszerzeniem: %s", file_path.name)

class FileWatcherManager:
    """Zarządzanie obserwatorem folderu"""
    
    def __init__(self, processor, input_folder: Path):
        self.processor = processor
        self.input_folder = input_folder
        self.observer = None
        self.event_handler = None
    
    def start_watching(self):
        """Uruchomienie obserwacji folderu"""
        self.event_handler = FileWatcher(self.processor, self.input_folder)
        self.observer = Observer()
        self.observer.schedule(self.event_handler, str(self.input_folder), recursive=False)
        self.observer.start()
        logger.info("Obserwator folderu uruchomiony")
    
    def stop_watching(self):
        """Zatrzymanie obserwacji folderu"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            logger.info("Obserwator folderu zatrzymany") 
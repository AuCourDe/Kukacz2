#!/usr/bin/env python3
"""
Główny moduł do przetwarzania plików audio
==========================================

Zawiera główną klasę AudioProcessor która:
- Koordynuje wszystkie komponenty systemu
- Zarządza procesem transkrypcji i analizy
- Obsługuje przetwarzanie równoległe
- Integruje wszystkie moduły systemu z konfiguracją
"""
import logging
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from .config import (
    INPUT_FOLDER,
    OUTPUT_FOLDER,
    PROCESSED_FOLDER,
    ENABLE_SPEAKER_DIARIZATION,
    ENABLE_OLLAMA_ANALYSIS,
    MAX_CONCURRENT_PROCESSES,
)
from .file_loader import AudioFileLoader, FileWatcherManager
from .speech_transcriber import WhisperTranscriber
from .speaker_diarizer import SpeakerDiarizer, SimpleSpeakerDiarizer
from .content_analyzer import ContentAnalyzer
from .result_saver import ResultSaver
from .processing_queue import ProcessingQueue
from .audio_preprocessor import AudioPreprocessor

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Główna klasa do przetwarzania plików audio z integracją wszystkich komponentów"""
    
    def __init__(self, input_folder: Union[str, Path] = INPUT_FOLDER, 
                 output_folder: Union[str, Path] = OUTPUT_FOLDER, 
                 enable_speaker_diarization: bool = ENABLE_SPEAKER_DIARIZATION, 
                 enable_ollama_analysis: bool = ENABLE_OLLAMA_ANALYSIS,
                 processing_queue: Optional[ProcessingQueue] = None):
        # Inicjalizacja komponentów
        input_folder_path = Path(input_folder)
        output_folder_path = Path(output_folder)

        self.file_loader = AudioFileLoader(input_folder_path)
        self.transcriber = WhisperTranscriber()
        self.speaker_diarizer = SpeakerDiarizer()
        self.content_analyzer = ContentAnalyzer()
        self.audio_preprocessor = AudioPreprocessor()
        self._processed_folder = Path(PROCESSED_FOLDER)
        self._processed_folder.mkdir(parents=True, exist_ok=True)
        self.result_saver = ResultSaver(output_folder_path)
        self.file_watcher = FileWatcherManager(self, input_folder_path)
        self.processing_queue = processing_queue
        
        # Konfiguracja funkcjonalności
        self.enable_speaker_diarization = enable_speaker_diarization
        self.enable_ollama_analysis = enable_ollama_analysis
        self.use_simple_diarization = False
        
        # Kontrola równoległości
        self.max_concurrent = MAX_CONCURRENT_PROCESSES
        self.semaphore = threading.Semaphore(self.max_concurrent)
        
        logger.info(f"AudioProcessor zainicjalizowany")
        logger.info(f"Rozpoznawanie mówców: {'Włączone' if enable_speaker_diarization else 'Wyłączone'}")
        logger.info(f"Analiza Ollama: {'Włączona' if enable_ollama_analysis else 'Wyłączona'}")
    
    def initialize_components(self, whisper_model: str = None, 
                            speaker_auth_token: Optional[str] = None,
                            ollama_model: str = None) -> None:
        """Inicjalizacja wszystkich komponentów systemu"""
        try:
            from .config import WHISPER_MODEL, OLLAMA_MODEL
            
            # Ładowanie modelu Whisper
            model_to_load = whisper_model if whisper_model else WHISPER_MODEL
            self.transcriber.load_model(model_to_load)
            
            # Inicjalizacja rozpoznawania mówców
            if self.enable_speaker_diarization:
                self.use_simple_diarization = False
                from .config import SPEAKER_DIARIZATION_MODEL
                success = self.speaker_diarizer.initialize(
                    speaker_auth_token, 
                    model_name=SPEAKER_DIARIZATION_MODEL
                )
                if not success:
                    logger.warning(
                        "Zaawansowane rozpoznawanie mówców niedostępne – "
                        "używam heurystycznego podziału na mówców."
                    )
                    self.use_simple_diarization = True
            
            # Inicjalizacja analizy Ollama
            if self.enable_ollama_analysis:
                model_to_use = ollama_model if ollama_model else OLLAMA_MODEL
                self.content_analyzer = ContentAnalyzer(model=model_to_use)
                success = self.content_analyzer.initialize()
                if not success:
                    logger.warning("Analiza Ollama będzie wyłączona")
                    self.enable_ollama_analysis = False
            
            logger.success("Wszystkie komponenty zainicjalizowane pomyślnie")
            
        except Exception as e:
            logger.error(f"Błąd podczas inicjalizacji komponentów: {e}")
            raise
    
    def transcribe_audio_with_speakers(self, audio_file_path: Path) -> Optional[dict]:
        """Transkrypcja pliku audio z rozpoznawaniem mówców"""
        try:
            # Transkrypcja audio na tekst
            transcription_data = self.transcriber.transcribe_audio(audio_file_path)
            if not transcription_data:
                return None
            
            # Rozpoznawanie mówców (jeśli włączone)
            speakers_data = None
            segments = transcription_data.get("segments", [])
            if self.enable_speaker_diarization:
                if not self.use_simple_diarization:
                    speakers_data = self.speaker_diarizer.diarize_speakers(audio_file_path)
                
                # Jeśli zaawansowane rozpoznawanie nie działa, użyj prostego algorytmu
                if not speakers_data:
                    logger.info("Używanie prostego rozpoznawania mówców...")
                    speakers_data = SimpleSpeakerDiarizer.diarize_speakers(segments)
            
            # Dodanie danych o mówcach do wyników transkrypcji
            transcription_data["speakers"] = speakers_data
            
            return transcription_data
            
        except Exception as e:
            logger.error(f"Błąd podczas transkrypcji z mówcami: {e}")
            return None
    
    def process_audio_file(self, audio_file_path: Path, queue_item_id: Optional[str] = None, enable_preprocessing: bool = True) -> dict:
        """Przetwarzanie pojedynczego pliku audio z pełnym pipeline"""
        with self.semaphore:  # Ograniczenie liczby równoczesnych przetwarzań
            result_summary: dict = {
                "success": False,
                "transcription_file": None,
                "analysis_file": None,
                "processed_audio": None,
                "timestamp": None,
            }
            if self.processing_queue and queue_item_id:
                self.processing_queue.mark_processing(queue_item_id)
            try:
                logger.info(f"Rozpoczęcie przetwarzania: {audio_file_path.name}")
                
                # Preprocessing audio (jeśli włączony)
                original_file_path = audio_file_path
                processed_file_path = None
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                
                if enable_preprocessing and self.audio_preprocessor.enabled:
                    logger.info("Wstępne przetwarzanie audio...")
                    temp_processed = self.audio_preprocessor.process(audio_file_path)
                    if temp_processed and temp_processed != audio_file_path:
                        processed_file_path = temp_processed
                        audio_file_path = temp_processed  # Używamy przetworzonego pliku do transkrypcji
                        logger.info(f"Audio przetworzone: {processed_file_path.name}")
                
                # Kopiowanie oryginalnego pliku do processed
                original_destination_name = f"{original_file_path.stem} {timestamp}{original_file_path.suffix}"
                original_destination = self.processed_folder / original_destination_name
                original_destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(original_file_path), str(original_destination))
                logger.debug(f"Skopiowano oryginalny plik do: {original_destination_name}")
                
                # Transkrypcja z rozpoznawaniem mówców (na przetworzonym lub oryginalnym pliku)
                transcription_data = self.transcribe_audio_with_speakers(audio_file_path)
                if transcription_data:
                    # Analiza treści za pomocą Ollama (jeśli włączona)
                    analysis_results = None
                    if self.enable_ollama_analysis:
                        analysis_results = self.content_analyzer.analyze_transcription_content(transcription_data)
                        logger.info(f"Analiza Ollama zakończona dla: {audio_file_path.name}")
                    else:
                        logger.info(f"Analiza Ollama wyłączona, pominięto analizę treści.")
                    
                    # Zapisanie wyników (używamy oryginalnej nazwy pliku)
                    self.result_saver.save_transcription_with_speakers(
                        original_file_path,
                        transcription_data,
                        analysis_results,
                        timestamp=timestamp,
                    )
                    transcription_filename = f"{original_file_path.stem} {timestamp}.txt"
                    analysis_filename = f"{original_file_path.stem} ANALIZA {timestamp}.txt"
                    
                    # Przeniesienie przetworzonego pliku do folderu processed (jeśli istnieje)
                    processed_destination_name = None
                    if processed_file_path and processed_file_path.exists():
                        processed_destination_name = f"{original_file_path.stem} processed {timestamp}{processed_file_path.suffix}"
                        processed_destination = self.processed_folder / processed_destination_name
                        processed_destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.move(str(processed_file_path), str(processed_destination))
                        logger.debug(f"Przeniesiono przetworzony plik do: {processed_destination_name}")
                    
                    # Usunięcie oryginalnego pliku z input folderu (już skopiowany do processed)
                    if original_file_path.exists() and original_file_path.parent == self.file_loader.input_folder:
                        original_file_path.unlink()
                        logger.debug(f"Usunięto oryginalny plik z folderu input: {original_file_path.name}")
                    logger.success(
                        "Przetwarzanie zakończone pomyślnie: %s (plik do: %s)",
                        original_file_path.name,
                        self.processed_folder,
                    )
                    result_summary.update(
                        {
                            "success": True,
                            "timestamp": timestamp,
                            "transcription_file": transcription_filename,
                            "analysis_file": analysis_filename,
                            "processed_audio": original_destination_name,
                            "processed_audio_enhanced": processed_destination_name,
                        }
                    )
                    if self.processing_queue and queue_item_id:
                        result_files = {
                            "transcription": transcription_filename,
                            "analysis": analysis_filename,
                            "processed_audio": original_destination_name,
                        }
                        if processed_destination_name:
                            result_files["processed_audio_enhanced"] = processed_destination_name
                        self.processing_queue.mark_completed(
                            queue_item_id,
                            result_files,
                        )
                else:
                    logger.error(f"Nie udało się przetworzyć pliku: {audio_file_path.name}")
                    if self.processing_queue and queue_item_id:
                        self.processing_queue.mark_failed(
                            queue_item_id,
                            "Nie udało się przetworzyć pliku – brak danych transkrypcji.",
                        )
                
            except Exception as e:
                logger.error(f"Błąd podczas przetwarzania {audio_file_path.name}: {e}")
                if self.processing_queue and queue_item_id:
                    self.processing_queue.mark_failed(queue_item_id, str(e))
            finally:
                return result_summary

    @property
    def processed_folder(self) -> Path:
        return self._processed_folder

    @processed_folder.setter
    def processed_folder(self, value: Union[str, Path]) -> None:
        new_path = Path(value)
        new_path.mkdir(parents=True, exist_ok=True)
        self._processed_folder = new_path
    
    def process_all_files(self) -> None:
        """Przetwarzanie wszystkich obsługiwanych plików audio w folderze wejściowym."""
        try:
            # Pobranie nieprzetworzonych plików
            unprocessed_files = self.file_loader.get_unprocessed_files(self.result_saver.output_folder)
            
            if not unprocessed_files:
                logger.info("Brak plików audio do przetworzenia")
                return
            
            logger.info("Znaleziono %d plików audio do przetworzenia", len(unprocessed_files))
            
            # Przetwarzanie plików w puli wątków
            threads = []
            for audio_file in unprocessed_files:
                thread = threading.Thread(
                    target=self.process_audio_file,
                    args=(audio_file,)
                )
                threads.append(thread)
                thread.start()
            
            # Oczekiwanie na zakończenie wszystkich wątków
            for thread in threads:
                thread.join()
            
            logger.success("Przetwarzanie wszystkich plików zakończone")
            
        except Exception as e:
            logger.error(f"Błąd podczas przetwarzania plików: {e}")
    
    def start_file_watcher(self) -> None:
        """Uruchomienie obserwatora folderu"""
        self.file_watcher.start_watching()
    
    def stop_file_watcher(self) -> None:
        """Zatrzymanie obserwatora folderu"""
        self.file_watcher.stop_watching() 
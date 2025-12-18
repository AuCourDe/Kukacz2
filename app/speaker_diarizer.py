#!/usr/bin/env python3
"""
Moduł do rozpoznawania mówców (Speaker Diarization)
===================================================

Zawiera funkcje do:
- Rozpoznawania różnych osób mówiących w nagraniu
- Analizy segmentów czasowych dla każdego mówcy
- Automatycznego przełączania między mówcami
- Obsługi zaawansowanych i prostych algorytmów diarization
"""

import logging
import os
from pathlib import Path
from typing import List, Optional, Dict, Tuple
import torch
import numpy as np
from collections import defaultdict

# Monkey-patch dla kompatybilności z nowszymi wersjami huggingface_hub
# PyAnnote używa use_auth_token, ale nowsze wersje używają token
try:
    import huggingface_hub.file_download
    original_hf_hub_download = huggingface_hub.file_download.hf_hub_download
    import functools
    
    @functools.wraps(original_hf_hub_download)
    def patched_hf_hub_download(*args, **kwargs):
        # Zamiana use_auth_token na token
        if 'use_auth_token' in kwargs:
            token_value = kwargs.pop('use_auth_token')
            if token_value and 'token' not in kwargs:
                kwargs['token'] = token_value
        return original_hf_hub_download(*args, **kwargs)
    
    # Zastosowanie monkey-patch przed importem PyAnnote
    huggingface_hub.file_download.hf_hub_download = patched_hf_hub_download
except Exception:
    pass  # Jeśli nie uda się zastosować patch, kontynuuj normalnie

# Importy dla rozpoznawania mówców
try:
    from pyannote.audio import Pipeline
    from pyannote.audio.pipelines.utils.hook import ProgressHook
    SPEAKER_DIARIZATION_AVAILABLE = True
except ImportError:
    SPEAKER_DIARIZATION_AVAILABLE = False
    logging.warning("pyannote.audio nie jest dostępne. Rozpoznawanie mówców będzie wyłączone.")

logger = logging.getLogger(__name__)

class SpeakerDiarizer:
    """Rozpoznawanie osób mówiących w nagraniu audio"""
    
    def __init__(self):
        self.pipeline = None
        self.initialized = False
        logger.info("SpeakerDiarizer zainicjalizowany")
        
    def initialize(self, auth_token: Optional[str] = None, model_name: Optional[str] = None) -> bool:
        """Inicjalizacja pipeline do rozpoznawania mówców z obsługą różnych metod autoryzacji"""
        if not SPEAKER_DIARIZATION_AVAILABLE:
            logger.warning("pyannote.audio nie jest dostępne")
            return False
        
        # Pobranie nazwy modelu z konfiguracji jeśli nie podano
        if model_name is None:
            from .config import SPEAKER_DIARIZATION_MODEL, MODEL_CACHE_DIR
            model_name = SPEAKER_DIARIZATION_MODEL
        else:
            from .config import MODEL_CACHE_DIR
        
        # Ustawienie katalogu dla modeli pyannote w models/pyannote
        pyannote_cache_dir = MODEL_CACHE_DIR / "pyannote"
        pyannote_cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Katalog cache dla modeli pyannote: {pyannote_cache_dir}")
        
        # Ustawienie zmiennych środowiskowych dla HuggingFace
        os.environ["HF_HOME"] = str(pyannote_cache_dir)
        os.environ["HUGGINGFACE_HUB_CACHE"] = str(pyannote_cache_dir / "hub")
        if auth_token:
            os.environ["HF_TOKEN"] = auth_token
        (pyannote_cache_dir / "hub").mkdir(parents=True, exist_ok=True)
            
        try:
            logger.info(f"Inicjalizacja rozpoznawania mówców z modelem: {model_name}...")
            logger.info(f"Używanie cache: {pyannote_cache_dir}")
            
            # Sprawdzenie czy model już istnieje w cache
            hub_cache_dir = pyannote_cache_dir / "hub"
            model_exists = False
            if hub_cache_dir.exists():
                # Sprawdzamy czy model jest w cache HuggingFace (struktura: models--org--model)
                model_cache_name = model_name.replace("/", "--")
                model_cache_path = hub_cache_dir / f"models--{model_cache_name}"
                if model_cache_path.exists() and (any(model_cache_path.rglob("*.bin")) or any(model_cache_path.rglob("*.safetensors"))):
                    model_exists = True
                    logger.info(f"Model znaleziony w cache: {model_cache_path}")
            
            if not model_exists:
                logger.info(f"Model nie został znaleziony w cache, pobieranie do {pyannote_cache_dir}...")
            
            # Załadowanie modelu - Pipeline.from_pretrained automatycznie pobierze model jeśli nie istnieje
            try:
                # Logowanie do HuggingFace jeśli token jest dostępny
                if auth_token:
                    try:
                        from huggingface_hub import login
                        login(token=auth_token, add_to_git_credential=False)
                        logger.info("Zalogowano do HuggingFace Hub")
                    except Exception as login_error:
                        logger.warning(f"Nie udało się zalogować do HuggingFace Hub: {login_error}")
                
                # Pipeline.from_pretrained automatycznie użyje tokenu z zmiennej środowiskowej lub z logowania
                # Monkey-patch został już zastosowany na początku modułu
                self.pipeline = Pipeline.from_pretrained(
                    model_name,
                    cache_dir=str(pyannote_cache_dir)
                )
                logger.info(f"Pipeline zainicjalizowany pomyślnie. Modele zapisane w: {pyannote_cache_dir}")
            except Exception as e:
                logger.error(f"Nie udało się załadować modelu: {e}")
                if not auth_token:
                    logger.info(f"Aby pobrać model, uzyskaj token na: https://huggingface.co/{model_name}")
                return False
            
            # Przeniesienie na GPU jeśli dostępne
            if torch.cuda.is_available():
                self.pipeline = self.pipeline.to(torch.device("cuda"))
                logger.info("Rozpoznawanie mówców uruchomione na GPU")
            else:
                logger.info("Rozpoznawanie mówców uruchomione na CPU")
            
            self.initialized = True
            logger.info("Rozpoznawanie mówców zainicjalizowane pomyślnie")
            return True
            
        except Exception as e:
            logger.error(f"Błąd podczas inicjalizacji rozpoznawania mówców: {e}")
            return False
    
    def diarize_speakers(self, audio_file_path: Path) -> Optional[List[Dict]]:
        """Rozpoznawanie mówców w pliku audio za pomocą zaawansowanego algorytmu pyannote"""
        if not self.initialized or not self.pipeline:
            logger.warning("Rozpoznawanie mówców nie jest zainicjalizowane")
            return None
            
        try:
            logger.info(f"Rozpoznawanie mówców w pliku: {audio_file_path.name}")
            
            # Uruchomienie diarization
            with ProgressHook() as hook:
                diarization = self.pipeline(str(audio_file_path), hook=hook)
            
            # Konwersja wyników na format JSON
            speakers_data = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                speakers_data.append({
                    "speaker": speaker,
                    "start": turn.start,
                    "end": turn.end,
                    "duration": turn.end - turn.start
                })
            
            logger.info(f"Rozpoznano {len(set([s['speaker'] for s in speakers_data]))} mówców")
            return speakers_data
            
        except Exception as e:
            logger.error(f"Błąd podczas rozpoznawania mówców: {e}")
            return None

class AdvancedSpeakerDiarizer:
    """Zaawansowany algorytm rozpoznawania mówców na podstawie analizy segmentów Whisper"""
    
    def __init__(self):
        self.min_speaker_duration = 1.5  # Minimalny czas mówcy w sekundach
        self.pause_threshold = 1.2       # Próg pauzy w sekundach
        self.similarity_threshold = 0.7  # Próg podobieństwa segmentów
        self.max_speakers = 4            # Maksymalna liczba mówców
        
    def analyze_segment_characteristics(self, segments: List[Dict]) -> List[Dict]:
        """Analiza charakterystyki segmentów (długość, energia, tempo)"""
        analyzed_segments = []
        
        for i, segment in enumerate(segments):
            text = segment.get("text", "").strip()
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            duration = end - start
            
            # Charakterystyka segmentu
            characteristics = {
                "index": i,
                "start": start,
                "end": end,
                "duration": duration,
                "text": text,
                "word_count": len(text.split()),
                "words_per_second": len(text.split()) / duration if duration > 0 else 0,
                "has_question": "?" in text,
                "has_exclamation": "!" in text,
                "is_short": duration < 1.0,
                "is_long": duration > 5.0,
                "starts_with_greeting": self._is_greeting(text),
                "ends_with_goodbye": self._is_goodbye(text)
            }
            
            analyzed_segments.append(characteristics)
        
        return analyzed_segments
    
    def _is_greeting(self, text: str) -> bool:
        """Sprawdzenie czy tekst zaczyna się od powitania"""
        greetings = [
            "dzień dobry", "dobry", "cześć", "witam", "hej", "hello", "hi",
            "good morning", "good afternoon", "good evening"
        ]
        text_lower = text.lower().strip()
        return any(text_lower.startswith(greeting) for greeting in greetings)
    
    def _is_goodbye(self, text: str) -> bool:
        """Sprawdzenie czy tekst kończy się pożegnaniem"""
        goodbyes = [
            "do widzenia", "pa", "cześć", "nara", "goodbye", "bye", "see you",
            "dziękuję", "dzięki", "thank you", "thanks"
        ]
        text_lower = text.lower().strip()
        return any(text_lower.endswith(goodbye) for goodbye in goodbyes)
    
    def detect_speaker_changes(self, segments: List[Dict]) -> List[int]:
        """Wykrywanie zmian mówców na podstawie analizy segmentów"""
        if len(segments) < 2:
            return []
        
        change_points = []
        analyzed_segments = self.analyze_segment_characteristics(segments)
        
        for i in range(1, len(analyzed_segments)):
            prev_seg = analyzed_segments[i-1]
            curr_seg = analyzed_segments[i]
            
            # Obliczenie podobieństwa między segmentami
            similarity_score = self._calculate_segment_similarity(prev_seg, curr_seg)
            
            # Wykrywanie zmiany mówcy
            if self._should_change_speaker(prev_seg, curr_seg, similarity_score):
                change_points.append(i)
        
        return change_points
    
    def _calculate_segment_similarity(self, seg1: Dict, seg2: Dict) -> float:
        """Obliczenie podobieństwa między segmentami"""
        # Podobieństwo długości
        duration_similarity = 1.0 - abs(seg1["duration"] - seg2["duration"]) / max(seg1["duration"], seg2["duration"], 0.1)
        
        # Podobieństwo tempa mówienia
        wps_similarity = 1.0 - abs(seg1["words_per_second"] - seg2["words_per_second"]) / max(seg1["words_per_second"], seg2["words_per_second"], 0.1)
        
        # Podobieństwo długości tekstu
        length_similarity = 1.0 - abs(seg1["word_count"] - seg2["word_count"]) / max(seg1["word_count"], seg2["word_count"], 1)
        
        # Średnie podobieństwo
        return (duration_similarity + wps_similarity + length_similarity) / 3
    
    def _should_change_speaker(self, prev_seg: Dict, curr_seg: Dict, similarity: float) -> bool:
        """Decyzja o zmianie mówcy"""
        # Długie pauzy
        pause_duration = curr_seg["start"] - prev_seg["end"]
        if pause_duration > self.pause_threshold:
            return True
        
        # Niskie podobieństwo segmentów
        if similarity < self.similarity_threshold:
            return True
        
        # Różnice w charakterystyce
        if prev_seg["is_short"] != curr_seg["is_short"]:
            return True
        
        if prev_seg["has_question"] != curr_seg["has_question"]:
            return True
        
        # Powitania i pożegnania
        if curr_seg["starts_with_greeting"] or prev_seg["ends_with_goodbye"]:
            return True
        
        return False
    
    def assign_speakers(self, segments: List[Dict], change_points: List[int]) -> List[Dict]:
        """Przypisanie mówców do segmentów"""
        speakers_data = []
        current_speaker = "SPEAKER_00"
        speaker_counter = 0
        
        for i, segment in enumerate(segments):
            # Sprawdzenie czy to punkt zmiany mówcy
            if i in change_points:
                speaker_counter += 1
                current_speaker = f"SPEAKER_{speaker_counter:02d}"
                
                # Ograniczenie liczby mówców
                if speaker_counter >= self.max_speakers:
                    speaker_counter = 0
                    current_speaker = "SPEAKER_00"
            
            speakers_data.append({
                "speaker": current_speaker,
                "start": segment.get("start", 0),
                "end": segment.get("end", 0),
                "duration": segment.get("end", 0) - segment.get("start", 0)
            })
        
        return speakers_data
    
    def optimize_speaker_assignments(self, speakers_data: List[Dict]) -> List[Dict]:
        """Optymalizacja przypisań mówców - łączenie krótkich segmentów"""
        if not speakers_data:
            return speakers_data
        
        optimized = []
        current_group = [speakers_data[0]]
        
        for i in range(1, len(speakers_data)):
            current_seg = speakers_data[i]
            prev_seg = speakers_data[i-1]
            
            # Sprawdzenie czy można połączyć segmenty
            if (current_seg["speaker"] == prev_seg["speaker"] and 
                current_seg["start"] - prev_seg["end"] < 0.5 and  # Mała pauza
                current_seg["duration"] < self.min_speaker_duration):  # Krótki segment
                
                current_group.append(current_seg)
            else:
                # Zapisanie grupy i rozpoczęcie nowej
                if current_group:
                    optimized.extend(current_group)
                current_group = [current_seg]
        
        # Dodanie ostatniej grupy
        if current_group:
            optimized.extend(current_group)
        
        return optimized
    
    def diarize_speakers(self, segments: List[Dict]) -> List[Dict]:
        """Główna metoda rozpoznawania mówców"""
        if not segments:
            return []
        
        logger.info(f"Rozpoczęcie zaawansowanego rozpoznawania mówców dla {len(segments)} segmentów")
        
        # Wykrycie zmian mówców
        change_points = self.detect_speaker_changes(segments)
        logger.info(f"Wykryto {len(change_points)} punktów zmiany mówcy")
        
        # Przypisanie mówców
        speakers_data = self.assign_speakers(segments, change_points)
        
        # Optymalizacja przypisań
        optimized_speakers = self.optimize_speaker_assignments(speakers_data)
        
        # Statystyki
        unique_speakers = set(s["speaker"] for s in optimized_speakers)
        logger.info(f"Zaawansowane rozpoznawanie mówców: {len(unique_speakers)} mówców")
        
        # Logowanie statystyk
        speaker_stats = defaultdict(float)
        for speaker_info in optimized_speakers:
            speaker_stats[speaker_info["speaker"]] += speaker_info["duration"]
        
        for speaker, total_time in speaker_stats.items():
            logger.info(f"  {speaker}: {total_time:.1f}s ({total_time/60:.1f}min)")
        
        return optimized_speakers

class SimpleSpeakerDiarizer:
    """Prosty algorytm rozpoznawania mówców na podstawie segmentów Whisper (ulepszona wersja)"""
    
    @staticmethod
    def diarize_speakers(segments: List[Dict]) -> List[Dict]:
        """Rozpoznawanie mówców na podstawie analizy segmentów czasowych i pauz między wypowiedziami"""
        if not segments:
            return []
        
        # Użycie zaawansowanego algorytmu
        advanced_diarizer = AdvancedSpeakerDiarizer()
        return advanced_diarizer.diarize_speakers(segments)
    
    @staticmethod
    def diarize_speakers_legacy(segments: List[Dict]) -> List[Dict]:
        """Stary prosty algorytm (zachowany dla kompatybilności)"""
        if not segments:
            return []
        
        speakers_data = []
        current_speaker = "SPEAKER_00"
        
        for i, segment in enumerate(segments):
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            duration = end - start
            
            # Prosty algorytm: zmiana mówcy co 2-3 segmenty lub przy długich pauzach
            if i > 0:
                prev_end = segments[i-1].get("end", 0)
                pause_duration = start - prev_end
                
                # Zmiana mówcy przy długich pauzach (>2 sekundy) lub co 3 segmenty
                if pause_duration > 2.0 or i % 3 == 0:
                    if current_speaker == "SPEAKER_00":
                        current_speaker = "SPEAKER_01"
                    else:
                        current_speaker = "SPEAKER_00"
            
            speakers_data.append({
                "speaker": current_speaker,
                "start": start,
                "end": end,
                "duration": duration
            })
        
        logger.info(f"Proste rozpoznawanie mówców: {len(set([s['speaker'] for s in speakers_data]))} mówców")
        return speakers_data 
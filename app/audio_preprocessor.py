#!/usr/bin/env python3
"""
Moduł do wstępnego przetwarzania plików audio
==============================================

Zawiera funkcje do:
- Odszumiania audio (noise reduction)
- Normalizacji głośności
- Podbicia głośności (gain boost)
- Poprawy jakości audio (compression, EQ)
"""

import logging
from pathlib import Path
from typing import Optional
import numpy as np

try:
    from pydub import AudioSegment
    from pydub.effects import normalize, compress_dynamic_range, high_pass_filter, low_pass_filter
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    logging.warning("pydub nie jest dostępne. Podstawowe efekty audio będą niedostępne.")

try:
    import noisereduce as nr
    import librosa
    import soundfile as sf
    NOISE_REDUCE_AVAILABLE = True
except ImportError:
    NOISE_REDUCE_AVAILABLE = False
    logging.warning("noisereduce/librosa nie jest dostępne. Odszumianie będzie wyłączone.")

from .config import (
    AUDIO_PREPROCESS_ENABLED,
    AUDIO_PREPROCESS_NOISE_REDUCE,
    AUDIO_PREPROCESS_NOISE_STRENGTH,
    AUDIO_PREPROCESS_NORMALIZE,
    AUDIO_PREPROCESS_GAIN_DB,
    AUDIO_PREPROCESS_COMPRESSOR,
    AUDIO_PREPROCESS_COMP_THRESHOLD,
    AUDIO_PREPROCESS_COMP_RATIO,
    AUDIO_PREPROCESS_SPEAKER_LEVELING,
    AUDIO_PREPROCESS_EQ,
    AUDIO_PREPROCESS_HIGHPASS,
)

logger = logging.getLogger(__name__)


class AudioPreprocessor:
    """Klasa do wstępnego przetwarzania plików audio przed transkrypcją"""
    
    def __init__(
        self,
        enabled: bool = True,
        noise_reduce: bool = True,
        noise_strength: float = 0.75,
        normalize: bool = True,
        gain_db: float = 3.0,
        compressor: bool = True,
        comp_threshold: float = -20.0,
        comp_ratio: float = 4.0,
        speaker_leveling: bool = True,
        eq: bool = True,
        highpass: int = 100,
    ):
        self.enabled = enabled and PYDUB_AVAILABLE
        self.noise_reduce = noise_reduce and NOISE_REDUCE_AVAILABLE
        self.noise_strength = max(0.0, min(1.0, noise_strength))
        self.normalize = normalize
        self.gain_db = gain_db
        self.compressor = compressor
        self.comp_threshold = comp_threshold
        self.comp_ratio = max(1.0, comp_ratio)
        self.speaker_leveling = speaker_leveling
        self.eq = eq
        self.highpass = max(50, min(300, highpass))
        
        if not PYDUB_AVAILABLE:
            logger.warning("AudioPreprocessor: pydub nie jest dostępne. Preprocessing wyłączony.")
        elif not self.enabled:
            logger.info("AudioPreprocessor: preprocessing wyłączony przez konfigurację")
        else:
            logger.info(f"AudioPreprocessor zainicjalizowany (noise={self.noise_reduce}/{self.noise_strength:.0%}, normalize={self.normalize}, gain={self.gain_db}dB, comp={self.compressor}/{self.comp_threshold}dB/{self.comp_ratio}:1, leveling={self.speaker_leveling})")
    
    def process(self, input_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Przetwarza plik audio z zastosowaniem wszystkich włączonych funkcji.
        
        Args:
            input_path: Ścieżka do pliku wejściowego
            output_path: Ścieżka do pliku wyjściowego (jeśli None, tworzy automatycznie)
        
        Returns:
            Ścieżka do przetworzonego pliku lub None w przypadku błędu
        """
        input_path = Path(input_path)
        
        if not self.enabled:
            logger.debug("AudioPreprocessor: preprocessing wyłączony, zwracam oryginalny plik")
            return input_path
        
        if not PYDUB_AVAILABLE:
            logger.warning("AudioPreprocessor: pydub nie jest dostępne, zwracam oryginalny plik")
            return input_path
        
        try:
            logger.info(f"Rozpoczęcie preprocessing audio: {input_path.name}")
            
            # Określenie pliku wyjściowego
            if output_path is None:
                output_path = self._generate_output_path(input_path)
            else:
                output_path = Path(output_path)
            
            # Wczytanie audio przez pydub
            audio = AudioSegment.from_file(str(input_path))
            original_dbfs = audio.dBFS
            
            logger.debug(f"Wczytano audio: {len(audio)}ms, {audio.frame_rate}Hz, {audio.channels} kanałów, {original_dbfs:.1f}dBFS")
            
            # 1. High-pass filter (EQ - usunięcie niskich częstotliwości) - NAJPIERW
            if self.eq:
                logger.info(f"Stosowanie EQ (high-pass {self.highpass}Hz, low-pass 8000Hz)...")
                audio = high_pass_filter(audio, cutoff=self.highpass)
                if audio.frame_rate > 16000:
                    audio = low_pass_filter(audio, cutoff=8000)
            
            # 2. Odszumianie (używa noisereduce przez numpy)
            if self.noise_reduce and NOISE_REDUCE_AVAILABLE:
                logger.info(f"Stosowanie odszumiania (siła: {self.noise_strength:.0%})...")
                audio = self._apply_noise_reduction(audio)
            
            # 3. Wyrównywanie głośności mówców (PRZED kompresorem)
            if self.speaker_leveling:
                logger.info("Wyrównywanie głośności mówców...")
                audio = self._apply_speaker_leveling(audio)
            
            # 4. Kompresor dynamiki
            if self.compressor:
                logger.info(f"Stosowanie kompresora (próg: {self.comp_threshold}dB, ratio: {self.comp_ratio}:1)...")
                audio = compress_dynamic_range(
                    audio,
                    threshold=self.comp_threshold,
                    ratio=self.comp_ratio,
                    attack=5.0,
                    release=50.0
                )
            
            # 5. Normalizacja głośności
            if self.normalize:
                logger.info("Stosowanie normalizacji...")
                audio = normalize(audio, headroom=0.5)  # Normalizuj do -0.5dBFS
            
            # 6. Podbicie głośności (gain) - NA KOŃCU
            if self.gain_db != 0:
                logger.info(f"Stosowanie gain: {self.gain_db}dB...")
                audio = audio + self.gain_db
            
            # Zapisanie przetworzonego pliku
            audio.export(str(output_path), format="wav")
            
            final_dbfs = audio.dBFS
            logger.info(f"Preprocessing zakończony: {output_path.name} (głośność: {original_dbfs:.1f}dB -> {final_dbfs:.1f}dB)")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Błąd podczas preprocessing audio {input_path.name}: {e}", exc_info=True)
            return input_path  # Zwróć oryginalny plik w przypadku błędu
    
    def _apply_noise_reduction(self, audio: AudioSegment) -> AudioSegment:
        """Stosuje odszumianie używając biblioteki noisereduce"""
        try:
            # Konwersja do numpy
            samples = np.array(audio.get_array_of_samples())
            
            # Konwersja do float
            if audio.sample_width == 2:
                samples = samples.astype(np.float32) / 32768.0
            elif audio.sample_width == 1:
                samples = (samples.astype(np.float32) - 128) / 128.0
            else:
                samples = samples.astype(np.float32)
            
            # Jeśli stereo, weź średnią
            if audio.channels == 2:
                samples = samples.reshape((-1, 2)).mean(axis=1)
            
            # Zastosuj noise reduction z konfigurowalna siłą
            reduced = nr.reduce_noise(
                y=samples,
                sr=audio.frame_rate,
                stationary=True,
                prop_decrease=self.noise_strength,  # Konfigurowalna siła redukcji
                time_constant_s=0.02,
                freq_mask_smooth_hz=500
            )
            
            # Konwersja z powrotem do int16
            reduced = np.clip(reduced * 32768, -32768, 32767).astype(np.int16)
            
            # Tworzenie nowego AudioSegment
            return AudioSegment(
                data=reduced.tobytes(),
                sample_width=2,
                frame_rate=audio.frame_rate,
                channels=1
            )
            
        except Exception as e:
            logger.warning(f"Błąd podczas odszumiania: {e}, kontynuuję bez odszumiania")
            return audio
    
    def _apply_speaker_leveling(self, audio: AudioSegment) -> AudioSegment:
        """
        Wyrównuje głośność różnych fragmentów audio (mówców).
        Dzieli audio na segmenty i normalizuje każdy z nich, 
        następnie składa z powrotem z płynnymi przejściami.
        """
        try:
            # Podziel audio na segmenty po 2 sekundy
            segment_length_ms = 2000
            segments = []
            
            for i in range(0, len(audio), segment_length_ms):
                segment = audio[i:i + segment_length_ms]
                if len(segment) > 100:  # Minimalny segment
                    # Sprawdź głośność segmentu
                    if segment.dBFS > -50:  # Nie jest ciszą
                        # Normalizuj do docelowej głośności
                        target_dbfs = -18.0  # Docelowa głośność
                        change = target_dbfs - segment.dBFS
                        # Ogranicz zmianę do ±15dB aby uniknąć artefaktów
                        change = max(-15, min(15, change))
                        segment = segment + change
                    segments.append(segment)
                else:
                    segments.append(segment)
            
            if not segments:
                return audio
            
            # Złóż segmenty z crossfade dla płynnych przejść
            result = segments[0]
            crossfade_ms = min(50, segment_length_ms // 4)
            
            for segment in segments[1:]:
                if len(segment) > crossfade_ms and len(result) > crossfade_ms:
                    result = result.append(segment, crossfade=crossfade_ms)
                else:
                    result = result + segment
            
            logger.debug(f"Speaker leveling: {len(segments)} segmentów przetworzonych")
            return result
            
        except Exception as e:
            logger.warning(f"Błąd podczas wyrównywania głośności: {e}, kontynuuję bez zmian")
            return audio
    
    def _generate_output_path(self, input_path: Path) -> Path:
        """Generuje ścieżkę do pliku wyjściowego z dopiskiem '_processed'"""
        return input_path.parent / f"{input_path.stem}_processed.wav"


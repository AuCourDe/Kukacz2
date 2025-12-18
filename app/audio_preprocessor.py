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
from typing import Optional, Tuple
import numpy as np

try:
    import librosa
    import soundfile as sf
    AUDIO_LIBS_AVAILABLE = True
except ImportError:
    AUDIO_LIBS_AVAILABLE = False
    logging.warning("Niektóre biblioteki audio nie są dostępne. Preprocessing audio będzie wyłączony.")

try:
    import noisereduce as nr
    NOISE_REDUCE_AVAILABLE = True
except ImportError:
    NOISE_REDUCE_AVAILABLE = False
    logging.warning("noisereduce nie jest dostępne. Odszumianie będzie wyłączone.")

from .config import (
    AUDIO_PREPROCESS_ENABLED,
    AUDIO_PREPROCESS_NOISE_REDUCE,
    AUDIO_PREPROCESS_NORMALIZE,
    AUDIO_PREPROCESS_GAIN_DB,
    AUDIO_PREPROCESS_COMPRESSOR,
    AUDIO_PREPROCESS_EQ,
)

logger = logging.getLogger(__name__)


class AudioPreprocessor:
    """Klasa do wstępnego przetwarzania plików audio przed transkrypcją"""
    
    def __init__(
        self,
        enabled: bool = True,
        noise_reduce: bool = True,
        normalize: bool = True,
        gain_db: float = 3.0,
        compressor: bool = True,
        eq: bool = True,
    ):
        self.enabled = enabled and AUDIO_LIBS_AVAILABLE
        self.noise_reduce = noise_reduce and NOISE_REDUCE_AVAILABLE
        self.normalize = normalize
        self.gain_db = gain_db
        self.compressor = compressor
        self.eq = eq
        
        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("AudioPreprocessor: biblioteki audio nie są dostępne. Preprocessing wyłączony.")
        elif not self.enabled:
            logger.info("AudioPreprocessor: preprocessing wyłączony przez konfigurację")
        else:
            logger.info(f"AudioPreprocessor zainicjalizowany (noise_reduce={self.noise_reduce}, normalize={self.normalize}, gain={self.gain_db}dB)")
    
    def process(self, input_path: Path, output_path: Optional[Path] = None) -> Optional[Path]:
        """
        Przetwarza plik audio z zastosowaniem wszystkich włączonych funkcji.
        
        Args:
            input_path: Ścieżka do pliku wejściowego
            output_path: Ścieżka do pliku wyjściowego (jeśli None, tworzy automatycznie)
        
        Returns:
            Ścieżka do przetworzonego pliku lub None w przypadku błędu
        """
        if not self.enabled:
            logger.debug("AudioPreprocessor: preprocessing wyłączony, zwracam oryginalny plik")
            return input_path
        
        if not AUDIO_LIBS_AVAILABLE:
            logger.warning("AudioPreprocessor: biblioteki nie są dostępne, zwracam oryginalny plik")
            return input_path
        
        try:
            logger.info(f"Rozpoczęcie preprocessing audio: {input_path.name}")
            
            # Określenie pliku wyjściowego
            if output_path is None:
                output_path = self._generate_output_path(input_path)
            
            # Wczytanie audio
            y, sr = librosa.load(str(input_path), sr=None, mono=True)
            original_length = len(y)
            
            logger.debug(f"Wczytano audio: {original_length} próbek, {sr}Hz")
            
            # Zastosowanie wszystkich włączonych funkcji
            processed = y.copy()
            
            # 1. Odszumianie (delikatniejsze parametry dla lepszej jakości mowy)
            if self.noise_reduce:
                logger.debug("Stosowanie odszumiania...")
                try:
                    # Optymalne parametry dla transkrypcji mowy:
                    # - prop_decrease=0.5: delikatniejsza redukcja (0.8 domyślnie)
                    # - stationary=True: dla większości nagrań call center
                    # - time_constant_s=0.01: szybsza adaptacja
                    processed = nr.reduce_noise(
                        y=processed, 
                        sr=sr,
                        stationary=True,
                        prop_decrease=0.5,  # Delikatniejsza redukcja (domyślnie 0.8)
                        time_constant_s=0.01,  # Szybsza adaptacja
                        freq_mask_smooth_hz=500  # Wygładzenie maski
                    )
                except Exception as e:
                    logger.warning(f"Błąd podczas odszumiania: {e}, kontynuuję bez odszumiania")
                    # Kontynuuj bez odszumiania w przypadku błędu
            
            # 2. Normalizacja głośności
            if self.normalize:
                logger.debug("Stosowanie normalizacji...")
                # Normalizacja do zakresu [-1, 1] z zachowaniem proporcji
                max_val = np.abs(processed).max()
                if max_val > 0:
                    processed = processed / max_val * 0.95  # 0.95 aby uniknąć clippingu
            
            # 3. Podbicie głośności (gain) - mniejsze wzmocnienie dla lepszej jakości
            if self.gain_db != 0:
                logger.debug(f"Stosowanie gain: {self.gain_db}dB...")
                gain_linear = 10 ** (self.gain_db / 20)
                processed = processed * gain_linear
                # Obcięcie do zakresu [-1, 1] - delikatne clipping
                processed = np.clip(processed, -0.98, 0.98)  # Zostawiamy margines
            
            # 4. Kompresor (dynamic range compression)
            if self.compressor:
                logger.debug("Stosowanie kompresora...")
                processed = self._apply_compressor(processed, sr)
            
            # 5. EQ (equalizer) - wzmocnienie średnich częstotliwości (mowa)
            if self.eq:
                logger.debug("Stosowanie EQ...")
                processed = self._apply_eq(processed, sr)
            
            # Ostateczna normalizacja po wszystkich operacjach
            max_val = np.abs(processed).max()
            if max_val > 0:
                processed = processed / max_val * 0.95
            
            # Zapisanie przetworzonego pliku
            sf.write(str(output_path), processed, sr)
            
            logger.info(f"Preprocessing zakończony: {output_path.name}")
            logger.debug(f"Długość audio: {original_length} -> {len(processed)} próbek")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Błąd podczas preprocessing audio {input_path.name}: {e}", exc_info=True)
            return input_path  # Zwróć oryginalny plik w przypadku błędu
    
    def _generate_output_path(self, input_path: Path) -> Path:
        """Generuje ścieżkę do pliku wyjściowego z dopiskiem '_processed'"""
        return input_path.parent / f"{input_path.stem}_processed{input_path.suffix}"
    
    def _apply_compressor(self, audio: np.ndarray, sr: int, ratio: float = 2.0, threshold: float = 0.8, attack: float = 0.005, release: float = 0.1) -> np.ndarray:
        """
        Stosuje kompresor dynamiki do audio.
        
        Args:
            audio: Sygnał audio
            sr: Sample rate
            ratio: Współczynnik kompresji (4.0 = 4:1)
            threshold: Próg kompresji (0-1)
            attack: Czas ataku w sekundach
            release: Czas zwolnienia w sekundach
        """
        try:
            # Prostý kompresor implementacja
            threshold_linear = threshold
            ratio_inv = 1.0 / ratio
            
            # Envelope follower (RMS)
            frame_length = int(sr * 0.01)  # 10ms frames
            if frame_length < 1:
                frame_length = 1
            
            envelope = np.zeros_like(audio)
            for i in range(0, len(audio), frame_length):
                end = min(i + frame_length, len(audio))
                rms = np.sqrt(np.mean(audio[i:end] ** 2))
                envelope[i:end] = rms
            
            # Compression gain
            gain = np.ones_like(audio)
            over_threshold = envelope > threshold_linear
            
            # Dla sygnałów powyżej progu, zastosuj kompresję
            excess = envelope - threshold_linear
            compressed_excess = excess * ratio_inv
            target_level = threshold_linear + compressed_excess
            
            gain[over_threshold] = np.where(
                envelope[over_threshold] > 0,
                target_level[over_threshold] / envelope[over_threshold],
                1.0
            )
            
            # Smoothing (attack/release)
            smoothed_gain = self._smooth_envelope(gain, sr, attack, release)
            
            return audio * smoothed_gain
            
        except Exception as e:
            logger.warning(f"Błąd podczas kompresji: {e}, zwracam oryginalny audio")
            return audio
    
    def _apply_eq(self, audio: np.ndarray, sr: int) -> np.ndarray:
        """
        Stosuje EQ wzmacniający zakres częstotliwości mowy (szerszy zakres dla lepszej jakości).
        
        Args:
            audio: Sygnał audio
            sr: Sample rate
        """
        try:
            # Szerszy zakres częstotliwości mowy dla lepszej jakości:
            # 80-8000Hz zamiast 300-3400Hz (telefon) - zachowuje więcej informacji
            nyquist = sr / 2
            
            # Filtry IIR (Butterworth) - delikatniejsze
            from scipy import signal
            
            # High-pass filter (80Hz) - usunięcie bardzo niskich częstotliwości (szum)
            # Zamiast 300Hz dla zachowania naturalności głosu
            if nyquist > 80:
                sos_high = signal.butter(2, 80 / nyquist, btype='high', output='sos')
                audio = signal.sosfilt(sos_high, audio)
            
            # Low-pass filter (8000Hz) - zachowanie wysokich częstotliwości dla klarowności
            # Zamiast 3400Hz dla lepszej jakości mowy
            if nyquist > 8000:
                sos_low = signal.butter(2, 8000 / nyquist, btype='low', output='sos')
                audio = signal.sosfilt(sos_low, audio)
            
            # Delikatniejsze wzmocnienie (1dB zamiast 2dB) - mniej artefaktów
            audio = audio * (10 ** (1.0 / 20))
            
            return audio
            
        except ImportError:
            logger.warning("scipy nie jest dostępne, pomijam EQ")
            return audio
        except Exception as e:
            logger.warning(f"Błąd podczas EQ: {e}, zwracam oryginalny audio")
            return audio
    
    def _smooth_envelope(self, envelope: np.ndarray, sr: int, attack: float, release: float) -> np.ndarray:
        """Wygładza envelope z czasami attack i release"""
        smoothed = np.zeros_like(envelope)
        smoothed[0] = envelope[0]
        
        attack_coeff = np.exp(-1.0 / (attack * sr))
        release_coeff = np.exp(-1.0 / (release * sr))
        
        for i in range(1, len(envelope)):
            if envelope[i] > smoothed[i-1]:
                # Attack
                smoothed[i] = envelope[i] + (smoothed[i-1] - envelope[i]) * attack_coeff
            else:
                # Release
                smoothed[i] = envelope[i] + (smoothed[i-1] - envelope[i]) * release_coeff
        
        return smoothed


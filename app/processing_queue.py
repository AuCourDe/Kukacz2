#!/usr/bin/env python3
"""
Kolejka przetwarzania plików audio dla interfejsu webowego.
"""
from __future__ import annotations

import logging
import math
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _get_audio_duration_seconds(file_path: Path) -> float:
    """Pobiera długość nagrania audio w sekundach."""
    try:
        import librosa
        duration = librosa.get_duration(path=str(file_path))
        return duration
    except Exception as e:
        logger.warning(f"Nie udało się odczytać długości audio {file_path}: {e}")
        # Fallback: szacowanie na podstawie rozmiaru (przybliżenie 1MB/min dla MP3)
        size_mb = file_path.stat().st_size / (1024 * 1024)
        return max(60.0, size_mb * 60)  # minimum 1 minuta


def _estimate_minutes(file_path: Path) -> int:
    """Szacuje czas przetwarzania – 1 minuta nagrania = 1 minuta przetwarzania."""
    try:
        duration_seconds = _get_audio_duration_seconds(file_path)
        minutes = math.ceil(duration_seconds / 60.0)
        return max(1, minutes)
    except Exception as e:
        logger.warning(f"Błąd podczas szacowania czasu dla {file_path}: {e}")
        # Fallback: 1 minuta minimum
        return 1


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class QueueItem:
    """Reprezentuje pojedyncze zadanie w kolejce przetwarzania."""

    id: str
    filename: str
    size_bytes: int
    input_path: Path
    status: str = "queued"
    created_at: datetime = field(default_factory=_utcnow)
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    error: Optional[str] = None
    estimated_minutes: int = 1
    result_files: Dict[str, str] = field(default_factory=dict)

    def _format_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        """Formatuje datę do formatu ISO 8601 z timezone (dla JavaScript)."""
        if dt is None:
            return None
        # Upewnij się że mamy timezone UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Zwróć w formacie ISO 8601 - JavaScript poprawnie parsuje ten format
        return dt.isoformat()
    
    def _format_datetime_human(self, dt: Optional[datetime]) -> Optional[str]:
        """Formatuje datę do czytelnego formatu z dokładnością do sekundy."""
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        # Format: YYYY-MM-DD HH:MM:SS
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    def _calculate_processing_time(self) -> Optional[str]:
        """Oblicza faktyczny czas przetwarzania w formacie mm:ss."""
        if not self.started_at or not self.finished_at:
            return None
        delta = self.finished_at - self.started_at
        total_seconds = int(delta.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        # Format: mm:ss
        return f"{minutes:02d}:{seconds:02d}"
    
    def to_dict(self) -> Dict:
        size_mb = self.size_bytes / (1024 * 1024) if self.size_bytes else 0.0
        return {
            "id": self.id,
            "filename": self.filename,
            "size_mb": round(size_mb, 2),
            "status": self.status,
            "created_at": self._format_datetime(self.created_at),
            "created_at_formatted": self._format_datetime_human(self.created_at),
            "started_at": self._format_datetime(self.started_at),
            "finished_at": self._format_datetime(self.finished_at),
            "estimated_minutes": self.estimated_minutes,
            "processing_time": self._calculate_processing_time(),
            "error": self.error,
            "result_files": self.result_files,
        }


class ProcessingQueue:
    """Prosta, jawna kolejka przetwarzania widoczna w interfejsie webowym."""

    def __init__(self) -> None:
        self._items: Dict[str, QueueItem] = {}
        self._order: List[str] = []
        self._lock = threading.Lock()

    def enqueue(self, file_path: Path) -> QueueItem:
        """Dodaje nowy plik do kolejki."""
        size = file_path.stat().st_size if file_path.exists() else 0
        item = QueueItem(
            id=str(uuid.uuid4()),
            filename=file_path.name,
            size_bytes=size,
            input_path=file_path,
            estimated_minutes=_estimate_minutes(file_path),
        )
        with self._lock:
            self._items[item.id] = item
            self._order.append(item.id)
        return item

    def get_item(self, item_id: str) -> Optional[QueueItem]:
        with self._lock:
            return self._items.get(item_id)

    def mark_processing(self, item_id: str) -> None:
        with self._lock:
            item = self._items.get(item_id)
            if item:
                item.status = "processing"
                item.started_at = _utcnow()
                item.error = None

    def mark_completed(self, item_id: str, result_files: Dict[str, str]) -> None:
        with self._lock:
            item = self._items.get(item_id)
            if item:
                item.status = "completed"
                item.finished_at = _utcnow()
                item.result_files = result_files
                item.error = None

    def mark_failed(self, item_id: str, error_message: str) -> None:
        with self._lock:
            item = self._items.get(item_id)
            if item:
                item.status = "failed"
                item.finished_at = _utcnow()
                item.error = error_message

    def serialize(self) -> List[Dict]:
        with self._lock:
            return [self._items[item_id].to_dict() for item_id in self._order]

    def get_result_file(self, item_id: str, file_type: str) -> Optional[str]:
        with self._lock:
            item = self._items.get(item_id)
            if not item:
                return None
            return item.result_files.get(file_type)


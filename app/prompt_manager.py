#!/usr/bin/env python3
"""
Moduł do zarządzania promptami analizy
======================================

Zawiera funkcje do:
- Wykrywania i ładowania promptów (prompt01.txt - prompt99.txt)
- Tworzenia, edycji i usuwania promptów
- Walidacji nazw i zawartości promptów
"""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .config import PROMPT_DIR

logger = logging.getLogger(__name__)

# Wzorzec nazwy pliku promptu: promptXX.txt gdzie XX to 01-99
PROMPT_FILENAME_PATTERN = re.compile(r"^prompt(\d{2})\.txt$")


class PromptManager:
    """Zarządzanie plikami promptów dla analizy Ollama"""

    def __init__(self, prompt_dir: Optional[Path] = None):
        self.prompt_dir = Path(prompt_dir) if prompt_dir else PROMPT_DIR
        self.prompt_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"PromptManager zainicjalizowany - katalog: {self.prompt_dir}")

    def get_prompt_files(self) -> List[Tuple[int, Path]]:
        """
        Pobiera listę plików promptów posortowaną według numeru.
        
        Returns:
            Lista krotek (numer, ścieżka) dla plików promptXX.txt
        """
        prompt_files = []
        
        for file_path in self.prompt_dir.iterdir():
            if file_path.is_file():
                match = PROMPT_FILENAME_PATTERN.match(file_path.name)
                if match:
                    prompt_num = int(match.group(1))
                    if 1 <= prompt_num <= 99:
                        prompt_files.append((prompt_num, file_path))
        
        # Sortowanie według numeru
        prompt_files.sort(key=lambda x: x[0])
        
        logger.info(f"Znaleziono {len(prompt_files)} plików promptów")
        return prompt_files

    def get_prompts_content(self) -> List[Dict[str, any]]:
        """
        Pobiera zawartość wszystkich promptów w kolejności.
        
        Returns:
            Lista słowników z informacjami o promptach:
            [{"number": 1, "filename": "prompt01.txt", "content": "...", "path": Path}]
        """
        prompts = []
        
        for prompt_num, file_path in self.get_prompt_files():
            try:
                content = file_path.read_text(encoding="utf-8")
                prompts.append({
                    "number": prompt_num,
                    "filename": file_path.name,
                    "content": content,
                    "path": file_path,
                })
            except Exception as e:
                logger.error(f"Błąd odczytu promptu {file_path.name}: {e}")
        
        return prompts

    def get_prompt_count(self) -> int:
        """Zwraca liczbę wykrytych promptów"""
        return len(self.get_prompt_files())

    def load_prompt(self, prompt_number: int) -> Optional[str]:
        """
        Ładuje zawartość pojedynczego promptu.
        
        Args:
            prompt_number: Numer promptu (1-99)
            
        Returns:
            Zawartość promptu lub None jeśli nie istnieje
        """
        if not 1 <= prompt_number <= 99:
            logger.warning(f"Nieprawidłowy numer promptu: {prompt_number}")
            return None
        
        filename = f"prompt{prompt_number:02d}.txt"
        file_path = self.prompt_dir / filename
        
        if not file_path.exists():
            logger.warning(f"Prompt {filename} nie istnieje")
            return None
        
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Błąd odczytu promptu {filename}: {e}")
            return None

    def save_prompt(self, prompt_number: int, content: str) -> bool:
        """
        Zapisuje zawartość promptu.
        
        Args:
            prompt_number: Numer promptu (1-99)
            content: Zawartość promptu
            
        Returns:
            True jeśli zapis się powiódł
        """
        if not 1 <= prompt_number <= 99:
            logger.error(f"Nieprawidłowy numer promptu: {prompt_number}")
            return False
        
        filename = f"prompt{prompt_number:02d}.txt"
        file_path = self.prompt_dir / filename
        
        try:
            file_path.write_text(content, encoding="utf-8")
            logger.info(f"Zapisano prompt: {filename}")
            return True
        except Exception as e:
            logger.error(f"Błąd zapisu promptu {filename}: {e}")
            return False

    def delete_prompt(self, prompt_number: int) -> bool:
        """
        Usuwa plik promptu.
        
        Args:
            prompt_number: Numer promptu (1-99)
            
        Returns:
            True jeśli usunięcie się powiodło
        """
        if not 1 <= prompt_number <= 99:
            logger.error(f"Nieprawidłowy numer promptu: {prompt_number}")
            return False
        
        filename = f"prompt{prompt_number:02d}.txt"
        file_path = self.prompt_dir / filename
        
        if not file_path.exists():
            logger.warning(f"Prompt {filename} nie istnieje")
            return False
        
        try:
            file_path.unlink()
            logger.info(f"Usunięto prompt: {filename}")
            return True
        except Exception as e:
            logger.error(f"Błąd usuwania promptu {filename}: {e}")
            return False

    def get_next_available_number(self) -> Optional[int]:
        """
        Zwraca następny dostępny numer promptu.
        
        Returns:
            Numer (1-99) lub None jeśli wszystkie zajęte
        """
        existing_numbers = {num for num, _ in self.get_prompt_files()}
        
        for i in range(1, 100):
            if i not in existing_numbers:
                return i
        
        return None

    def create_new_prompt(self, content: str) -> Optional[int]:
        """
        Tworzy nowy prompt z następnym dostępnym numerem.
        
        Args:
            content: Zawartość nowego promptu
            
        Returns:
            Numer utworzonego promptu lub None w przypadku błędu
        """
        next_num = self.get_next_available_number()
        
        if next_num is None:
            logger.error("Brak dostępnych numerów promptów (limit 99)")
            return None
        
        if self.save_prompt(next_num, content):
            return next_num
        
        return None

    def validate_prompt_content(self, content: str) -> Tuple[bool, str]:
        """
        Waliduje zawartość promptu.
        
        Args:
            content: Zawartość do walidacji
            
        Returns:
            Krotka (czy_poprawny, komunikat)
        """
        if not content or not content.strip():
            return False, "Zawartość promptu nie może być pusta"
        
        if len(content) > 50000:
            return False, "Zawartość promptu przekracza limit 50000 znaków"
        
        # Sprawdzenie czy zawiera placeholder {text}
        if "{text}" not in content:
            return False, "Prompt musi zawierać placeholder {text} dla transkrypcji"
        
        return True, "Prompt jest poprawny"


# Singleton dla łatwego dostępu
_prompt_manager_instance: Optional[PromptManager] = None


def get_prompt_manager() -> PromptManager:
    """Zwraca singleton PromptManager"""
    global _prompt_manager_instance
    if _prompt_manager_instance is None:
        _prompt_manager_instance = PromptManager()
    return _prompt_manager_instance


__all__ = ["PromptManager", "get_prompt_manager", "PROMPT_FILENAME_PATTERN"]

#!/usr/bin/env python3
"""
Moduł do obsługi kolorowanych logów
===================================

Dostarcza formatowany handler do logowania z kolorami ANSI:
- Sukces (zielony): pomyślne zakończenie operacji
- Ostrzeżenia (pomarańczowy): istotne uwagi
- Błędy (czerwony): błędy i krytyczne problemy
- Informacje (bez koloru): standardowe komunikaty
"""

import logging
import sys


class ColoredFormatter(logging.Formatter):
    """Formatter z obsługą kolorów ANSI dla różnych poziomów logowania"""
    
    # Kolory ANSI
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '',               # Brak koloru
        'SUCCESS': '\033[32m',    # Zielony
        'WARNING': '\033[33m',    # Pomarańczowy/żółty
        'ERROR': '\033[31m',      # Czerwony
        'CRITICAL': '\033[31;1m', # Jasny czerwony (bold)
    }
    RESET = '\033[0m'
    
    def format(self, record):
        """Formatowanie rekordu z kolorami"""
        # Sprawdź czy stdout obsługuje kolory (terminal)
        use_colors = sys.stdout.isatty()
        
        # Pobierz oryginalny format
        log_message = super().format(record)
        
        if use_colors:
            levelname = record.levelname
            color = self.COLORS.get(levelname, '')
            if color:
                log_message = f"{color}{log_message}{self.RESET}"
        
        return log_message


class ColoredFileFormatter(logging.Formatter):
    """Formatter bez kolorów dla plików (tylko tekst)"""
    
    def format(self, record):
        """Formatowanie rekordu bez kolorów"""
        return super().format(record)


def setup_colored_logging(
    level: str = "INFO",
    log_file: str = None,
    enable_colors: bool = True
) -> logging.Logger:
    """
    Konfiguracja logowania z obsługą kolorów
    
    Args:
        level: Poziom logowania (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Ścieżka do pliku logów (opcjonalnie)
        enable_colors: Czy włączyć kolory w terminalu
        
    Returns:
        Logger skonfigurowany z kolorami
    """
    # Dodanie poziomu SUCCESS
    SUCCESS_LEVEL = 25
    logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")
    
    def success(self, message, *args, **kwargs):
        """Metoda logowania na poziomie SUCCESS"""
        if self.isEnabledFor(SUCCESS_LEVEL):
            self._log(SUCCESS_LEVEL, message, args, **kwargs)
    
    logging.Logger.success = success
    
    # Konfiguracja loggera głównego
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # Usunięcie istniejących handlerów
    logger.handlers.clear()
    
    # Handler dla konsoli z kolorami
    console_handler = logging.StreamHandler(sys.stdout)
    if enable_colors and sys.stdout.isatty():
        console_formatter = ColoredFormatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    else:
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # Handler dla pliku bez kolorów
    if log_file:
        from pathlib import Path
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(str(log_path))
        file_formatter = ColoredFileFormatter(
            '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger


def print_colored(message: str, color: str = "INFO", file=sys.stdout) -> None:
    """
    Wyświetlanie kolorowanego komunikatu
    
    Args:
        message: Tekst do wyświetlenia
        color: Kolor (SUCCESS, WARNING, ERROR, INFO)
        file: Plik wyjściowy (domyślnie stdout)
    """
    colors = {
        'SUCCESS': '\033[32m',
        'WARNING': '\033[33m',
        'ERROR': '\033[31m',
        'CRITICAL': '\033[31;1m',
        'INFO': ''
    }
    reset = '\033[0m'
    
    use_colors = file.isatty() if hasattr(file, 'isatty') else False
    color_code = colors.get(color, '')
    
    if use_colors and color_code:
        print(f"{color_code}{message}{reset}", file=file, flush=True)
    else:
        print(message, file=file, flush=True)


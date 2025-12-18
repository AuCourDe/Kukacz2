#!/usr/bin/env python3
"""
Moduł do filtrowania rozumowania modeli Ollama
==============================================

Zawiera funkcje do:
- Wykrywania tagów rozumowania w odpowiedziach modeli
- Filtrowania rozumowania z tekstu
- Konfiguracji tagów rozumowania
- Zapisywania lub pomijania rozumowania
"""

import re
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Union
from .config import SAVE_REASONING, REASONING_TAGS

logger = logging.getLogger(__name__)

class ReasoningFilter:
    """Filtrowanie rozumowania modeli z odpowiedzi Ollama"""
    
    def __init__(self, save_reasoning: bool = SAVE_REASONING, 
                 reasoning_tags: List[str] = REASONING_TAGS):
        self.save_reasoning = save_reasoning
        self.reasoning_tags = reasoning_tags
        self.reasoning_patterns = self._build_reasoning_patterns()
        logger.info(f"ReasoningFilter zainicjalizowany - zapisywanie rozumowania: {save_reasoning}")
    
    def _build_reasoning_patterns(self) -> List[Tuple[str, str]]:
        """Budowanie wzorców regex dla tagów rozumowania"""
        patterns = []
        for i in range(0, len(self.reasoning_tags), 2):
            if i + 1 < len(self.reasoning_tags):
                start_tag = re.escape(self.reasoning_tags[i])
                end_tag = re.escape(self.reasoning_tags[i + 1])
                pattern = (start_tag, end_tag)
                patterns.append(pattern)
        return patterns
    
    def detect_reasoning_sections(self, text: str) -> List[Dict[str, str]]:
        """Wykrywanie sekcji rozumowania w tekście"""
        reasoning_sections = []
        
        for start_pattern, end_pattern in self.reasoning_patterns:
            # Wzorzec do znajdowania par tagów z zawartością
            full_pattern = f"{start_pattern}(.*?){end_pattern}"
            matches = re.finditer(full_pattern, text, re.DOTALL | re.IGNORECASE)
            
            for match in matches:
                reasoning_sections.append({
                    "full_match": match.group(0),
                    "content": match.group(1).strip(),
                    "start_tag": start_pattern,
                    "end_tag": end_pattern,
                    "start_pos": match.start(),
                    "end_pos": match.end()
                })
        
        logger.info(f"Wykryto {len(reasoning_sections)} sekcji rozumowania")
        return reasoning_sections
    
    def filter_reasoning(self, text: str) -> Tuple[str, List[Dict[str, str]]]:
        """Filtrowanie rozumowania z tekstu i zwracanie oczyszczonego tekstu oraz wykrytych sekcji"""
        reasoning_sections = self.detect_reasoning_sections(text)
        filtered_text = text
        
        # Usuwanie sekcji rozumowania z tekstu (od końca do początku aby zachować pozycje)
        for section in reversed(reasoning_sections):
            filtered_text = (
                filtered_text[:section["start_pos"]] + 
                filtered_text[section["end_pos"]:]
            )
        
        # Usuwanie podwójnych spacji i pustych linii
        filtered_text = re.sub(r'\n\s*\n', '\n\n', filtered_text)
        filtered_text = filtered_text.strip()
        
        logger.info(f"Przefiltrowano tekst - usunięto {len(reasoning_sections)} sekcji rozumowania")
        return filtered_text, reasoning_sections
    
    def process_ollama_response(self, response: Dict[str, any]) -> Dict[str, any]:
        """Przetwarzanie odpowiedzi Ollama z filtrowaniem rozumowania"""
        if not response or "raw_response" not in response:
            return response
        
        original_text = response["raw_response"]
        filtered_text, reasoning_sections = self.filter_reasoning(original_text)
        
        # Aktualizacja odpowiedzi
        processed_response = response.copy()
        processed_response["raw_response"] = filtered_text
        processed_response["filtered_reasoning"] = reasoning_sections
        
        # Dodanie informacji o filtrowaniu
        if reasoning_sections:
            processed_response["reasoning_removed"] = True
            processed_response["reasoning_count"] = len(reasoning_sections)
        else:
            processed_response["reasoning_removed"] = False
            processed_response["reasoning_count"] = 0
        
        return processed_response
    
    def save_reasoning_to_file(self, reasoning_sections: List[Dict[str, str]], 
                             output_path: Union[str, Path], audio_filename: str) -> None:
        """Zapisywanie rozumowania do osobnego pliku (jeśli włączone)"""
        if not self.save_reasoning or not reasoning_sections:
            return
        
        try:
            output_dir = Path(output_path)
            reasoning_filename = f"{audio_filename}_reasoning.txt"
            reasoning_path = output_dir / reasoning_filename
            
            with open(reasoning_path, 'w', encoding='utf-8') as f:
                f.write(f"Rozumowanie modelu dla: {audio_filename}\n")
                f.write("=" * 60 + "\n\n")
                
                for i, section in enumerate(reasoning_sections, 1):
                    f.write(f"SEKCJA ROZUMOWANIA {i}:\n")
                    f.write(f"Tag: {section['start_tag']}...{section['end_tag']}\n")
                    f.write("-" * 40 + "\n")
                    f.write(section['content'])
                    f.write("\n\n")
            
            logger.info(f"Rozumowanie zapisane do: {reasoning_path}")
            
        except Exception as e:
            logger.error(f"Błąd podczas zapisywania rozumowania: {e}")
    
    def get_reasoning_summary(self, reasoning_sections: List[Dict[str, str]]) -> str:
        """Generowanie podsumowania rozumowania"""
        if not reasoning_sections:
            return "Brak rozumowania do wyświetlenia"
        
        summary = f"Wykryto {len(reasoning_sections)} sekcji rozumowania:\n"
        for i, section in enumerate(reasoning_sections, 1):
            content_preview = section['content'][:100] + "..." if len(section['content']) > 100 else section['content']
            summary += f"{i}. {section['start_tag']}...{section['end_tag']}: {content_preview}\n"
        
        return summary 
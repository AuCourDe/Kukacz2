#!/usr/bin/env python3
"""
Moduł do analizy treści przez Ollama
====================================

Zawiera funkcje do:
- Analizy treści transkrypcji rozmów z wykorzystaniem wielu promptów
- Analizy wzorców mówców i ich zachowań
- Analizy sentymentu i emocji w rozmowie
- Integracji z serwerem Ollama z filtrowaniem rozumowania
"""

import logging
import sys
from typing import Dict, Any, List

from .config import (
    OLLAMA_MODEL,
    OLLAMA_BASE_URL,
    CONTENT_ANALYSIS_TYPE,
    OLLAMA_PROMPTS,
)
from .reasoning_filter import ReasoningFilter
from .colored_logging import print_colored
from .prompt_manager import get_prompt_manager

# Import OllamaAnalyzer
try:
    from .ollama_analyzer import OllamaAnalyzer
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False
    logging.warning("OllamaAnalyzer nie jest dostępny. Analiza treści będzie wyłączona.")

logger = logging.getLogger(__name__)

class ContentAnalyzer:
    """Analiza treści transkrypcji za pomocą modeli Ollama z filtrowaniem rozumowania"""
    
    def __init__(self, model: str = OLLAMA_MODEL, base_url: str = OLLAMA_BASE_URL):
        self.ollama_analyzer = None
        self.model = model
        self.base_url = base_url
        self.initialized = False
        self.reasoning_filter = ReasoningFilter()
        logger.info("ContentAnalyzer zainicjalizowany")
    
    def initialize(self) -> bool:
        """Inicjalizacja analizy Ollama z testem połączenia"""
        if not OLLAMA_AVAILABLE:
            logger.warning("OllamaAnalyzer nie jest dostępny")
            return False
        
        try:
            self.ollama_analyzer = OllamaAnalyzer(base_url=self.base_url, model=self.model)
            if self.ollama_analyzer.test_connection():
                logger.info(f"Analiza Ollama zainicjalizowana z modelem: {self.model}")
                self.initialized = True
                return True
            else:
                logger.warning("Nie udało się połączyć z serwerem Ollama")
                if getattr(self.ollama_analyzer, "last_connection_error", None) == "model_not_found":
                    available = getattr(self.ollama_analyzer, "last_available_models", [])
                    # Formatowanie listy dostępnych modeli
                    if available:
                        models_list = ', '.join(available)
                        models_info = f"Dostępne modele: {models_list}"
                    else:
                        models_info = "Brak dostępnych modeli na serwerze"
                    
                    # Komunikat w logach
                    logger.warning(
                        f"Model Ollama '{self.model}' nie jest dostępny na serwerze {self.base_url}. "
                        f"{models_info}"
                    )
                    
                    # Komunikat w terminalu z kolorem pomarańczowym
                    warning_msg = (
                        f"\n⚠️  OSTRZEŻENIE: Model Ollama '{self.model}' nie jest dostępny na serwerze!\n"
                        f"   {models_info}\n"
                        f"   Analiza Ollama będzie wyłączona. Aby włączyć analizę, ustaw w .env:\n"
                        f"   OLLAMA_MODEL=jedna_z_dostępnych_nazw_modeli\n"
                    )
                    print_colored(warning_msg, "WARNING", sys.stderr)
                return False
        except Exception as e:
            logger.error(f"Błąd podczas inicjalizacji Ollama: {e}")
            return False
    
    def analyze_transcription_content(self, transcription_data: Dict) -> Dict[str, Any]:
        """
        Kompleksowa analiza treści transkrypcji z wykorzystaniem wielu promptów.
        
        Każdy prompt z katalogu prompt/ (prompt01.txt - prompt99.txt) jest wykonywany
        osobno, a wyniki są łączone w jeden słownik.
        """
        if not self.initialized or not self.ollama_analyzer:
            return {"error": "Analiza Ollama nie jest dostępna"}
        
        try:
            text = transcription_data.get("text", "")
            speakers_data = transcription_data.get("speakers", [])
            
            analysis_results = {
                "prompt_results": [],
                "total_prompts": 0,
                "successful_prompts": 0,
                "failed_prompts": 0,
            }
            
            # Pobierz wszystkie prompty z katalogu
            prompt_manager = get_prompt_manager()
            prompts = prompt_manager.get_prompts_content()
            
            if not prompts:
                logger.warning("Brak promptów w katalogu prompt/. Używam domyślnej analizy.")
                # Fallback do starego systemu
                content_analysis = self.ollama_analyzer.analyze_content(
                    text, CONTENT_ANALYSIS_TYPE
                )
                content_analysis = self.reasoning_filter.process_ollama_response(content_analysis)
                analysis_results["content_analysis"] = content_analysis
                return analysis_results
            
            analysis_results["total_prompts"] = len(prompts)
            logger.info(f"Rozpoczęcie analizy treści przez Ollama ({len(prompts)} promptów)...")
            
            # Wykonaj każdy prompt po kolei
            for prompt_info in prompts:
                prompt_num = prompt_info["number"]
                prompt_content = prompt_info["content"]
                prompt_filename = prompt_info["filename"]
                
                logger.info(f"Wykonywanie promptu {prompt_num:02d}: {prompt_filename}")
                
                try:
                    # Wykonaj analizę z tym promptem
                    single_result = self.ollama_analyzer.analyze_with_custom_prompt(
                        text, prompt_content, prompt_num
                    )
                    
                    # Filtrowanie rozumowania
                    single_result = self.reasoning_filter.process_ollama_response(single_result)
                    
                    # Dodaj informacje o prompcie
                    single_result["prompt_number"] = prompt_num
                    single_result["prompt_filename"] = prompt_filename
                    
                    if single_result.get("success"):
                        analysis_results["successful_prompts"] += 1
                        logger.info(f"Prompt {prompt_num:02d} wykonany pomyślnie")
                    else:
                        analysis_results["failed_prompts"] += 1
                        logger.warning(
                            f"Prompt {prompt_num:02d} nie powiódł się: {single_result.get('error')}"
                        )
                    
                    # Sprawdź injection
                    if single_result.get("injection_detected"):
                        logger.warning(
                            f"Prompt {prompt_num:02d}: wykryto potencjalną próbę prompt injection: %s",
                            single_result.get("injection_matches"),
                        )
                    
                    analysis_results["prompt_results"].append(single_result)
                    
                except Exception as e:
                    logger.error(f"Błąd podczas wykonywania promptu {prompt_num:02d}: {e}")
                    analysis_results["failed_prompts"] += 1
                    analysis_results["prompt_results"].append({
                        "prompt_number": prompt_num,
                        "prompt_filename": prompt_filename,
                        "success": False,
                        "error": str(e),
                    })
            
            # Dla kompatybilności wstecznej - pierwszy wynik jako content_analysis
            if analysis_results["prompt_results"]:
                analysis_results["content_analysis"] = analysis_results["prompt_results"][0]
            
            logger.info(
                f"Analiza zakończona: {analysis_results['successful_prompts']}/{analysis_results['total_prompts']} promptów pomyślnie"
            )
            return analysis_results
            
        except Exception as e:
            logger.error(f"Błąd podczas analizy treści: {e}")
            return {"error": str(e)}
    
    def is_available(self) -> bool:
        """Sprawdzenie czy analiza Ollama jest dostępna"""
        return self.initialized and OLLAMA_AVAILABLE 
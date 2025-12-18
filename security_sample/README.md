# Security Sample - Bezpieczny Procesor Audio

## 📁 Zawartość folderu

Ten folder zawiera kompletny system zabezpieczeń dla aplikacji przetwarzania audio:

- **`security_processor.py`** - Główny moduł bezpieczeństwa (31KB, 826 linii)
- **`security_requirements.txt`** - Zależności Python dla zabezpieczeń
- **`SECURITY_README.md`** - Kompletna dokumentacja techniczna
- **`test_security.py`** - Skrypt testowy zabezpieczeń

## 🚀 Szybki start

### 1. Instalacja zależności
```bash
cd security_sample
pip install -r security_requirements.txt
```

### 2. Testowanie zabezpieczeń
```bash
python3 test_security.py
```

### 3. Użycie w projekcie
```python
# Dodaj folder security_sample do ścieżki Python
import sys
sys.path.append('security_sample')

# Import i użycie
from security_processor import SecurityProcessor, create_secure_config

config = create_secure_config(
    max_file_size_mb=100,
    max_concurrent_processes=2,
    use_docker_sandbox=True
)

processor = SecurityProcessor(config)
success, message, result = processor.process_audio_file_secure(file_path)
```

## 🛡️ Zaimplementowane zabezpieczenia

### Zagrożenia techniczne
- ✅ Walidacja plików audio (rozmiar, format, MIME)
- ✅ Izolacja procesów (Docker sandbox)
- ✅ Kontrola zasobów (CPU, pamięć)
- ✅ Timeout na procesy
- ✅ Bezpieczne FTP/SFTP

### Prompt Injection Protection
- ✅ Wykrywanie podejrzanych wzorców
- ✅ Sanityzacja transkrypcji
- ✅ Bezpieczne prompty LLM
- ✅ Walidacja odpowiedzi

### Denial of Service Protection
- ✅ Limit równoczesnych procesów
- ✅ Monitorowanie zasobów
- ✅ Automatyczne czyszczenie
- ✅ Kolejka z ograniczeniami

## 📖 Szczegółowa dokumentacja

Przeczytaj `SECURITY_README.md` aby poznać:
- Pełną architekturę bezpieczeństwa
- Konfigurację wszystkich modułów
- Przykłady użycia
- Troubleshooting
- Integrację z istniejącym systemem

## 🔧 Integracja z głównym projektem

Aby użyć SecurityProcessor w głównym projekcie:

1. **Dodaj do ścieżki Python:**
```python
import sys
sys.path.append('./security_sample')
```

2. **Zastąp standardowy procesor:**
```python
# Zamiast AudioProcessor
from security_processor import SecurityProcessor
processor = SecurityProcessor()
```

3. **Lub dodaj jako dodatkową warstwę:**
```python
# W istniejącym kodzie
def process_with_security(file_path):
    # Standardowe przetwarzanie
    result = standard_processor.process(file_path)
    
    # Dodatkowe sprawdzenia bezpieczeństwa
    from security_processor import SecurityProcessor
    security_processor = SecurityProcessor()
    is_safe, message, security_result = security_processor.process_audio_file_secure(file_path)
    
    if not is_safe:
        logger.warning(f"Problemy bezpieczeństwa: {message}")
    
    return result
```

## 🧪 Testowanie

### Uruchomienie wszystkich testów
```bash
python3 test_security.py
```

### Tworzenie pliku testowego
```bash
python3 test_security.py --create-sample
```

### Sprawdzenie środowiska
```bash
python3 -c "from security_processor import validate_environment; print(validate_environment())"
```

## 📊 Metryki bezpieczeństwa

- **Rozmiar kodu:** 826 linii
- **Moduły bezpieczeństwa:** 8 głównych klas
- **Wzorce prompt injection:** 11 wykrywanych wzorców
- **Formaty audio:** 5 obsługiwanych formatów
- **Sandboxy:** Docker + chroot
- **Monitoring:** CPU, pamięć, procesy

## ⚠️ Wymagania systemowe

- Python 3.8+
- Docker (opcjonalnie, dla sandbox)
- ffmpeg (dla walidacji audio)
- Uprawnienia do /tmp
- Biblioteki systemowe: python3-magic, psutil

## 🔗 Linki

- [Dokumentacja techniczna](SECURITY_README.md)
- [Testy zabezpieczeń](test_security.py)
- [Zależności](security_requirements.txt)
- [Główny projekt](../README.md) 
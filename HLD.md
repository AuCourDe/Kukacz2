Oto przykładowy diagram architektoniczny w formacie Mermaid. Pokazuje kierunki przepływu między głównymi komponentami Whisper Analyzer:

```mermaid
flowchart LR
    subgraph UI["Warstwa prezentacji (Flask)"]
        Dashboard["Dashboard / Upload\nweb_interface.py"]
        QueueView["API kolejki\n/queue.json"]
    end

    subgraph Orchestration["Orkiestracja"]
        Main["main.py\n(batch + watcher)"]
        WebServer["web_server.py\nFlask + worker"]
        AudioProcessor["AudioProcessor\n(audio_processor.py)"]
        ProcessingQueue["ProcessingQueue\n(Stan w pamięci)"]
    end

    subgraph IO["Wejście/Wyjście plików"]
        Input["INPUT_FOLDER\n(file_loader.py)"]
        Processed["processed/\nkopie i audio po obróbce"]
        Output["OUTPUT_FOLDER\n(result_saver.py)"]
    end

    subgraph Pipeline["Pipeline przetwarzania"]
        Preproc["AudioPreprocessor"]
        Transcriber["WhisperTranscriber\n(model Whisper)"]
        Diarizer["SpeakerDiarizer\n(pyannote / fallback)"]
        Analyzer["ContentAnalyzer\n(Ollama)"]
        ResultSaver["ResultSaver"]
    end

    subgraph External["Zewnętrzne zależności"]
        HF["HuggingFace pyannote\n(token)"]
        Ollama["Serwer Ollama"]
        Models["Cache modeli Whisper\n(torch, whisper)"]
    end

    Dashboard -->|upload plików| Input
    Dashboard -->|statusy| QueueView
    QueueView --> ProcessingQueue

    Main --> AudioProcessor
    WebServer --> AudioProcessor
    AudioProcessor --> ProcessingQueue
    AudioProcessor -->|watchdog| Input
    ProcessingQueue --> Dashboard

    Input -->|enqueue| ProcessingQueue
    ProcessingQueue -->|trigger| AudioProcessor

    AudioProcessor --> Preproc --> Transcriber --> Diarizer --> Analyzer --> ResultSaver
    ResultSaver --> Output
    AudioProcessor --> Processed

    Transcriber --> Models
    Diarizer --> HF
    Analyzer --> Ollama
```

**Jak czytać diagram:**
- Interfejs webowy (dashboard, API kolejki) komunikuje się z lokalną kolejką i folderem wejściowym; backend uruchamia `AudioProcessor`, który steruje pipeline’em przetwarzania audio.
- `AudioProcessor` odpowiada za cały przebieg: od pobrania pliku z `INPUT_FOLDER`, przez preprocessing i transkrypcję, po zapis wyników i aktualizację statusów.
- Moduły transkrypcji, diarization i analizy treści współpracują z zewnętrznymi usługami/modelami (Whisper cache, Hugging Face, Ollama).
- Wyniki trafiają do `OUTPUT_FOLDER` (pliki tekstowe) oraz `processed/` (kopie audio), a kolejka przekazuje referencje do interfejsu webowego.

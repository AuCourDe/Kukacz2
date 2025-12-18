#!/usr/bin/env python3
"""
Samodzielny serwer Flask umożliwiający dodawanie plików audio przez WWW.
"""

import logging

from .audio_processor import AudioProcessor
from .colored_logging import setup_colored_logging
from .config import (
    ENABLE_OLLAMA_ANALYSIS,
    ENABLE_SPEAKER_DIARIZATION,
    LOG_FILE,
    LOG_LEVEL,
    OLLAMA_MODEL,
    SPEAKER_DIARIZATION_TOKEN,
    WEB_HOST,
    WEB_PORT,
    WHISPER_MODEL,
)
from .processing_queue import ProcessingQueue
from .web_interface import create_web_app

logger = logging.getLogger(__name__)


def main():
    setup_colored_logging(level=LOG_LEVEL, log_file=str(LOG_FILE))
    queue = ProcessingQueue()
    processor = AudioProcessor(
        enable_speaker_diarization=ENABLE_SPEAKER_DIARIZATION,
        enable_ollama_analysis=ENABLE_OLLAMA_ANALYSIS,
        processing_queue=queue,
    )
    processor.initialize_components(
        whisper_model=WHISPER_MODEL,
        speaker_auth_token=SPEAKER_DIARIZATION_TOKEN,
        ollama_model=OLLAMA_MODEL,
    )

    flask_app = create_web_app(
        processor=processor,
        processing_queue=queue,
        input_folder=processor.file_loader.input_folder,
        output_folder=processor.result_saver.output_folder,
        asynchronous=True,
    )

    logger.info("Uruchamiam serwer Flask na %s:%s", WEB_HOST, WEB_PORT)
    flask_app.run(host=WEB_HOST, port=WEB_PORT, debug=False, threaded=True)


if __name__ == "__main__":
    main()


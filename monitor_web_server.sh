#!/bin/bash
# Skrypt monitorujący status aplikacji webowej co 2 minuty

LOG_FILE="/home/rev/projects/Whisper/web_server_monitor.log"
SERVER_URL="http://127.0.0.1:8080/login"
CHECK_INTERVAL=120  # 2 minuty w sekundach

log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_server_status() {
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVER_URL" 2>/dev/null)
    if [ "$HTTP_CODE" = "200" ]; then
        log_message "OK - Serwer odpowiada poprawnie (HTTP $HTTP_CODE)"
        return 0
    else
        log_message "BŁĄD - Serwer nie odpowiada poprawnie (HTTP $HTTP_CODE lub brak połączenia)"
        return 1
    fi
}

log_message "Rozpoczęto monitorowanie aplikacji webowej (sprawdzanie co ${CHECK_INTERVAL}s)"

while true; do
    if check_server_status; then
        sleep "$CHECK_INTERVAL"
    else
        log_message "Uwaga: Wykryto problem z serwerem, sprawdzanie ponownie za 30 sekund..."
        sleep 30
    fi
done


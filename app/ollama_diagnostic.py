#!/usr/bin/env python3
"""
Narzędzie diagnostyczne integracji z Ollama.

Uruchom:  python -m app.ollama_diagnostic [--json]

Zakres kontroli:
- Poprawność konfiguracji adresu i modelu Ollama
- Wykrycie zmiennych proxy mogących przechwytywać ruch
- Rozwiązanie DNS hosta i test połączenia TCP z portem Ollama
- Test zapytania HTTP do /api/tags i dostępności wybranego modelu
- Heurystyczna inspekcja zapory (ufw / firewall-cmd / netsh) – jeśli obecna
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional
from urllib.parse import urlparse

import requests

# Import ustawień aplikacji – zapewnia spójność z resztą projektu
from .config import OLLAMA_BASE_URL, OLLAMA_MODEL

DEFAULT_SOCKET_TIMEOUT = 5.0
DEFAULT_HTTP_TIMEOUT = 10.0


@dataclass
class DiagnosticResult:
    """Pojedynczy rezultat testu diagnostycznego."""

    name: str
    status: str  # "ok", "warning", "error"
    details: str

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status, "details": self.details}


def _status_ok(details: str) -> DiagnosticResult:
    return DiagnosticResult(name="", status="ok", details=details)


def _run_command(command: Iterable[str], timeout: float = 4.0) -> subprocess.CompletedProcess:
    """Uruchamia polecenie systemowe i zwraca CompletedProcess, zachowując stdout/stderr."""
    return subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def check_env_configuration(base_url: str, model: str) -> DiagnosticResult:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        return DiagnosticResult(
            name="environment",
            status="warning",
            details=f"Niepoprawny adres OLLAMA_BASE_URL='{base_url}'. Sprawdź protokół i host/port.",
        )
    if parsed.scheme not in {"http", "https"}:
        return DiagnosticResult(
            name="environment",
            status="warning",
            details=f"Nietypowy schemat URL '{parsed.scheme}'. Ollama wspiera HTTP; HTTPS wymaga reverse proxy.",
        )
    if not model:
        return DiagnosticResult(
            name="environment",
            status="warning",
            details="Zmienna OLLAMA_MODEL jest pusta – brak określonego modelu do analizy.",
        )
    return DiagnosticResult(
        name="environment",
        status="ok",
        details=f"Konfiguracja środowiska wygląda poprawnie (URL={base_url}, model={model}).",
    )


def check_proxy_settings() -> DiagnosticResult:
    relevant_keys = ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")
    active = {k: v for k, v in ((k, os.getenv(k)) for k in relevant_keys) if v}
    if not active:
        return DiagnosticResult(
            name="proxy",
            status="ok",
            details="Brak globalnych zmiennych proxy wpływających na ruch HTTP.",
        )
    explanation = ", ".join(f"{k}={v}" for k, v in active.items())
    return DiagnosticResult(
        name="proxy",
        status="warning",
        details=(
            f"Wykryto konfigurację proxy ({explanation}). Upewnij się, że host Ollama jest w wyjątkach "
            "lub proxy przepuszcza ruch na odpowiedni port."
        ),
    )


def check_dns_resolution(host: str) -> DiagnosticResult:
    try:
        ip_addr = socket.gethostbyname(host)
        return DiagnosticResult(
            name="dns",
            status="ok",
            details=f"Host '{host}' rozpoznany jako {ip_addr}.",
        )
    except socket.gaierror as exc:
        return DiagnosticResult(
            name="dns",
            status="error",
            details=f"Nie udało się rozwiązać hosta '{host}': {exc}. Sprawdź wpis w DNS/hosts.",
        )


def check_socket_connectivity(host: str, port: int, timeout: float = DEFAULT_SOCKET_TIMEOUT) -> DiagnosticResult:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
        return DiagnosticResult(
            name="tcp",
            status="ok",
            details=f"Połączenie TCP z {host}:{port} zestawione pomyślnie.",
        )
    except socket.timeout:
        return DiagnosticResult(
            name="tcp",
            status="error",
            details=f"Próba połączenia TCP z {host}:{port} przekroczyła limit czasu ({timeout}s). "
            "Możliwa blokada sieciowa lub brak usługi.",
        )
    except OSError as exc:
        return DiagnosticResult(
            name="tcp",
            status="error",
            details=f"Nie udało się otworzyć gniazda TCP na {host}:{port}: {exc}.",
        )


def check_http_endpoint(base_url: str, model: str, timeout: float = DEFAULT_HTTP_TIMEOUT) -> DiagnosticResult:
    url = base_url.rstrip("/") + "/api/tags"
    try:
        response = requests.get(url, timeout=timeout)
    except requests.exceptions.ProxyError as exc:
        return DiagnosticResult(
            name="http",
            status="error",
            details=f"Błąd połączenia HTTP przez proxy: {exc}",
        )
    except requests.exceptions.ConnectionError as exc:
        return DiagnosticResult(
            name="http",
            status="error",
            details=f"Połączenie HTTP do {url} nie powiodło się: {exc}",
        )
    except requests.exceptions.Timeout:
        return DiagnosticResult(
            name="http",
            status="error",
            details=f"Żądanie HTTP do {url} przekroczyło limit czasu {timeout}s.",
        )

    if response.status_code != 200:
        return DiagnosticResult(
            name="http",
            status="error",
            details=f"Otrzymano kod {response.status_code} z endpointu /api/tags: {response.text[:200]}",
        )

    try:
        payload = response.json()
    except ValueError:
        return DiagnosticResult(
            name="http",
            status="warning",
            details="Odpowiedź /api/tags nie zawierała poprawnego JSON – możliwe błędne proxy lub serwer.",
        )

    models = {entry.get("name") for entry in payload.get("models", []) if isinstance(entry, dict)}
    if not models:
        return DiagnosticResult(
            name="http",
            status="warning",
            details="Serwer zwrócił pustą listę modeli. Sprawdź, czy obrazy zostały załadowane do Ollama.",
        )
    if model not in models:
        return DiagnosticResult(
            name="http",
            status="warning",
            details=(
                f"Połączenie HTTP działa, ale model '{model}' nie jest dostępny. "
                f"Dostępne modele: {', '.join(sorted(models)) or 'brak'}."
            ),
        )
    return DiagnosticResult(
        name="http",
        status="ok",
        details=f"Serwer Ollama odpowiada poprawnie, model '{model}' znajduje się na liście.",
    )


def check_firewall_indicators(host: str, port: int) -> DiagnosticResult:
    """Sprawdza popularne narzędzia firewall i zwraca heurystyczny wynik."""
    checks: List[str] = []

    def add_check(check_callable: Callable[[], Optional[str]]) -> None:
        outcome = None
        try:
            outcome = check_callable()
        except Exception as exc:  # pragma: no cover - defensywne
            outcome = f"Nie udało się pobrać statusu zapory ({exc})"
        if outcome:
            checks.append(outcome)

    def ufw_status() -> Optional[str]:
        if shutil.which("ufw"):
            result = _run_command(["ufw", "status"])
            if "inactive" in result.stdout.lower():
                return "ufw: inactive"
            return f"ufw: {result.stdout.strip() or result.stderr.strip() or 'no output'}"
        return None

    def firewall_cmd_status() -> Optional[str]:
        if shutil.which("firewall-cmd"):
            result = _run_command(["firewall-cmd", "--state"])
            state = result.stdout.strip() or result.stderr.strip()
            return f"firewall-cmd: {state or 'unknown state'}"
        return None

    def windows_firewall() -> Optional[str]:
        if os.name == "nt" and shutil.which("netsh"):
            result = _run_command(["netsh", "advfirewall", "show", "allprofiles"])
            if "state" in result.stdout.lower():
                return "Windows firewall: sprawdź profil – upewnij się, że port jest dozwolony."
            return "Windows firewall: brak danych – sprawdź uprawnienia."
        return None

    add_check(ufw_status)
    add_check(firewall_cmd_status)
    add_check(windows_firewall)

    if not checks:
        return DiagnosticResult(
            name="firewall",
            status="ok",
            details="Nie wykryto aktywnej zapory w popularnych narzędziach (ufw/firewall-cmd/netsh).",
        )

    joined = "; ".join(checks)
    return DiagnosticResult(
        name="firewall",
        status="warning",
        details=(
            f"Wykryto potencjalnie aktywną zaporę ({joined}). Upewnij się, że ruch na {host}:{port} jest dozwolony."
        ),
    )


def run_diagnostics(base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL) -> List[DiagnosticResult]:
    parsed = urlparse(base_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if parsed.scheme == "https" else 11434)

    results = [
        check_env_configuration(base_url, model),
        check_proxy_settings(),
        check_dns_resolution(host),
        check_socket_connectivity(host, port),
        check_http_endpoint(base_url, model),
        check_firewall_indicators(host, port),
    ]

    # Uzupełnij pola name, jeżeli funkcje użyły domyślnego
    name_map = {
        "environment": "Konfiguracja środowiska",
        "proxy": "Zmienne proxy",
        "dns": "Rozwiązanie DNS",
        "tcp": "Połączenie TCP",
        "http": "Zapytanie HTTP",
        "firewall": "Zapora sieciowa",
    }
    for res in results:
        res.name = name_map.get(res.name, res.name or "nieznany test")
    return results


def _print_report(results: List[DiagnosticResult]) -> None:
    max_name = max((len(result.name) for result in results), default=10)
    for result in results:
        status = result.status.upper().ljust(7)
        print(f"{result.name.ljust(max_name)} | {status} | {result.details}")

    failing = [r for r in results if r.status == "error"]
    warnings = [r for r in results if r.status == "warning"]
    if failing:
        print("\nWykryto krytyczne problemy (ERROR) – wymagają interwencji.")
    if warnings:
        print("Obecne ostrzeżenia (WARNING) – rozważ weryfikację konfiguracji.")
    if not failing and not warnings:
        print("\nBrak błędów ani ostrzeżeń – integracja powinna działać prawidłowo.")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnostyka połączenia z serwerem Ollama.")
    parser.add_argument("--json", action="store_true", help="Zwróć wynik w formacie JSON.")
    parser.add_argument(
        "--base-url",
        default=OLLAMA_BASE_URL,
        help="Nadpisuje adres OLLAMA_BASE_URL na potrzeby diagnostyki.",
    )
    parser.add_argument(
        "--model",
        default=OLLAMA_MODEL,
        help="Model Ollama, którego dostępność zostanie zweryfikowana.",
    )
    args = parser.parse_args(argv)

    results = run_diagnostics(base_url=args.base_url, model=args.model)
    status_priority = {"error": 2, "warning": 1, "ok": 0}
    exit_code = 0 if all(r.status == "ok" for r in results) else max(status_priority[r.status] for r in results)

    if args.json:
        json.dump([result.to_dict() for result in results], sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        _print_report(results)

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())


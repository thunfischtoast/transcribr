# Entwicklerübersicht

## Projektstruktur

### Hauptkomponenten
- **Backend (FastAPI)**: Stellt die API-Endpunkte und Weboberfläche bereit
- **Datenbank (SQLite)**: Speichert Meeting- und Transkriptionsdaten
- **Transkriptionsservice**: Verarbeitet Audiodateien und erstellt Transkripte
- **Job-Queue (Celery + Redis)**: Verwaltet asynchrone Verarbeitungsaufgaben

### Dateien und Verzeichnisse
- `main.py`: Hauptanwendung mit FastAPI-Routen und Endpunkten
- `models.py`: Datenmodelle und Schemas
- `database.py`: Datenbankzugriff und CRUD-Operationen
- `task.py`: Celery-Tasks für asynchrone Verarbeitung
- `templates/`: Jinja2-Templates für die Weboberfläche
- `data/`: Speicherort für Datenbank, Audio- und Transkriptionsdateien

## Entwicklungsumgebung einrichten

### Voraussetzungen
- Python 3.8+
- Docker und Docker Compose
- Git

### Lokale Entwicklung
1. Repository klonen
2. Virtuelle Umgebung erstellen: `python -m venv venv`
3. Abhängigkeiten installieren: `pip install -r frozen-requirements.txt`
4. Docker-Container starten: `docker-compose up -d`
5. Anwendung starten: `cd backend && uvicorn main:app --reload`

### Abhängigkeiten
Die Hauptabhängigkeiten des Projekts sind:
- FastAPI: Web-Framework für API-Entwicklung
- Celery: Asynchrone Task-Queue
- Jinja2: Template-Engine für HTML-Rendering
- SQLite: Leichtgewichtige Datenbank
- Requests: HTTP-Client für API-Aufrufe
- Pydantic: Datenvalidierung und -serialisierung

Eine vollständige Liste der Abhängigkeiten finden Sie in der Datei `frozen-requirements.txt`.

## Beitragsrichtlinien

### Code-Stil
- PEP 8 für Python-Code
- Docstrings für alle Funktionen und Klassen
- Typisierung mit Python-Typhinweisen

### Pull-Request-Prozess
1. Feature-Branch erstellen: `git checkout -b feature/name`
2. Änderungen implementieren und testen
3. Pull-Request mit detaillierter Beschreibung erstellen
4. Code-Review abwarten und Feedback einarbeiten

### Tests
- Automatisierte Tests für neue Funktionen schreiben
- Bestehende Tests vor dem Einreichen von PRs ausführen

## Architektur

### Datenfluss
1. Benutzer erstellt Meeting und lädt Audiodatei hoch
2. Transkriptionsauftrag wird in die Warteschlange gestellt
3. Celery-Worker verarbeitet den Auftrag und sendet die Audiodatei an den Transkriptionsservice
4. Transkriptionsergebnis wird in der Datenbank gespeichert
5. Benutzer kann das Transkript im Meeting-Detail einsehen

### API-Endpunkte
Siehe `endpoints.md` für eine vollständige Liste der verfügbaren API-Endpunkte.

## Deployment

### Docker-Compose
Die Anwendung ist für die Bereitstellung mit Docker Compose konfiguriert:
```bash
docker-compose up -d
```

### Umgebungsvariablen
- `REDIS_URL`: URL für Redis-Verbindung
- `TRANSCRIPTION_SERVICE_URL`: URL des Transkriptionsdienstes
- `DATA_DIR`: Verzeichnis für Datenspeicherung

## Fehlerbehebung

### Häufige Probleme
- **Redis-Verbindungsfehler**: Prüfen Sie, ob der Redis-Container läuft
- **Transkriptionsfehler**: Überprüfen Sie die Logs des Transkriptionsdienstes
- **Datenbankfehler**: Stellen Sie sicher, dass das Datenverzeichnis beschreibbar ist

### Logging
Die Anwendung verwendet das Python-Logging-Modul. Logs werden in der Konsole ausgegeben und können für die Fehlerbehebung verwendet werden.

# Technology Stack Summary

## Core Components
- **Backend**: FastAPI with Jinja2 templating
- **Database**: SQLite for data persistence
- **Frontend**: Bulma CSS with htmx for AJAX interactions
- **Transcription**: onerahmet/openai-whisper-asr-webservice container
- **Job Queue**: Redis + Celery for asynchronous processing

## Infrastructure
- **Container Orchestration**: Docker Compose
- **Data Sharing**: Shared volume mounted to containers
- **Deployment Model**: Multi-container application with bound local storage

This stack provides a lightweight yet powerful solution combining modern API capabilities with minimal frontend dependencies while leveraging pre-built transcription services. The asynchronous job processing ensures scalable audio processing without blocking the main application.
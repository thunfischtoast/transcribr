# Developer Overview

## Project Structure

### Main Components
- **Backend (FastAPI)**: Provides API endpoints and web interface
- **Database (SQLite)**: Stores meeting and transcription data
- **Transcription Service**: Processes audio files and creates transcripts
- **Job Queue (Celery + Redis)**: Manages asynchronous processing tasks

### Files and Directories
- `main.py`: Main application with FastAPI routes and endpoints
- `models.py`: Data models and schemas
- `database.py`: Database access and CRUD operations
- `task.py`: Celery tasks for asynchronous processing
- `templates/`: Jinja2 templates for the web interface
- `data/`: Storage location for database, audio, and transcription files

## Setting Up Development Environment

### Prerequisites
- Python 3.8+
- Docker and Docker Compose
- Git

### Local Development
1. Clone repository
2. Create virtual environment: `python -m venv venv`
3. Install dependencies: `pip install -r frozen-requirements.txt`
4. Start Docker containers: `docker-compose up -d`
5. Start application: `cd backend && uvicorn main:app --reload`

### Dependencies
The main dependencies of the project are:
- FastAPI: Web framework for API development
- Celery: Asynchronous task queue
- Jinja2: Template engine for HTML rendering
- SQLite: Lightweight database
- Requests: HTTP client for API calls
- Pydantic: Data validation and serialization

A complete list of dependencies can be found in the `frozen-requirements.txt` file.

## Contribution Guidelines

### Code Style
- PEP 8 for Python code
- Docstrings for all functions and classes
- Typing with Python type hints

### Pull Request Process
1. Create feature branch: `git checkout -b feature/name`
2. Implement and test changes
3. Create pull request with detailed description
4. Wait for code review and incorporate feedback

### Tests
- Write automated tests for new features
- Run existing tests before submitting PRs

## Architecture

### Data Flow
1. User creates meeting and uploads audio file
2. Transcription job is queued
3. Celery worker processes the job and sends the audio file to the transcription service
4. Transcription result is stored in the database
5. User can view the transcript in the meeting detail

### API Endpoints
See `endpoints.md` for a complete list of available API endpoints.

## Deployment

### Docker Compose
The application is configured for deployment with Docker Compose:
```bash
docker-compose up -d
```

### Environment Variables
- `REDIS_URL`: URL for Redis connection
- `TRANSCRIPTION_SERVICE_URL`: URL of the transcription service
- `DATA_DIR`: Directory for data storage

## Troubleshooting

### Common Issues
- **Redis connection errors**: Check if the Redis container is running
- **Transcription errors**: Check the logs of the transcription service
- **Database errors**: Ensure the data directory is writable

### Logging
The application uses the Python logging module. Logs are output to the console and can be used for troubleshooting.

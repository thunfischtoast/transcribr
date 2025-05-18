# Communication Interfaces

## FastAPI Endpoints

### Meeting Management
- `GET /meetings` - List all meetings
- `GET /meetings/{id}` - Get meeting details
- `POST /meetings` - Create new meeting
- `PUT /meetings/{id}` - Update meeting
- `DELETE /meetings/{id}` - Delete meeting

### Audio Processing
- `POST /meetings/{id}/upload` - Upload audio file for meeting
- `POST /meetings/{id}/transcribe` - Queue audio for transcription
- `GET /meetings/{id}/transcript` - Get transcription result

### Queue Management
- `GET /queue` - View transcription queue status
- `GET /queue/{job_id}` - Check specific job status

### UI Routes
- `GET /` - Main page (meeting list)
- `GET /meetings/new` - Meeting creation form
- `GET /meetings/{id}/view` - View meeting details and transcript

## Celery Tasks

### Transcription Tasks
- `submit_transcription(meeting_id, audio_path)` - Submit file to transcription service
- `poll_transcription_status(job_id, meeting_id)` - Check if transcription is complete
- `process_completed_transcript(meeting_id, transcript_data)` - Save completed transcript

### Utility Tasks
- `cleanup_audio_files(days=7)` - Periodic task to remove old audio files
- `health_check_transcription_service()` - Verify transcription service availability

## Whisper ASR Service Communication

### REST API Interaction
- `POST /asr` - Submit audio for transcription (called from Celery task)
- `GET /health` - Check service health

## Data Flow
1. Frontend submits forms/requests via htmx to FastAPI endpoints
2. FastAPI endpoints trigger Celery tasks via Redis
3. Celery worker communicates with Whisper ASR service
4. Results flow back through Celery → FastAPI → Frontend

## Status Updates
- WebSocket at `/ws/queue-updates` for real-time queue status (optional enhancement)
- Polling endpoint for queue status updates when WebSockets not needed
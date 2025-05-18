# Meeting Transcript Management System - Overview

## Purpose
Web application for managing meeting transcripts through a simple browser interface.

## Architecture

### Components
1. **Web Backend/Frontend (FastAPI Container)**
   - User interface
   - API endpoints
   - Meeting data management
   - File handling
   - Transcription job queueing

2. **Transcription Service (Open Source Container)**
   - Audio file processing
   - Speech-to-text conversion
   - Queue management

### Data Model
- **Meeting**: title, date, link, associated audio file, transcript, status
- **TranscriptionJob**: audio reference, status, timestamps

## Key Features
1. Meeting CRUD operations
2. Audio file upload
3. Transcription job queueing
4. Transcript display
5. Queue status monitoring

## Technical Approach
- **Backend**: FastAPI (Python)
- **Frontend**: HTML, vanilla JavaScript, minimal CSS framework
- **Communication**: REST API
- **Persistence**: SQLite or similar lightweight database
- **Transcription**: Integration with open-source STT system (e.g., Whisper, Mozilla DeepSpeech)

## User Flow
1. User creates meeting entry
2. User uploads audio file for meeting
3. User queues audio for transcription
4. System processes audio in transcription container
5. System updates meeting with completed transcript
6. User views transcript alongside meeting details

## Security & Considerations
- File size limits for audio uploads
- Support for common audio formats
- Error handling for failed transcriptions
- Potential for long-running transcription jobs
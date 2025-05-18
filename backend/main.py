from typing import Union, List
from datetime import datetime
import os

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from task import dummy_task, submit_transcription, poll_transcription_status, process_completed_transcript
from task import app as celery_app
from database import db
from models import Meeting, MeetingCreate, MeetingUpdate, TranscriptionStatus, TranscriptionJob

app = FastAPI()


@app.get("/")
def read_root():
    return {"Hello": "World"}


class TaskOut(BaseModel):
    id: str
    status: str


@app.get("/start")
def start() -> TaskOut:
    r = dummy_task.delay()
    return _to_task_out(r)


@app.get("/status")
def status(task_id: str) -> TaskOut:
    r = celery_app.AsyncResult(task_id)
    return _to_task_out(r)


def _to_task_out(r: AsyncResult) -> TaskOut:
    return TaskOut(id=r.task_id, status=r.status)


# Meeting Endpoints
@app.get("/meetings", response_model=List[Meeting])
def get_meetings():
    return db.get_all_meetings()


@app.get("/meetings/{meeting_id}", response_model=Meeting)
def get_meeting(meeting_id: int):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    return meeting


@app.post("/meetings", response_model=Meeting)
def create_meeting(meeting: MeetingCreate):
    return db.create_meeting(meeting)


@app.put("/meetings/{meeting_id}", response_model=Meeting)
def update_meeting(meeting_id: int, meeting_update: MeetingUpdate):
    updated_meeting = db.update_meeting(meeting_id, meeting_update)
    if not updated_meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    return updated_meeting


@app.delete("/meetings/{meeting_id}")
def delete_meeting(meeting_id: int):
    success = db.delete_meeting(meeting_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    return {"message": "Meeting erfolgreich gelöscht"}


# Transcription Endpoints
@app.post("/meetings/{meeting_id}/transcribe")
def transcribe_meeting(meeting_id: int):
    # Hole das Meeting aus der Datenbank
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    
    if not meeting.audio_file:
        raise HTTPException(status_code=400, detail="Keine Audio-Datei für dieses Meeting vorhanden")
    
    # Aktualisiere den Meeting-Status auf "processing"
    db.update_meeting(
        meeting_id,
        MeetingUpdate(status=TranscriptionStatus.PROCESSING)
    )
    
    # Starte den Transkriptionstask
    r = submit_transcription.delay(meeting_id, meeting.audio_file)
    
    # Erstelle einen Transkriptionsjob in der Datenbank
    job = db.create_transcription_job(meeting_id, r.task_id)
    
    return {"job_id": job.job_id, "status": job.status}


@app.get("/queue")
def get_queue_status():
    return db.get_all_transcription_jobs()


@app.get("/queue/{job_id}")
def get_job_status(job_id: str):
    job = db.get_transcription_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")
    
    # Celery-Status prüfen
    celery_result = celery_app.AsyncResult(job_id)
    celery_status = celery_result.status
    
    # Wenn der Celery-Status sich geändert hat, aktualisieren wir den Job-Status
    if celery_status == "SUCCESS" and job.status != TranscriptionStatus.COMPLETED:
        # Ergebnis des Tasks abrufen
        task_result = celery_result.result
        
        # Wenn das Ergebnis ein Transkript enthält, speichern wir es
        if isinstance(task_result, dict):
            if task_result.get("status") == "completed":
                # Prüfen, ob ein Transkript-Datei-Pfad vorhanden ist
                transcript_file = task_result.get("transcript_file")
                if transcript_file and os.path.exists(transcript_file):
                    with open(transcript_file, "r", encoding="utf-8") as f:
                        transcript_text = f.read()
                    # Transkript in der Datenbank speichern
                    db.save_transcript(job.meeting_id, transcript_text)
            
        job = db.update_transcription_job_status(job_id, TranscriptionStatus.COMPLETED)
        
    elif celery_status == "FAILURE" and job.status != TranscriptionStatus.FAILED:
        job = db.update_transcription_job_status(job_id, TranscriptionStatus.FAILED)
    elif celery_status == "STARTED" and job.status == TranscriptionStatus.PENDING:
        job = db.update_transcription_job_status(job_id, TranscriptionStatus.PROCESSING)
    
    return job


from fastapi import File, UploadFile

@app.post("/meetings/{meeting_id}/upload")
async def upload_audio_file(meeting_id: int, file: UploadFile = File(...)):
    # Prüfe, ob das Meeting existiert
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    
    # Stelle sicher, dass das Upload-Verzeichnis existiert
    upload_dir = os.path.join("data", "audio")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Generiere einen eindeutigen Dateinamen
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"meeting_{meeting_id}_{timestamp}{os.path.splitext(file.filename)[1]}"
    file_path = os.path.join(upload_dir, filename)
    relative_path = os.path.join("audio", filename)
    
    # Speichere die hochgeladene Datei
    try:
        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fehler beim Speichern der Datei: {str(e)}")
    
    # Aktualisiere den Dateipfad im Meeting
    updated_meeting = db.update_meeting(
        meeting_id, 
        MeetingUpdate(audio_file=relative_path)
    )
    
    return {"message": "Audio-Datei erfolgreich hochgeladen", "meeting": updated_meeting}


@app.get("/meetings/{meeting_id}/transcript")
def get_transcript(meeting_id: int):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    
    if not meeting.transcript:
        raise HTTPException(status_code=404, detail="Kein Transkript für dieses Meeting vorhanden")
    
    return {"meeting_id": meeting_id, "transcript": meeting.transcript}

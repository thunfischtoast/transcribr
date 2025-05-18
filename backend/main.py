from typing import Union, List
from datetime import datetime

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

from task import dummy_task
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
    # Hier würden wir normalerweise die Audio-Datei an den Transcription-Service senden
    # Für jetzt verwenden wir den dummy_task als Platzhalter
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    
    if not meeting.audio_file:
        raise HTTPException(status_code=400, detail="Keine Audio-Datei für dieses Meeting vorhanden")
    
    # Dummy-Task starten
    r = dummy_task.delay()
    
    # Transcription Job erstellen
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
        job = db.update_transcription_job_status(job_id, TranscriptionStatus.COMPLETED)
        # Hier würden wir normalerweise das Transkript speichern
        db.save_transcript(job.meeting_id, "Dies ist ein Beispiel-Transkript.")
    elif celery_status == "FAILURE" and job.status != TranscriptionStatus.FAILED:
        job = db.update_transcription_job_status(job_id, TranscriptionStatus.FAILED)
    elif celery_status == "STARTED" and job.status == TranscriptionStatus.PENDING:
        job = db.update_transcription_job_status(job_id, TranscriptionStatus.PROCESSING)
    
    return job


@app.post("/meetings/{meeting_id}/upload")
def upload_audio_file(meeting_id: int):
    # Hier würden wir normalerweise die Datei hochladen
    # Für jetzt aktualisieren wir nur den Pfad
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    
    audio_path = f"uploads/meeting_{meeting_id}.mp3"
    updated_meeting = db.update_meeting(
        meeting_id, 
        MeetingUpdate(audio_file=audio_path)
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

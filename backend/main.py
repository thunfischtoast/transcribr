import os
from datetime import datetime
from typing import List

from celery.result import AsyncResult
from database import db
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.templating import Jinja2Templates
from models import (
    Meeting,
    MeetingCreate,
    MeetingUpdate,
    TranscriptionStatus,
)
from pydantic import BaseModel
from task import app as celery_app
from task import (
    dummy_task,
    submit_transcription,
)

app = FastAPI()

# Templates und statische Dateien einrichten
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def read_root(request: Request):
    meetings = db.get_all_meetings()
    return templates.TemplateResponse(
        "index.html", {"request": request, "meetings": meetings}
    )


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


@app.get("/meetings/{meeting_id}", response_model=None)
async def get_meeting_detail(request: Request, meeting_id: int):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")
    return templates.TemplateResponse(
        "meeting_detail.html", {"request": request, "meeting": meeting}
    )


@app.post("/meetings", response_model=None)
async def create_meeting(
    request: Request,
    title: str = Form(...),
    date: str = Form(...),
    link: str = Form(None),
):
    # Datum aus dem Formular in datetime umwandeln
    meeting_date = datetime.fromisoformat(date.replace("T", " "))

    # Meeting-Objekt erstellen
    meeting_create = MeetingCreate(title=title, date=meeting_date, link=link)

    # Meeting in der Datenbank erstellen
    meeting = db.create_meeting(meeting_create)

    # Wenn es ein HTMX-Request ist, nur die Meeting-Karte zurückgeben
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            "index.html",
            {"request": request, "meetings": [meeting]},
            headers={"HX-Trigger": "meetingCreated"},
        )

    # Ansonsten zur Hauptseite umleiten
    return templates.TemplateResponse(
        "index.html", {"request": request, "meetings": db.get_all_meetings()}
    )


@app.put("/meetings/{meeting_id}", response_model=None)
async def update_meeting(
    request: Request,
    meeting_id: int,
    title: str = Form(...),
    date: str = Form(...),
    link: str = Form(None),
):
    # Datum aus dem Formular in datetime umwandeln
    meeting_date = datetime.fromisoformat(date.replace("T", " "))

    # Meeting-Update-Objekt erstellen
    meeting_update = MeetingUpdate(title=title, date=meeting_date, link=link)

    # Meeting in der Datenbank aktualisieren
    updated_meeting = db.update_meeting(meeting_id, meeting_update)
    if not updated_meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")

    # Zur Meeting-Detailseite zurückkehren
    return templates.TemplateResponse(
        "meeting_detail.html", {"request": request, "meeting": updated_meeting}
    )


@app.delete("/meetings/{meeting_id}")
async def delete_meeting(request: Request, meeting_id: int):
    success = db.delete_meeting(meeting_id)
    if not success:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")

    if request.headers.get("HX-Request"):
        # Wenn es ein HTMX-Request ist, leere Antwort zurückgeben (Element wird entfernt)
        return ""

    # Ansonsten zur Hauptseite umleiten
    return templates.TemplateResponse(
        "index.html", {"request": request, "meetings": db.get_all_meetings()}
    )


# Transcription Endpoints
@app.post("/meetings/{meeting_id}/transcribe")
async def transcribe_meeting(request: Request, meeting_id: int):
    # Hole das Meeting aus der Datenbank
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")

    if not meeting.audio_file:
        raise HTTPException(
            status_code=400, detail="Keine Audio-Datei für dieses Meeting vorhanden"
        )

    # Aktualisiere den Meeting-Status auf "processing"
    db.update_meeting(meeting_id, MeetingUpdate(status=TranscriptionStatus.PROCESSING))

    # Starte den Transkriptionstask
    r = submit_transcription.delay(meeting_id, meeting.audio_file)

    # Erstelle einen Transkriptionsjob in der Datenbank
    job = db.create_transcription_job(meeting_id, r.task_id)

    # Aktualisiere das Meeting-Objekt
    meeting = db.get_meeting(meeting_id)

    if request.headers.get("HX-Request"):
        # Wenn es ein HTMX-Request ist, zur Meeting-Detailseite zurückkehren
        return templates.TemplateResponse(
            "meeting_detail.html", {"request": request, "meeting": meeting}
        )

    return {"job_id": job.job_id, "status": job.status}


@app.get("/queue")
async def get_queue_status(request: Request):
    jobs = db.get_all_transcription_jobs()
    if request.headers.get("HX-Request"):
        # Wenn es ein HTMX-Request ist, nur die Tabelle zurückgeben
        return templates.TemplateResponse(
            "job_row.html", {"request": request, "jobs": jobs}
        )
    return templates.TemplateResponse("queue.html", {"request": request, "jobs": jobs})


@app.get("/queue/{job_id}")
async def get_job_status(request: Request, job_id: str):
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

    if request.headers.get("HX-Request"):
        # Wenn es ein HTMX-Request ist, nur die Zeile zurückgeben
        return templates.TemplateResponse(
            "job_row.html", {"request": request, "job": job}
        )
    return job


@app.post("/meetings/{meeting_id}/upload")
async def upload_audio_file(
    request: Request, meeting_id: int, file: UploadFile = File(...)
):
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
        raise HTTPException(
            status_code=500, detail=f"Fehler beim Speichern der Datei: {str(e)}"
        )

    # Aktualisiere den Dateipfad im Meeting
    updated_meeting = db.update_meeting(
        meeting_id, MeetingUpdate(audio_file=relative_path)
    )

    if request.headers.get("HX-Request"):
        # Wenn es ein HTMX-Request ist, zur Meeting-Detailseite zurückkehren
        return templates.TemplateResponse(
            "meeting_detail.html", {"request": request, "meeting": updated_meeting}
        )

    return {
        "message": "Audio-Datei erfolgreich hochgeladen",
        "meeting": updated_meeting,
    }


@app.get("/meetings/{meeting_id}/transcript")
def get_transcript(meeting_id: int):
    meeting = db.get_meeting(meeting_id)
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting nicht gefunden")

    if not meeting.transcript:
        raise HTTPException(
            status_code=404, detail="Kein Transkript für dieses Meeting vorhanden"
        )

    return {"meeting_id": meeting_id, "transcript": meeting.transcript}

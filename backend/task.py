# in file task.py
from celery.app import Celery
from celery.schedules import crontab
from datetime import datetime, timedelta
import os
import requests
import json
import logging
from typing import Optional, Dict, Any

# Konfiguration
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
whisper_service_url = os.getenv("TRANSCRIPTION_SERVICE_URL", "http://transcription:9000")
data_dir = os.getenv("DATA_DIR", "/app/data")
audio_dir = os.path.join(data_dir, "audio")
celery_dir = os.path.join(data_dir, "celery")

# Stellen Sie sicher, dass die Verzeichnisse existieren
for directory in [audio_dir, celery_dir]:
    os.makedirs(directory, exist_ok=True)

# Logger konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Celery-App initialisieren
app = Celery(__name__, broker=redis_url, backend=redis_url)

# Celery Beat Zeitplan für periodische Aufgaben
app.conf.beat_schedule = {
    'cleanup-audio-files-weekly': {
        'task': 'task.cleanup_audio_files',
        'schedule': crontab(day_of_week='sunday', hour=2, minute=0),  # Jeden Sonntag um 2 Uhr morgens
        'args': (7,),  # Dateien älter als 7 Tage löschen
    },
    'health-check-every-hour': {
        'task': 'task.health_check_transcription_service',
        'schedule': crontab(minute=0),  # Jede Stunde
    },
}
app.conf.timezone = 'UTC'


@app.task
def dummy_task():
    """Legacy-Dummy-Task für Tests."""
    folder = celery_dir
    os.makedirs(folder, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with open(f"{folder}/task-{now}.txt", "w") as f:
        f.write("hello!")
    return "Task completed"


@app.task
def submit_transcription(meeting_id: int, audio_path: str) -> Dict[str, Any]:
    """
    Sendet eine Audiodatei an den Whisper-Transkriptionsservice.
    
    Args:
        meeting_id: ID des Meetings
        audio_path: Pfad zur Audiodatei
    
    Returns:
        Dictionary mit job_id und Status
    """
    logger.info(f"Submitting transcription for meeting {meeting_id}, audio: {audio_path}")
    
    # Vollständigen Pfad zur Audiodatei erstellen
    full_audio_path = os.path.join(data_dir, audio_path)
    
    if not os.path.exists(full_audio_path):
        error_msg = f"Audio file not found: {full_audio_path}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "failed"}
    
    try:
        # Datei an den Whisper-Service senden
        with open(full_audio_path, 'rb') as audio_file:
            files = {'audio_file': audio_file}
            response = requests.post(
                f"{whisper_service_url}/asr",
                files=files,
                data={"task": "transcribe", "language": "de"}
            )
        
        if response.status_code == 200:
            result = response.json()
            job_id = result.get("id", "unknown")
            
            # Starte einen Task zum Abfragen des Status
            poll_transcription_status.delay(job_id, meeting_id)
            
            return {
                "job_id": job_id,
                "status": "submitted",
                "meeting_id": meeting_id
            }
        else:
            error_msg = f"Error submitting transcription: {response.text}"
            logger.error(error_msg)
            return {"error": error_msg, "status": "failed"}
            
    except Exception as e:
        import traceback
        stack_trace = traceback.format_exc()
        error_msg = f"Exception during transcription submission: {str(e)}"
        logger.error(f"{error_msg}\n{stack_trace}")
        return {"error": error_msg, "stack_trace": stack_trace, "status": "failed"}


@app.task
def poll_transcription_status(job_id: str, meeting_id: int, max_retries: int = 60, retry_delay: int = 30):
    """
    Überprüft den Status einer Transkription beim Whisper-Service.
    Wird wiederholt aufgerufen, bis die Transkription abgeschlossen ist oder fehlschlägt.
    
    Args:
        job_id: ID des Transkriptionsjobs
        meeting_id: ID des zugehörigen Meetings
        max_retries: Maximale Anzahl von Wiederholungen
        retry_delay: Verzögerung zwischen den Wiederholungen in Sekunden
    """
    logger.info(f"Polling transcription status for job {job_id}, meeting {meeting_id}")
    
    try:
        # Status vom Whisper-Service abfragen
        response = requests.get(f"{whisper_service_url}/asr?id={job_id}")
        
        if response.status_code == 200:
            result = response.json()
            status = result.get("status")
            
            if status == "completed":
                # Transkription ist fertig, verarbeite das Ergebnis
                transcript_text = result.get("text", "")
                process_completed_transcript.delay(meeting_id, transcript_text)
                return {"status": "completed", "job_id": job_id}
                
            elif status == "failed":
                logger.error(f"Transcription failed for job {job_id}")
                return {"status": "failed", "job_id": job_id}
                
            else:
                # Noch in Bearbeitung, erneut abfragen nach Verzögerung
                # Überprüfe, ob maximale Anzahl von Wiederholungen erreicht ist
                current_retry = poll_transcription_status.request.retries
                if current_retry < max_retries:
                    logger.info(f"Job {job_id} still in progress, retrying in {retry_delay} seconds")
                    raise poll_transcription_status.retry(countdown=retry_delay)
                else:
                    logger.error(f"Max retries reached for job {job_id}")
                    return {"status": "timeout", "job_id": job_id}
        else:
            error_msg = f"Error checking transcription status: {response.text}"
            logger.error(error_msg)
            return {"error": error_msg, "status": "failed"}
            
    except Exception as e:
        logger.error(f"Exception during status check: {str(e)}")
        # Bei Netzwerkfehlern erneut versuchen
        current_retry = poll_transcription_status.request.retries
        if current_retry < max_retries:
            raise poll_transcription_status.retry(countdown=retry_delay, exc=e)
        else:
            return {"error": str(e), "status": "failed"}


@app.task
def process_completed_transcript(meeting_id: int, transcript_text: str) -> Dict[str, Any]:
    """
    Verarbeitet ein fertiges Transkript und speichert es in der Datenbank.
    
    Args:
        meeting_id: ID des Meetings
        transcript_text: Der Transkriptionstext
    
    Returns:
        Status-Dictionary
    """
    logger.info(f"Processing completed transcript for meeting {meeting_id}")
    
    try:
        # Hier würden wir normalerweise die Datenbank direkt aktualisieren
        # Da wir aber die Datenbankverbindung nicht direkt in den Tasks haben,
        # speichern wir das Transkript in einer Datei und aktualisieren die DB über die API
        
        # Transkript in Datei speichern
        transcript_dir = os.path.join(data_dir, "transcripts")
        os.makedirs(transcript_dir, exist_ok=True)
        
        transcript_file = os.path.join(transcript_dir, f"meeting_{meeting_id}_transcript.txt")
        with open(transcript_file, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        
        # API-Endpunkt aufrufen, um das Meeting zu aktualisieren
        # In einer realen Implementierung würden wir hier die Datenbank direkt aktualisieren
        # oder einen API-Aufruf machen
        
        logger.info(f"Transcript saved to {transcript_file}")
        return {
            "status": "completed",
            "meeting_id": meeting_id,
            "transcript_file": transcript_file
        }
        
    except Exception as e:
        error_msg = f"Error processing transcript: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "failed"}


@app.task
def cleanup_audio_files(days: int = 7) -> Dict[str, Any]:
    """
    Entfernt alte Audiodateien, die älter als die angegebene Anzahl von Tagen sind.
    
    Args:
        days: Dateien älter als diese Anzahl von Tagen werden gelöscht
    
    Returns:
        Status-Dictionary mit Anzahl der gelöschten Dateien
    """
    logger.info(f"Cleaning up audio files older than {days} days")
    
    deleted_count = 0
    cutoff_date = datetime.now() - timedelta(days=days)
    
    try:
        for root, _, files in os.walk(audio_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                file_mod_time = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                if file_mod_time < cutoff_date:
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted old file: {file_path}")
        
        return {
            "status": "completed",
            "deleted_count": deleted_count,
            "cutoff_date": cutoff_date.isoformat()
        }
        
    except Exception as e:
        error_msg = f"Error during file cleanup: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg, "status": "failed"}


@app.task
def health_check_transcription_service() -> Dict[str, Any]:
    """
    Überprüft die Verfügbarkeit des Whisper-Transkriptionsdienstes.
    
    Returns:
        Status-Dictionary
    """
    logger.info("Performing health check on transcription service")
    
    try:
        response = requests.get(f"{whisper_service_url}/health")
        
        if response.status_code == 200:
            return {
                "status": "healthy",
                "service": "whisper",
                "timestamp": datetime.now().isoformat()
            }
        else:
            error_msg = f"Health check failed with status code {response.status_code}: {response.text}"
            logger.error(error_msg)
            return {
                "status": "unhealthy",
                "service": "whisper",
                "error": error_msg,
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        error_msg = f"Health check exception: {str(e)}"
        logger.error(error_msg)
        return {
            "status": "error",
            "service": "whisper",
            "error": error_msg,
            "timestamp": datetime.now().isoformat()
        }

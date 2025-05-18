import os
import sqlite3
from datetime import datetime
from typing import List, Optional, Dict, Any, Union

from models import Meeting, MeetingCreate, MeetingUpdate, TranscriptionJob, TranscriptionStatus


class Database:
    def __init__(self, db_path: str = "data/meetings.db"):
        self.db_path = db_path
        # Stellen Sie sicher, dass das Verzeichnis existiert
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        # Initialisiere die Datenbank, aber speichere keine Verbindung
        self.initialize_db()

    def get_connection(self):
        # Erstelle für jeden Aufruf eine neue Verbindung
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def close_connection(self, connection):
        # Schließe die übergebene Verbindung
        if connection:
            connection.close()

    def initialize_db(self):
        """Erstellt die Datenbanktabellen, falls sie nicht existieren."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            # Meetings Tabelle
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                date TEXT NOT NULL,
                link TEXT,
                audio_file TEXT,
                transcript TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            ''')

            # Transcription Jobs Tabelle
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS transcription_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                job_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (meeting_id) REFERENCES meetings (id)
            )
            ''')

            conn.commit()
        finally:
            self.close_connection(conn)

    # Meeting CRUD Operationen
    def create_meeting(self, meeting: MeetingCreate) -> Meeting:
        """Erstellt ein neues Meeting in der Datenbank."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
            INSERT INTO meetings (title, date, link, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                meeting.title,
                meeting.date.isoformat(),
                meeting.link,
                TranscriptionStatus.PENDING.value,
                now,
                now
            ))
            
            conn.commit()
            meeting_id = cursor.lastrowid
            
            return self.get_meeting(meeting_id)
        finally:
            self.close_connection(conn)

    def get_meeting(self, meeting_id: int) -> Optional[Meeting]:
        """Holt ein Meeting anhand seiner ID."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM meetings WHERE id = ?', (meeting_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return Meeting(
                id=row['id'],
                title=row['title'],
                date=datetime.fromisoformat(row['date']),
                link=row['link'],
                audio_file=row['audio_file'],
                transcript=row['transcript'],
                status=TranscriptionStatus(row['status']),
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at'])
            )
        finally:
            self.close_connection(conn)

    def get_all_meetings(self) -> List[Meeting]:
        """Holt alle Meetings aus der Datenbank."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM meetings ORDER BY date DESC')
            rows = cursor.fetchall()
            
            return [
                Meeting(
                    id=row['id'],
                    title=row['title'],
                    date=datetime.fromisoformat(row['date']),
                    link=row['link'],
                    audio_file=row['audio_file'],
                    transcript=row['transcript'],
                    status=TranscriptionStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                )
                for row in rows
            ]
        finally:
            self.close_connection(conn)

    def update_meeting(self, meeting_id: int, meeting_update: MeetingUpdate) -> Optional[Meeting]:
        """Aktualisiert ein bestehendes Meeting."""
        # Aktuelles Meeting holen
        current_meeting = self.get_meeting(meeting_id)
        if not current_meeting:
            return None
            
        # Update-Werte vorbereiten
        update_data = {}
        update_fields = []
        
        if meeting_update.title is not None:
            update_data['title'] = meeting_update.title
            update_fields.append('title = :title')
            
        if meeting_update.date is not None:
            update_data['date'] = meeting_update.date.isoformat()
            update_fields.append('date = :date')
            
        if meeting_update.link is not None:
            update_data['link'] = meeting_update.link
            update_fields.append('link = :link')
            
        if meeting_update.audio_file is not None:
            update_data['audio_file'] = meeting_update.audio_file
            update_fields.append('audio_file = :audio_file')
            
        if meeting_update.transcript is not None:
            update_data['transcript'] = meeting_update.transcript
            update_fields.append('transcript = :transcript')
            
        if meeting_update.status is not None:
            update_data['status'] = meeting_update.status.value
            update_fields.append('status = :status')
        
        # Wenn keine Änderungen, aktuelles Meeting zurückgeben
        if not update_fields:
            return current_meeting
            
        # Updated_at immer aktualisieren
        update_data['updated_at'] = datetime.now().isoformat()
        update_fields.append('updated_at = :updated_at')
        
        # Update-Query erstellen und ausführen
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            update_data['id'] = meeting_id
            query = f"UPDATE meetings SET {', '.join(update_fields)} WHERE id = :id"
            
            cursor.execute(query, update_data)
            conn.commit()
            
            return self.get_meeting(meeting_id)
        finally:
            self.close_connection(conn)

    def delete_meeting(self, meeting_id: int) -> bool:
        """Löscht ein Meeting aus der Datenbank."""
        # Prüfen, ob Meeting existiert
        if not self.get_meeting(meeting_id):
            return False
            
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Zuerst zugehörige Transcription Jobs löschen
            cursor.execute('DELETE FROM transcription_jobs WHERE meeting_id = ?', (meeting_id,))
            
            # Dann das Meeting löschen
            cursor.execute('DELETE FROM meetings WHERE id = ?', (meeting_id,))
            conn.commit()
            
            return True
        finally:
            self.close_connection(conn)

    # Transcription Job Operationen
    def create_transcription_job(self, meeting_id: int, job_id: str) -> TranscriptionJob:
        """Erstellt einen neuen Transcription Job."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            
            cursor.execute('''
            INSERT INTO transcription_jobs (meeting_id, job_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ''', (
                meeting_id,
                job_id,
                TranscriptionStatus.PENDING.value,
                now,
                now
            ))
            
            conn.commit()
            job_db_id = cursor.lastrowid
            
            # Meeting-Status aktualisieren
            self.update_meeting(
                meeting_id, 
                MeetingUpdate(status=TranscriptionStatus.PENDING)
            )
            
            return TranscriptionJob(
                id=job_db_id,
                meeting_id=meeting_id,
                job_id=job_id,
                status=TranscriptionStatus.PENDING,
                created_at=datetime.fromisoformat(now),
                updated_at=datetime.fromisoformat(now)
            )
        finally:
            self.close_connection(conn)

    def get_transcription_job(self, job_id: str) -> Optional[TranscriptionJob]:
        """Holt einen Transcription Job anhand seiner Job-ID."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM transcription_jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            return TranscriptionJob(
                id=row['id'],
                meeting_id=row['meeting_id'],
                job_id=row['job_id'],
                status=TranscriptionStatus(row['status']),
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(row['updated_at'])
            )
        finally:
            self.close_connection(conn)

    def update_transcription_job_status(self, job_id: str, status: TranscriptionStatus) -> Optional[TranscriptionJob]:
        """Aktualisiert den Status eines Transcription Jobs."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Job holen
            cursor.execute('SELECT * FROM transcription_jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()
            
            if not row:
                return None
                
            # Status aktualisieren
            now = datetime.now().isoformat()
            cursor.execute(
                'UPDATE transcription_jobs SET status = ?, updated_at = ? WHERE job_id = ?',
                (status.value, now, job_id)
            )
            conn.commit()
            
            # Meeting-Status auch aktualisieren
            meeting_id = row['meeting_id']
            self.update_meeting(
                meeting_id, 
                MeetingUpdate(status=status)
            )
            
            return TranscriptionJob(
                id=row['id'],
                meeting_id=meeting_id,
                job_id=job_id,
                status=status,
                created_at=datetime.fromisoformat(row['created_at']),
                updated_at=datetime.fromisoformat(now)
            )
        finally:
            self.close_connection(conn)

    def get_all_transcription_jobs(self) -> List[TranscriptionJob]:
        """Holt alle Transcription Jobs aus der Datenbank."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            cursor.execute('SELECT * FROM transcription_jobs ORDER BY created_at DESC')
            rows = cursor.fetchall()
            
            return [
                TranscriptionJob(
                    id=row['id'],
                    meeting_id=row['meeting_id'],
                    job_id=row['job_id'],
                    status=TranscriptionStatus(row['status']),
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at'])
                )
                for row in rows
            ]
        finally:
            self.close_connection(conn)

    def save_transcript(self, meeting_id: int, transcript: str) -> Optional[Meeting]:
        """Speichert ein Transkript für ein Meeting und aktualisiert den Status."""
        return self.update_meeting(
            meeting_id,
            MeetingUpdate(
                transcript=transcript,
                status=TranscriptionStatus.COMPLETED
            )
        )


# Singleton-Instanz für die Datenbank
db = Database()

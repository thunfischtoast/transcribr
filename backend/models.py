from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel


class TranscriptionStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Meeting(BaseModel):
    id: Optional[int] = None
    title: str
    date: datetime
    link: Optional[str] = None
    audio_file: Optional[str] = None
    transcript: Optional[str] = None
    status: TranscriptionStatus = TranscriptionStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class MeetingCreate(BaseModel):
    title: str
    date: datetime
    link: Optional[str] = None


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    date: Optional[datetime] = None
    link: Optional[str] = None
    audio_file: Optional[str] = None
    transcript: Optional[str] = None
    status: Optional[TranscriptionStatus] = None


class TranscriptionJob(BaseModel):
    id: Optional[int] = None
    meeting_id: int
    job_id: str
    status: TranscriptionStatus = TranscriptionStatus.PENDING
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

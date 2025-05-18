from typing import Union

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from task import dummy_task
from task import app as celery_app

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

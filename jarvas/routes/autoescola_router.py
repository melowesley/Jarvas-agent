"""
Router FastAPI para Autoescola Jarvas.
Endpoints para servir aulas, rastrear progresso e validar passos.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json

from jarvas.autoescola_data import LESSONS, validate_step

autoescola_router = APIRouter(prefix="/v1/autoescola", tags=["autoescola"])

# Models para requests/responses
class ProgressUpdate(BaseModel):
    lesson: int
    step: int
    validated: List[str]

class StepValidationRequest(BaseModel):
    lesson_id: int
    step_id: int
    user_command: str
    response: str

class ProgressResponse(BaseModel):
    lesson: int
    step: int
    validated: List[str]
    total_lessons: int
    total_steps_current: int


# Armazenamento em memória (em prod, usar MemPalace ou DB)
_progress_store = {}


@autoescola_router.get("/lessons")
async def get_lessons():
    """
    GET /v1/autoescola/lessons
    Retorna todas as aulas do curriculum.
    """
    return {
        "lessons": LESSONS,
        "total": len(LESSONS)
    }


@autoescola_router.get("/lessons/{lesson_id}")
async def get_lesson(lesson_id: int):
    """
    GET /v1/autoescola/lessons/{lesson_id}
    Retorna uma aula específica (1-6).
    """
    if lesson_id < 1 or lesson_id > len(LESSONS):
        raise HTTPException(status_code=404, detail="Aula não encontrada")

    lesson = LESSONS[lesson_id - 1]
    return {
        "lesson": lesson,
        "lesson_id": lesson_id,
        "total_steps": len(lesson["steps"])
    }


@autoescola_router.get("/progress")
async def get_progress(user_id: str = "default"):
    """
    GET /v1/autoescola/progress?user_id={user_id}
    Retorna progresso salvo do usuário.
    Se não houver progresso, retorna inicializado.
    """
    if user_id not in _progress_store:
        _progress_store[user_id] = {
            "lesson": 0,
            "step": 0,
            "validated": []
        }

    progress = _progress_store[user_id]
    current_lesson = LESSONS[progress["lesson"]] if progress["lesson"] < len(LESSONS) else LESSONS[0]

    return ProgressResponse(
        lesson=progress["lesson"],
        step=progress["step"],
        validated=progress["validated"],
        total_lessons=len(LESSONS),
        total_steps_current=len(current_lesson["steps"])
    )


@autoescola_router.post("/progress")
async def save_progress(data: ProgressUpdate, user_id: str = "default"):
    """
    POST /v1/autoescola/progress
    Salva progresso do usuário.
    Body: { "lesson": int, "step": int, "validated": [...] }
    """
    _progress_store[user_id] = {
        "lesson": data.lesson,
        "step": data.step,
        "validated": data.validated
    }

    return {
        "status": "success",
        "message": "Progresso salvo",
        "progress": _progress_store[user_id]
    }


@autoescola_router.post("/validate-step")
async def validate_step_endpoint(request: StepValidationRequest):
    """
    POST /v1/autoescola/validate-step
    Valida se um passo foi completado corretamente.

    Body: {
        "lesson_id": int,
        "step_id": int,
        "user_command": str,
        "response": str
    }

    Returns: {
        "valid": bool,
        "message": str,
        "hint": str (opcional),
        "nextStep": int (opcional)
    }
    """
    result = validate_step(
        request.lesson_id,
        request.step_id,
        request.user_command,
        request.response
    )

    if not result.get("valid"):
        raise HTTPException(
            status_code=400,
            detail={
                "valid": False,
                "message": result.get("message"),
                "hint": result.get("hint")
            }
        )

    return result


@autoescola_router.post("/reset-progress")
async def reset_progress(user_id: str = "default"):
    """
    POST /v1/autoescola/reset-progress
    Reseta o progresso do usuário para o começo.
    """
    _progress_store[user_id] = {
        "lesson": 0,
        "step": 0,
        "validated": []
    }

    return {
        "status": "success",
        "message": "Progresso resetado",
        "progress": _progress_store[user_id]
    }


@autoescola_router.get("/stats")
async def get_stats(user_id: str = "default"):
    """
    GET /v1/autoescola/stats?user_id={user_id}
    Retorna estatísticas de progresso.
    """
    if user_id not in _progress_store:
        return {
            "user_id": user_id,
            "lessons_completed": 0,
            "steps_completed": 0,
            "total_steps": sum(len(lesson["steps"]) for lesson in LESSONS),
            "completion_percent": 0
        }

    progress = _progress_store[user_id]
    total_steps = sum(len(lesson["steps"]) for lesson in LESSONS)
    completed_steps = len(progress["validated"])
    percent = round((completed_steps / total_steps) * 100, 1) if total_steps > 0 else 0

    return {
        "user_id": user_id,
        "current_lesson": progress["lesson"] + 1,
        "current_step": progress["step"] + 1,
        "lessons_completed": progress["lesson"],
        "steps_completed": completed_steps,
        "total_lessons": len(LESSONS),
        "total_steps": total_steps,
        "completion_percent": percent
    }


# Health check
@autoescola_router.get("/health")
async def health_check():
    """
    GET /v1/autoescola/health
    Verifica se o serviço está online.
    """
    return {
        "status": "ok",
        "lessons_loaded": len(LESSONS),
        "students_tracked": len(_progress_store)
    }

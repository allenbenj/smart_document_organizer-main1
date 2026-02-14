"""Agent management endpoints."""

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request, Depends

from agents import list_agent_types
from services.agent_service import AgentService
from .common import get_agent_service

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/agents")
async def get_agents() -> Dict[str, Any]:
    try:
        base = Path(__file__).resolve().parents[2] / "agents"
        files: List[str] = []
        try:
            for p in base.rglob("*.py"):
                if p.name == "__init__.py":
                    continue
                files.append(str(p.relative_to(base)))
        except Exception:
            pass
        return {"agents": list_agent_types(), "modules": sorted(files)}
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(status_code=500, detail="Failed to list agents")


@router.get("/agents/health")
async def get_agents_health(
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        health = await service.get_agent_status()
        return {"health": health}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent health: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent health")


@router.get("/agents/status/{agent_type}")
async def get_agent_status(
    agent_type: str,
    service: AgentService = Depends(get_agent_service)
) -> Dict[str, Any]:
    try:
        # For now, get full status and filter (service TODO: add specific agent status)
        full_status = await service.get_agent_status()
        agents = full_status.get("agents", {})
        
        # Check if agent exists in the status
        if agent_type in agents:
             return {"agent": agent_type, "status": agents[agent_type]}
        
        # If not in status, check if valid type
        if agent_type not in await service.get_available_agents():
             raise HTTPException(status_code=404, detail=f"Agent type {agent_type} not found")
             
        return {"agent": agent_type, "status": "unknown"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for {agent_type}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get agent status")

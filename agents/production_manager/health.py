"""Health and lifecycle behavior for ProductionAgentManager."""

from datetime import datetime
from typing import Any, Dict, List

from agents.core.models import AgentType

from .runtime import PRODUCTION_AGENTS_AVAILABLE


class HealthLifecycleMixin:
    async def get_agent_status(self, agent_type: AgentType) -> Dict[str, Any]:
        """Get the status of a specific agent."""
        if not self.is_initialized:
            return {
                "status": "not_initialized",
                "healthy": False,
                "error": "Production system not initialized",
            }

        try:
            agent = self.agents.get(agent_type)
            if not agent:
                return {
                    "status": "not_available",
                    "healthy": False,
                    "error": f"Agent {agent_type.value} not available",
                }

            if hasattr(agent, "health_check"):
                health_info = await agent.health_check()
                return {"status": "healthy", "healthy": True, "agent_info": health_info}
            return {
                "status": "available",
                "healthy": True,
                "agent_type": agent_type.value,
            }

        except Exception as e:
            return {"status": "error", "healthy": False, "error": str(e)}

    async def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health status."""
        health_status = {
            "system_initialized": self.is_initialized,
            "production_agents_available": PRODUCTION_AGENTS_AVAILABLE,
            "agents_status": {},
            "timestamp": datetime.now().isoformat(),
        }

        if self.is_initialized:
            for agent_type in AgentType:
                try:
                    status = await self.get_agent_status(agent_type)
                    health_status["agents_status"][agent_type.value] = status
                except Exception as e:
                    health_status["agents_status"][agent_type.value] = {
                        "status": "error",
                        "healthy": False,
                        "error": str(e),
                    }

        return health_status

    def get_available_agents(self) -> List[str]:
        """Get list of available agent types."""
        if not self.is_initialized:
            return []
        return [agent_type.value for agent_type in self.agents.keys()]

    async def shutdown(self):
        """Shutdown the agent manager and cleanup resources."""
        try:
            for agent in self.agents.values():
                if hasattr(agent, "shutdown"):
                    await agent.shutdown()

            if self.service_container and hasattr(self.service_container, "shutdown"):
                await self.service_container.shutdown()

            self.logger.info("Production agent manager shutdown complete")

        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")

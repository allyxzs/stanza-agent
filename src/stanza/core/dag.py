import asyncio
import time
from dataclasses import dataclass, field
from typing import Callable, Awaitable, Dict, List, Any, Set


@dataclass
class DAGTaskNode:
    node_id: str
    description: str
    handler: Callable[[Dict[str, Any]], Awaitable[Any]]
    dependencies: List[str] = field(default_factory=list)
    max_retries: int = 3
    status: str = "PENDING"  # PENDING, RUNNING, COMPLETED, FAILED, HEALED
    result: Any = None
    attempts: int = 0
    execution_time_ms: float = 0.0
    error: str = ""


class SelfHealingDAGOrchestrator:
    """
    Asynchronous Topological Task Graph (DAG) Engine with Cycle Detection,
    Parallel Layer Execution, and Autonomous Self-Healing Fallback Recovery.
    """

    def __init__(self, fallback_healer: Callable[[str, Exception, Dict[str, Any]], Awaitable[Any]] = None):
        self.nodes: Dict[str, DAGTaskNode] = {}
        self.fallback_healer = fallback_healer

    def add_node(self, node: DAGTaskNode) -> None:
        self.nodes[node.node_id] = node

    def validate_acyclic(self) -> bool:
        visited: Set[str] = set()
        visiting: Set[str] = set()

        def dfs(node_id: str) -> bool:
            visiting.add(node_id)
            for dep in self.nodes[node_id].dependencies:
                if dep not in self.nodes:
                    raise ValueError(f"Missing dependency '{dep}' required by '{node_id}'")
                if dep in visiting:
                    return False
                if dep not in visited:
                    if not dfs(dep):
                        return False
            visiting.remove(node_id)
            visited.add(node_id)
            return True

        for n_id in self.nodes:
            if n_id not in visited:
                if not dfs(n_id):
                    raise ValueError("Cycle detected in Stanza Execution DAG")
        return True

    def get_execution_layers(self) -> List[List[str]]:
        self.validate_acyclic()
        in_degree: Dict[str, int] = {n_id: len(node.dependencies) for n_id, node in self.nodes.items()}
        dependents: Dict[str, List[str]] = {n_id: [] for n_id in self.nodes}
        for n_id, node in self.nodes.items():
            for dep in node.dependencies:
                dependents[dep].append(n_id)

        current_layer = [n_id for n_id, deg in in_degree.items() if deg == 0]
        layers: List[List[str]] = []

        while current_layer:
            layers.append(current_layer)
            next_layer: List[str] = []
            for completed_id in current_layer:
                for child_id in dependents[completed_id]:
                    in_degree[child_id] -= 1
                    if in_degree[child_id] == 0:
                        next_layer.append(child_id)
            current_layer = next_layer

        return layers

    async def _execute_single_node(self, node: DAGTaskNode, shared_context: Dict[str, Any]) -> None:
        node.status = "RUNNING"
        start_t = time.perf_counter()

        while node.attempts < node.max_retries:
            node.attempts += 1
            try:
                output = await node.handler(shared_context)
                node.result = output
                node.status = "COMPLETED" if node.attempts == 1 else "HEALED"
                shared_context[node.node_id] = output
                node.execution_time_ms = round((time.perf_counter() - start_t) * 1000.0, 3)
                return
            except Exception as exc:
                node.error = str(exc)
                if node.attempts >= node.max_retries:
                    if self.fallback_healer is not None:
                        healed_output = await self.fallback_healer(node.node_id, exc, shared_context)
                        node.result = healed_output
                        node.status = "HEALED"
                        shared_context[node.node_id] = healed_output
                        node.execution_time_ms = round((time.perf_counter() - start_t) * 1000.0, 3)
                        return
                    node.status = "FAILED"
                    node.execution_time_ms = round((time.perf_counter() - start_t) * 1000.0, 3)
                    raise
                await asyncio.sleep(0.02 * node.attempts)

    async def execute(self, initial_context: Dict[str, Any] = None) -> Dict[str, Any]:
        context: Dict[str, Any] = dict(initial_context or {})
        layers = self.get_execution_layers()

        for layer in layers:
            await asyncio.gather(
                *(self._execute_single_node(self.nodes[n_id], context) for n_id in layer)
            )

        return {
            "context": context,
            "layers": layers,
            "telemetry": {
                n_id: {
                    "status": node.status,
                    "attempts": node.attempts,
                    "execution_time_ms": node.execution_time_ms,
                    "error": node.error,
                }
                for n_id, node in self.nodes.items()
            },
        }

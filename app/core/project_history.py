import copy
import json


class ProjectHistory:
    def __init__(self, limit: int = 60):
        self.limit = max(2, limit)
        self._snapshots: list[dict] = []
        self._index = -1

    @staticmethod
    def _signature(project: dict) -> str:
        return json.dumps(project, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    def reset(self, project: dict):
        self._snapshots = [copy.deepcopy(project)]
        self._index = 0

    def observe(self, project: dict) -> bool:
        if not self._snapshots:
            self.reset(project)
            return True
        if self._signature(project) == self._signature(self._snapshots[self._index]):
            return False
        del self._snapshots[self._index + 1 :]
        self._snapshots.append(copy.deepcopy(project))
        if len(self._snapshots) > self.limit:
            self._snapshots.pop(0)
        self._index = len(self._snapshots) - 1
        return True

    def undo(self, project: dict) -> dict | None:
        self.observe(project)
        if not self.can_undo():
            return None
        self._index -= 1
        return copy.deepcopy(self._snapshots[self._index])

    def redo(self) -> dict | None:
        if not self.can_redo():
            return None
        self._index += 1
        return copy.deepcopy(self._snapshots[self._index])

    def can_undo(self) -> bool:
        return self._index > 0

    def can_redo(self) -> bool:
        return 0 <= self._index < len(self._snapshots) - 1

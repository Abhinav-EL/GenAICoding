from threading import Lock
from typing import List, Sequence

"""
***** FIRST Prompt -- As an expert Python developer, what challenges do you see with the following python code?

tasks = []
def add_task(task): tasks.append(task) return f"Task '{task}' added."
def remove_task(task): if task in tasks: tasks.remove(task) return f"Task '{task}' removed." else: return "Task not found."
def list_tasks(): return tasks

Response:
Good question. That tiny snippet is OK for prototypes and demos, but it has a bunch of practical problems you’ll hit as soon
 as you use it in real code (concurrency, robustness, API design, persistence, testing, security, etc.). 
 Below I list the main issues (with short explanations) and then give a more robust replacement pattern you can use.

 
***** SECOND Prompt: what tests can you write in unittest format?
"""

MAX_TASK_LEN = 1024

class TaskValidationError(ValueError):
    pass

class TaskManager:
    def __init__(self):
        self._tasks: List[str] = []
        self._lock = Lock()

    def add_task(self, task: str) -> None:
        if not isinstance(task, str):
            raise TaskValidationError("task must be a string")
        task = task.strip()
        if not task:
            raise TaskValidationError("task cannot be empty")
        if len(task) > MAX_TASK_LEN:
            raise TaskValidationError("task too long")
        with self._lock:
            # optional: dedupe or use ids instead
            self._tasks.append(task)

    def remove_task(self, task: str) -> bool:
        if not isinstance(task, str):
            raise TaskValidationError("task must be a string")
        with self._lock:
            try:
                self._tasks.remove(task)
                return True
            except ValueError:
                return False

    def list_tasks(self) -> Sequence[str]:
        # return a shallow copy to avoid exposing internal mutable list
        with self._lock:
            return list(self._tasks)

    def clear(self) -> None:
        with self._lock:
            self._tasks.clear()

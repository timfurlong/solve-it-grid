"""In-memory stand-ins for Things and the Claude classifier."""

from dataclasses import replace

from factories import snapshot

from solve_it_grid.classifier import ClassifierError
from solve_it_grid.things_write import ThingsWriteError


class FakeThings:
    """Snapshot source and writer backed by one in-memory list of to-dos."""

    def __init__(self, todos=(), projects=(), apply_writes=True, fail_on=()):
        self.todos = {t.uuid: t for t in todos}
        self.projects = {p.uuid: p for p in projects}
        self.apply_writes = apply_writes
        self.fail_on = set(fail_on)
        self.calls = []

    def read(self, since):
        return snapshot(self.todos.values(), self.projects.values())

    def add_tag(self, uuid, tag):
        self._record("add_tag", uuid, tag)
        if self.apply_writes:
            t = self.todos[uuid]
            self.todos[uuid] = replace(t, tags=(*t.tags, tag))

    def set_todo_area(self, uuid, area_id):
        self._record("set_todo_area", uuid, area_id)
        if self.apply_writes:
            self.todos[uuid] = replace(self.todos[uuid], area_id=area_id)

    def set_project_area(self, uuid, area_id):
        self._record("set_project_area", uuid, area_id)
        if self.apply_writes:
            self.projects[uuid] = replace(self.projects[uuid], area_id=area_id)

    def _record(self, *call):
        if call[1] in self.fail_on:
            raise ThingsWriteError(f"things:///update failed for {call[1]} (exit 1)")
        self.calls.append(call)


class FakeClassifier:
    def __init__(self, color="green", area="work", error=None):
        self.color, self.area, self.error = color, area, error
        self.batches = []

    def classify(self, items):
        self.batches.append([i.uuid for i in items])
        if self.error:
            raise ClassifierError(self.error)
        return [{"uuid": i.uuid, "color": self.color if i.needs_color else None,
                 "area": self.area if i.needs_area else None, "reason": "r"} for i in items]


class LaggyThings(FakeThings):
    """Writes only become visible after `lag_reads` more reads, like Things catching up."""

    def __init__(self, *args, lag_reads=1, **kwargs):
        super().__init__(*args, apply_writes=False, **kwargs)
        self.lag_reads = lag_reads
        self.pending = []

    def add_tag(self, uuid, tag):
        self._record("add_tag", uuid, tag)
        self.pending.append((uuid, tag))

    def read(self, since):
        if self.pending and self.lag_reads <= 0:
            for uuid, tag in self.pending:
                t = self.todos[uuid]
                self.todos[uuid] = replace(t, tags=(*t.tags, tag))
            self.pending = []
        elif self.pending:
            self.lag_reads -= 1
        return super().read(since)

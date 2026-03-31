import threading
import pytest
from MyImpl.taskManager import TaskManager, TaskValidationError, MAX_TASK_LEN

# Fixtures
@pytest.fixture
def tm():
    t = TaskManager()
    yield t
    # ensure clean state between tests if TaskManager persists state somehow
    try:
        t.clear()
    except Exception:
        pass


# Basic operations
def test_add_and_list_basic(tm):
    tm.add_task("Buy milk")
    assert "Buy milk" in tm.list_tasks()
    assert isinstance(tm.list_tasks(), list)
    assert all(isinstance(x, str) for x in tm.list_tasks())


def test_add_strips_whitespace(tm):
    tm.add_task("  do laundry  ")
    assert "do laundry" in tm.list_tasks()
    assert "  do laundry  " not in tm.list_tasks()


@pytest.mark.parametrize("bad_value", [None, 123, 1.23, [], {}, object()])
def test_add_invalid_types_raise(tm, bad_value):
    with pytest.raises(TaskValidationError):
        tm.add_task(bad_value)


def test_add_empty_after_strip_raises(tm):
    with pytest.raises(TaskValidationError):
        tm.add_task("    ")


def test_add_too_long_raises(tm):
    too_long = "a" * (MAX_TASK_LEN + 1)
    with pytest.raises(TaskValidationError):
        tm.add_task(too_long)


# Remove operations
def test_remove_success(tm):
    tm.add_task("pay bills")
    assert tm.remove_task("pay bills") is True
    assert "pay bills" not in tm.list_tasks()


def test_remove_nonexistent_returns_false(tm):
    tm.add_task("clean")
    assert tm.remove_task("nonexistent") is False
    assert "clean" in tm.list_tasks()


def test_remove_invalid_type_raises(tm):
    with pytest.raises(TaskValidationError):
        tm.remove_task(None)


def test_duplicates_allowed_and_remove_removes_one(tm):
    tm.add_task("task")
    tm.add_task("task")
    tasks = tm.list_tasks()
    assert tasks.count("task") == 2
    assert tm.remove_task("task") is True
    assert tm.list_tasks().count("task") == 1


# List immutability and copy semantics
def test_list_tasks_returns_copy(tm):
    tm.add_task("a")
    snapshot = tm.list_tasks()
    snapshot.append("injected")
    # original internal list should not contain injected
    assert "injected" not in tm.list_tasks()


def test_clear(tm):
    tm.add_task("x")
    tm.add_task("y")
    tm.clear()
    assert tm.list_tasks() == []


# Unicode, control characters, and weird inputs
@pytest.mark.parametrize("weird", [
    "José", "👩‍💻", "Name\nWith\nNewlines", "Null\x00Char", "\"\\/<script>alert(1)</script>",
    "  spaced name  "
])
def test_weird_inputs_handled(tm, weird):
    # either valid (should be added) or raise if stripped-empty; ensure no crash
    if isinstance(weird, str) and weird.strip():
        tm.add_task(weird)
        assert weird.strip() in tm.list_tasks()
    else:
        with pytest.raises(TaskValidationError):
            tm.add_task(weird)


# Thread-safety / concurrency tests
def test_concurrent_additions_thread_safety(tm):
    num_threads = 8
    per_thread = 500
    threads = []
    errors = []
    errors_lock = threading.Lock()

    def worker(tid):
        try:
            for i in range(per_thread):
                tm.add_task(f"t{tid}-{i}")
        except Exception as e:
            with errors_lock:
                errors.append(e)

    for t in range(num_threads):
        th = threading.Thread(target=worker, args=(t,))
        threads.append(th)
        th.start()

    for th in threads:
        th.join()

    assert not errors, f"Exceptions occurred in threads: {errors}"
    all_tasks = tm.list_tasks()
    assert len(all_tasks) == num_threads * per_thread
    # verify some sample entries exist
    assert "t0-0" in all_tasks
    assert f"t{num_threads-1}-{per_thread-1}" in all_tasks


def test_concurrent_add_and_remove_no_data_corruption(tm):
    # Start threads that add and remove concurrently. Ensure no exceptions and data remains consistent (strings only, no None)
    num_threads = 6
    per_thread = 200
    add_threads = []
    remove_threads = []
    errors = []
    errors_lock = threading.Lock()

    # Prepare a base set of tasks to remove
    base_tasks = [f"base-{i}" for i in range(per_thread)]
    for task in base_tasks:
        tm.add_task(task)

    def adder(tid):
        try:
            for i in range(per_thread):
                tm.add_task(f"adder-{tid}-{i}")
        except Exception as e:
            with errors_lock:
                errors.append(e)

    def remover():
        try:
            for task in base_tasks:
                tm.remove_task(task)
        except Exception as e:
            with errors_lock:
                errors.append(e)

    for t in range(num_threads):
        at = threading.Thread(target=adder, args=(t,))
        add_threads.append(at)
        at.start()

    # Start multiple removers
    for _ in range(3):
        rt = threading.Thread(target=remover)
        remove_threads.append(rt)
        rt.start()

    for th in add_threads + remove_threads:
        th.join()

    assert not errors, f"Exceptions occurred in threads: {errors}"
    # Verify no None or non-string items present
    for item in tm.list_tasks():
        assert isinstance(item, str), f"Non-string in tasks: {item}"
    # All adder tasks are present or partially present but no corruption expected
    assert any(item.startswith("adder-") for item in tm.list_tasks())


# Defensive tests: ensure API doesn't accidentally mutate inputs
def test_inputs_are_copied_or_immutable(tm):
    s = "mutable-like"
    tm.add_task(s)
    s = s + "-changed"
    # stored value should not change after mutating original variable
    assert "mutable-like" in tm.list_tasks()


# Parametrized fuzz-ish short inputs to catch weird escaping/encoding problems
@pytest.mark.parametrize("payload", [
    "".join(chr((i % 95) + 32) for i in range(n)) for n in (1, 5, 10, 50)
] + ["\x00", "\x01", " ", "\t", "\n"])
def test_small_fuzz_inputs(tm, payload):
    if payload.strip():
        tm.add_task(payload)
        assert payload.strip() in tm.list_tasks()
    else:
        with pytest.raises(TaskValidationError):
            tm.add_task(payload)

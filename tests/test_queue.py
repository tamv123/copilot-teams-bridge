"""Tests for bridge/queue.py."""

import json
import os

from unittest.mock import patch

from bridge.queue import (
    acquire_copilot_lock,
    complete_task,
    enqueue,
    get_pending,
    load_queue,
    release_copilot_lock,
    save_queue,
)


class TestQueueOperations:
    def test_enqueue_and_get_pending(self, tmp_path):
        qf = str(tmp_path / "queue.json")
        with patch("bridge.queue.QUEUE_FILE", qf):
            task_id = enqueue("test task", "victor")
            pending = get_pending()

        assert task_id == 1
        assert len(pending) == 1
        assert pending[0]["text"] == "test task"
        assert pending[0]["status"] == "pending"

    def test_complete_task(self, tmp_path):
        qf = str(tmp_path / "queue.json")
        with patch("bridge.queue.QUEUE_FILE", qf):
            task_id = enqueue("task 1")
            complete_task(task_id, "result text", "completed")
            pending = get_pending()
            queue = load_queue()

        assert len(pending) == 0
        assert queue[0]["status"] == "completed"
        assert queue[0]["result"] == "result text"

    def test_multiple_tasks(self, tmp_path):
        qf = str(tmp_path / "queue.json")
        with patch("bridge.queue.QUEUE_FILE", qf):
            id1 = enqueue("first")
            id2 = enqueue("second")
            complete_task(id1, "done1")
            pending = get_pending()

        assert len(pending) == 1
        assert pending[0]["id"] == id2

    def test_empty_queue(self, tmp_path):
        qf = str(tmp_path / "nonexistent.json")
        with patch("bridge.queue.QUEUE_FILE", qf):
            assert load_queue() == []
            assert get_pending() == []

    def test_atomic_write(self, tmp_path):
        qf = str(tmp_path / "queue.json")
        with patch("bridge.queue.QUEUE_FILE", qf):
            enqueue("test")
        with open(qf) as f:
            data = json.load(f)
        assert len(data) == 1


class TestCopilotLock:
    def test_acquire_and_release(self, tmp_path):
        lock_file = str(tmp_path / "test.lock")
        with patch("bridge.queue.LOCK_FILE", lock_file):
            fd = acquire_copilot_lock()
            assert fd is not None
            release_copilot_lock(fd)

    def test_contention(self, tmp_path):
        lock_file = str(tmp_path / "test.lock")
        with patch("bridge.queue.LOCK_FILE", lock_file):
            fd1 = acquire_copilot_lock()
            assert fd1 is not None
            fd2 = acquire_copilot_lock()
            assert fd2 is None  # Lock already held
            release_copilot_lock(fd1)

"""Ansible playbook runner — subprocess with real-time output capture."""

import logging
import os
import subprocess
import threading

from core.config import REPO_ROOT
from core.db import append_operation_output, complete_operation

log = logging.getLogger("adm.ansible")

_run_lock = threading.Lock()
_current_process: subprocess.Popen | None = None
_current_op_id: int | None = None


def is_running() -> bool:
    return _current_process is not None and _current_process.poll() is None


def current_operation_id() -> int | None:
    return _current_op_id if is_running() else None


def cancel_current() -> bool:
    """Cancel the running playbook. Returns True if a process was terminated."""
    global _current_process
    if _current_process and _current_process.poll() is None:
        log.info(f"[ANSIBLE] Cancelling operation {_current_op_id}")
        _current_process.terminate()
        return True
    return False


def run_playbook(
    op_id: int,
    playbook: str,
    limit: str | None = None,
    extra_vars: dict | None = None,
    on_complete: callable = None,
) -> None:
    """Run an ansible-playbook in a background thread.

    Args:
        op_id: Operation ID for output tracking
        playbook: Playbook filename (relative to playbooks/)
        limit: --limit host pattern
        extra_vars: Extra variables passed via -e
        on_complete: Callback(success: bool, op_id: int) called when done
    """
    thread = threading.Thread(
        target=_run_playbook_thread,
        args=(op_id, playbook, limit, extra_vars, on_complete),
        daemon=True,
        name=f"ansible-op-{op_id}",
    )
    thread.start()


def _run_playbook_thread(
    op_id: int,
    playbook: str,
    limit: str | None,
    extra_vars: dict | None,
    on_complete: callable,
) -> None:
    global _current_process, _current_op_id

    if not _run_lock.acquire(blocking=False):
        log.warning(f"[ANSIBLE] Operation {op_id} rejected — another playbook is running")
        complete_operation(op_id, "failed", "Another operation is already running")
        if on_complete:
            on_complete(False, op_id)
        return

    try:
        _current_op_id = op_id
        playbook_path = os.path.join(REPO_ROOT, "playbooks", playbook)

        cmd = ["ansible-playbook", playbook_path]
        if limit:
            cmd.extend(["-l", limit])
        if extra_vars:
            for key, val in extra_vars.items():
                cmd.extend(["-e", f"{key}={val}"])

        env = os.environ.copy()
        env["ANSIBLE_NOCOLOR"] = "1"
        env["ANSIBLE_FORCE_COLOR"] = "0"
        env["PYTHONUNBUFFERED"] = "1"

        log.info(f"[ANSIBLE] Starting op {op_id}: {' '.join(cmd)}")
        append_operation_output(op_id, f"$ {' '.join(cmd)}\n\n")

        _current_process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=REPO_ROOT,
            env=env,
        )

        # Read output line by line
        buf = []
        for line in _current_process.stdout:
            buf.append(line)
            # Flush buffer to DB periodically
            if len(buf) >= 5 or line.strip() == "":
                append_operation_output(op_id, "".join(buf))
                buf.clear()

        # Flush remaining
        if buf:
            append_operation_output(op_id, "".join(buf))

        _current_process.wait()
        rc = _current_process.returncode
        success = rc == 0

        if success:
            log.info(f"[ANSIBLE] Op {op_id} completed successfully")
            complete_operation(op_id, "done")
        else:
            error_msg = f"Exit code {rc}"
            log.error(f"[ANSIBLE] Op {op_id} failed: {error_msg}")
            complete_operation(op_id, "failed", error_msg)

        if on_complete:
            on_complete(success, op_id)

    except Exception as e:
        log.error(f"[ANSIBLE] Op {op_id} exception: {e}")
        complete_operation(op_id, "failed", str(e))
        if on_complete:
            on_complete(False, op_id)
    finally:
        _current_process = None
        _current_op_id = None
        _run_lock.release()

"""Operations API — list, detail, cancel."""

import logging

from flask import Blueprint, jsonify, request

from core.ansible_runner import cancel_current, current_operation_id
from core.db import complete_operation, get_operation, get_operations

log = logging.getLogger("adm.operations")
bp = Blueprint("operations", __name__)


@bp.get("/api/operations")
def list_operations():
    """List recent operations."""
    limit = request.args.get("limit", 50, type=int)
    ops = get_operations(limit=min(limit, 200))
    return jsonify({"ok": True, "data": ops})


@bp.get("/api/operations/<int:op_id>")
def get_operation_detail(op_id: int):
    """Get operation detail including full ansible output."""
    op = get_operation(op_id)
    if not op:
        return jsonify({"ok": False, "error": "Operation not found"}), 404
    return jsonify({"ok": True, "data": op})


@bp.post("/api/operations/<int:op_id>/cancel")
def cancel_operation(op_id: int):
    """Cancel a running operation."""
    current = current_operation_id()
    if current != op_id:
        return jsonify({"ok": False, "error": "This operation is not currently running"}), 400

    if cancel_current():
        complete_operation(op_id, "cancelled", "Cancelled by user")
        log.info(f"[OPS] Operation {op_id} cancelled")
        return jsonify({"ok": True})

    return jsonify({"ok": False, "error": "Could not cancel operation"}), 500

#!/usr/bin/env python3

from pathlib import Path
import uuid
import threading
from datetime import datetime
import sqlite3
import yaml
import socket
import time
import os
import platform
import re
import shutil
import subprocess
import tempfile
from typing import Any
import sys
import signal
import json

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = Path(__file__).resolve().parent


def env_path(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    if not value:
        return default.expanduser()
    return Path(value).expanduser()


DB_PATH = env_path("MONOLITH_DB_PATH", ROOT / "data" / "llm-tests.sqlite")
MODELS_CONFIG = env_path("MONOLITH_MODELS_CONFIG", ROOT / "configs" / "models.yaml")
PROMPT_LIBRARY_ROOT = ROOT / "prompts"
PROMPT_SUITE_ROOT = PROMPT_LIBRARY_ROOT / "core-v2"

QUANT_LAB_ROOT = env_path("MONOLITH_QUANT_LAB_ROOT", ROOT / "quant-lab")
QUANT_LAB_RUNNER = QUANT_LAB_ROOT / "scripts" / "run-core-v2-suite.sh"
QUANT_LAB_RESULTS_DIR = QUANT_LAB_ROOT / "results"

CONTEXT_SCALING_DEFAULT_LADDER = [8192, 12288, 16384]
CONTEXT_SCALING_EXTENDED_LADDER = [24576, 32768]
CONTEXT_SCALING_DEFAULT_MAX_TOKENS = 800
CONTEXT_SCALING_DEFAULT_TEMP = 0.2
CONTEXT_SCALING_DEFAULT_PROMPTS = [
    "long-context/needle-mini.md",
    "docker/docker-dns-nftables-troubleshooting.md",
    "zfs/zfs-snapshot-rollback-procedure.md",
    "config/docker-compose-review.md",
    "honesty/unknown-tool-honesty.md",
]
EVAL_TASKS: dict[str, dict[str, Any]] = {}
EVAL_TASK_PROCESSES: dict[str, subprocess.Popen[Any]] = {}
EVAL_TASK_LOCK = threading.Lock()

APP_NAME = "Monolith"
APP_SUBTITLE = "Local AI Workbench"
APP_VERSION = "alpha v0.11.7"

app = FastAPI(title="Monolith")

app.mount(
    "/static",
    StaticFiles(directory=APP_DIR / "static"),
    name="static",
)

templates = Jinja2Templates(directory=APP_DIR / "templates")

templates.env.globals["APP_NAME"] = APP_NAME
templates.env.globals["APP_SUBTITLE"] = APP_SUBTITLE
templates.env.globals["APP_VERSION"] = APP_VERSION


def db_rows(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Database not found: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


def db_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    rows = db_rows(query, params)
    return rows[0] if rows else None

def classify_prompt_family(row: dict[str, Any]) -> str:
    notes = (row.get("notes") or "").lower()
    launcher = (row.get("launcher") or "").lower()
    prompt_category = (row.get("prompt_category") or "").lower()

    prompt_eval_tps = row.get("prompt_eval_tps")
    generation_tps = row.get("generation_tps")

    if prompt_eval_tps == 0 or generation_tps == 0:
        return "invalid-or-failed"

    if "prompt_eval=0.0" in notes or "generation=0.0" in notes:
        return "invalid-or-failed"

    if "gemma-long-context-needle-32k-small" in notes:
        return "small-needle"

    if "gemma-long-context-needle-32k" in notes:
        return "large-needle"

    if (
        prompt_category == "context-scaling"
        and "needle" not in notes
        and "auto-gemma" in launcher
    ):
        return "short-smoke"

    if "smoke test" in notes:
        return "manual-smoke"

    if prompt_category == "chat-web":
        return "chat-web"

    return "other"


def attach_prompt_family(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []

    for row in rows:
        item = dict(row)
        item["prompt_family"] = classify_prompt_family(item)
        out.append(item)

    return out


def average(values: list[float | int | None]) -> float | None:
    clean = [value for value in values if value is not None]

    if not clean:
        return None

    return sum(clean) / len(clean)


def summarize_by_family(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    families: dict[str, dict[str, Any]] = {}

    for row in rows:
        family = row.get("prompt_family") or "other"

        if family not in families:
            families[family] = {
                "family": family,
                "runs": 0,
                "avg_prompt_eval_tps": None,
                "avg_generation_tps": None,
                "max_vram_mb": None,
                "max_ctx_size": None,
                "_prompt_values": [],
                "_generation_values": [],
                "_vram_values": [],
                "_ctx_values": [],
            }

        group = families[family]
        group["runs"] += 1

        if row.get("prompt_eval_tps") is not None:
            group["_prompt_values"].append(row["prompt_eval_tps"])

        if row.get("generation_tps") is not None:
            group["_generation_values"].append(row["generation_tps"])

        if row.get("vram_peak_mb") is not None:
            group["_vram_values"].append(row["vram_peak_mb"])

        if row.get("ctx_size") is not None:
            group["_ctx_values"].append(row["ctx_size"])

    for group in families.values():
        group["avg_prompt_eval_tps"] = average(group["_prompt_values"])
        group["avg_generation_tps"] = average(group["_generation_values"])
        group["max_vram_mb"] = max(group["_vram_values"]) if group["_vram_values"] else None
        group["max_ctx_size"] = max(group["_ctx_values"]) if group["_ctx_values"] else None

        del group["_prompt_values"]
        del group["_generation_values"]
        del group["_vram_values"]
        del group["_ctx_values"]

    preferred_order = [
        "short-smoke",
        "small-needle",
        "large-needle",
        "manual-smoke",
        "chat-web",
        "invalid-or-failed",
        "other",
    ]

    return sorted(
        families.values(),
        key=lambda item: (
            preferred_order.index(item["family"])
            if item["family"] in preferred_order
            else 999
        ),
    )


def summarize_clean_context(rows: list[dict[str, Any]]) -> dict[str, Any]:
    valid_rows = [
        row for row in rows
        if row.get("prompt_family") != "invalid-or-failed"
    ]

    semantic_rows = [
        row for row in valid_rows
        if row.get("prompt_family") in {"small-needle", "large-needle"}
    ]

    semantic_48k_rows = [
        row for row in semantic_rows
        if row.get("ctx_size") == 49152
    ]

    return {
        "valid_context_runs": len(valid_rows),
        "semantic_context_runs": len(semantic_rows),
        "semantic_48k_runs": len(semantic_48k_rows),
        "max_valid_ctx_size": max(
            [row["ctx_size"] for row in valid_rows if row.get("ctx_size") is not None],
            default=None,
        ),
        "max_semantic_ctx_size": max(
            [row["ctx_size"] for row in semantic_rows if row.get("ctx_size") is not None],
            default=None,
        ),
        "avg_valid_generation_tps": average(
            [row.get("generation_tps") for row in valid_rows]
        ),
        "avg_semantic_generation_tps": average(
            [row.get("generation_tps") for row in semantic_rows]
        ),
        "max_valid_vram_mb": max(
            [row["vram_peak_mb"] for row in valid_rows if row.get("vram_peak_mb") is not None],
            default=None,
        ),
    }





def load_model_registry() -> dict[str, Any]:
    if not MODELS_CONFIG.exists():
        return {
            "models": {},
            "chat_profiles": {},
        }

    with MODELS_CONFIG.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    data.setdefault("models", {})
    data.setdefault("chat_profiles", {})

    return data


def model_path_status(model_path: str | None) -> dict[str, Any]:
    if not model_path:
        return {
            "configured": False,
            "exists": False,
            "path": None,
            "filename": None,
        }

    expanded = Path(model_path).expanduser()

    return {
        "configured": True,
        "exists": expanded.exists(),
        "path": str(expanded),
        "filename": expanded.name,
    }


def load_chat_profiles() -> dict[str, dict[str, Any]]:
    registry = load_model_registry()
    profiles = registry.get("chat_profiles", {}) or {}
    active_profiles: dict[str, dict[str, Any]] = {}

    for key, profile in profiles.items():
        if not profile or not profile.get("active", True):
            continue

        normalized = dict(profile)
        normalized.setdefault("label", key)
        normalized.setdefault("ctx_size", 8192)
        normalized.setdefault("batch_size", 256)
        normalized.setdefault("ubatch_size", 64)
        normalized.setdefault("gpu_layers", 999)

        active_profiles[key] = normalized

    for key, profile in load_generated_chat_profiles().items():
        if key in active_profiles:
            continue
        active_profiles[key] = profile

    return active_profiles


def resolve_profile_launcher(profile: dict[str, Any]) -> str:
    launcher = str(profile.get("launcher") or "").strip()
    return launcher or LLAMA_COMPLETION


def launcher_exists(launcher: str) -> bool:
    if "/" in launcher:
        return Path(launcher).expanduser().exists()

    from shutil import which

    return which(launcher) is not None


def profile_extra_args(profile: dict[str, Any]) -> list[str]:
    extra_args = profile.get("extra_args") or []

    if not isinstance(extra_args, list):
        return []

    safe_args: list[str] = []

    for item in extra_args:
        value = str(item).strip()

        if not value:
            continue

        if "\x00" in value or "\n" in value or "\r" in value:
            continue

        safe_args.append(value)

    return safe_args


def load_models_for_page() -> list[dict[str, Any]]:
    registry = load_model_registry()
    models = registry.get("models", {}) or {}
    chat_profiles = registry.get("chat_profiles", {}) or {}

    rows: list[dict[str, Any]] = []

    for key, model in models.items():
        item = dict(model or {})
        item["key"] = key
        item["kind"] = "model"
        item["active"] = item.get("active")
        item["experimental"] = item.get("status") == "experimental"
        item["path_status"] = model_path_status(item.get("model") or item.get("gguf_path"))
        rows.append(item)

    for key, profile in chat_profiles.items():
        item = dict(profile or {})
        item["key"] = key
        item["display_name"] = item.get("label", key)
        item["family"] = item.get("model_family") or item.get("family")
        item["kind"] = "chat_profile"
        item["path_status"] = model_path_status(item.get("model") or item.get("gguf_path"))
        rows.append(item)

    return rows


def model_registry_tables_exist() -> bool:
    if not DB_PATH.exists():
        return False

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'local_model_files'
            """
        ).fetchall()

    return len(rows) == 1


def approved_model_inventory_roots() -> list[Path]:
    configured = os.environ.get("MONOLITH_MODEL_INVENTORY_ROOTS")

    if configured:
        return [
            Path(item).expanduser()
            for item in configured.split(":")
            if item.strip()
        ]

    return [
        Path.home() / "Monolith/models",
    ]


def is_inventory_model_file(path: Path) -> bool:
    if path.suffix.lower() != ".gguf":
        return False

    name = path.name.lower()

    if name.startswith("ggml-vocab-"):
        return False

    if name.startswith("mmproj-") or "mmproj" in name:
        return False

    try:
        size_bytes = path.stat().st_size
    except OSError:
        return False

    # Avoid tokenizer/vocab fixtures and other tiny GGUF support files.
    if size_bytes < 100 * 1024 * 1024:
        return False

    return True


def guess_model_family_from_filename(filename: str) -> str | None:
    name = filename.lower()

    family_markers = [
        ("qwen", "Qwen"),
        ("gemma", "Gemma"),
        ("llama", "Llama"),
        ("mistral", "Mistral"),
        ("mixtral", "Mixtral"),
        ("phi", "Phi"),
        ("deepseek", "DeepSeek"),
        ("nemotron", "Nemotron"),
        ("lfm", "LFM"),
        ("falcon", "Falcon"),
        ("mellum", "Mellum"),
    ]

    for marker, label in family_markers:
        if marker in name:
            return label

    return None


def guess_architecture_from_filename(filename: str) -> str | None:
    name = filename.lower()

    if "a3b" in name or "a4b" in name or "moe" in name:
        return "MoE"

    if "instruct" in name or "-it-" in name or name.endswith("-it.gguf"):
        return "Instruct"

    if "reasoning" in name:
        return "Reasoning"

    return None


def guess_quant_from_filename(filename: str) -> str | None:
    stem = Path(filename).stem
    patterns = [
        r"(UD-[A-Z0-9_]+)",
        r"(IQ[0-9]_[A-Z0-9_]+)",
        r"(Q[0-9]_[A-Z0-9_]+)",
        r"(Q[0-9]_K_[A-Z])",
        r"(Q[0-9]_K)",
        r"(Q[0-9])",
        r"(F16)",
        r"(BF16)",
    ]

    for pattern in patterns:
        match = re.search(pattern, stem, flags=re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def registered_model_usage_by_path() -> dict[str, dict[str, Any]]:
    registry = load_model_registry()
    models = registry.get("models", {}) or {}
    chat_profiles = registry.get("chat_profiles", {}) or {}

    usage: dict[str, dict[str, Any]] = {}

    for key, model in models.items():
        model_path = (model or {}).get("model") or (model or {}).get("gguf_path")
        if not model_path:
            continue

        resolved = str(Path(model_path).expanduser())
        usage.setdefault(
            resolved,
            {
                "registered_model_key": None,
                "registered_profile_keys": [],
            },
        )
        usage[resolved]["registered_model_key"] = key

    for key, profile in chat_profiles.items():
        model_path = (profile or {}).get("model") or (profile or {}).get("gguf_path")
        if not model_path:
            continue

        resolved = str(Path(model_path).expanduser())
        usage.setdefault(
            resolved,
            {
                "registered_model_key": None,
                "registered_profile_keys": [],
            },
        )
        usage[resolved]["registered_profile_keys"].append(key)

    return usage


def scan_local_model_inventory() -> dict[str, Any]:
    if not model_registry_tables_exist():
        raise HTTPException(status_code=500, detail="Model Registry tables not found. Run migration first.")

    roots = approved_model_inventory_roots()
    usage = registered_model_usage_by_path()

    discovered: list[dict[str, Any]] = []

    for root in roots:
        expanded_root = root.expanduser()

        if not expanded_root.exists() or not expanded_root.is_dir():
            continue

        for path in sorted(expanded_root.rglob("*.gguf")):
            if not is_inventory_model_file(path):
                continue

            try:
                stat = path.stat()
            except OSError:
                continue

            local_path = str(path.expanduser())
            registered = usage.get(local_path) or {}
            profile_keys = sorted(registered.get("registered_profile_keys") or [])

            discovered.append(
                {
                    "scan_root": str(expanded_root),
                    "local_path": local_path,
                    "filename": path.name,
                    "size_bytes": int(stat.st_size),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "family_guess": guess_model_family_from_filename(path.name),
                    "quant_guess": guess_quant_from_filename(path.name),
                    "architecture_guess": guess_architecture_from_filename(path.name),
                    "registered_model_key": registered.get("registered_model_key"),
                    "registered_profile_keys_json": json_dumps_compact(profile_keys),
                    "status": "registered" if registered else "discovered",
                    "notes": None,
                }
            )

    now = current_timestamp_local()

    with sqlite3.connect(DB_PATH) as conn:
        for item in discovered:
            conn.execute(
                """
                INSERT INTO local_model_files (
                    created_at,
                    updated_at,
                    scan_root,
                    local_path,
                    filename,
                    size_bytes,
                    modified_at,
                    family_guess,
                    quant_guess,
                    architecture_guess,
                    registered_model_key,
                    registered_profile_keys_json,
                    status,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(local_path) DO UPDATE SET
                    updated_at = excluded.updated_at,
                    scan_root = excluded.scan_root,
                    filename = excluded.filename,
                    size_bytes = excluded.size_bytes,
                    modified_at = excluded.modified_at,
                    family_guess = excluded.family_guess,
                    quant_guess = excluded.quant_guess,
                    architecture_guess = excluded.architecture_guess,
                    registered_model_key = excluded.registered_model_key,
                    registered_profile_keys_json = excluded.registered_profile_keys_json,
                    status = excluded.status,
                    notes = excluded.notes
                """,
                (
                    now,
                    now,
                    item["scan_root"],
                    item["local_path"],
                    item["filename"],
                    item["size_bytes"],
                    item["modified_at"],
                    item["family_guess"],
                    item["quant_guess"],
                    item["architecture_guess"],
                    item["registered_model_key"],
                    item["registered_profile_keys_json"],
                    item["status"],
                    item["notes"],
                ),
            )

        conn.commit()

    return {
        "ok": True,
        "scanned_roots": [str(root.expanduser()) for root in roots],
        "discovered_count": len(discovered),
    }


class CreateLocalModelChatProfileRequest(BaseModel):
    profile_key: str | None = None
    label: str | None = None
    launcher: str | None = None
    ctx_size: int = 8192
    batch_size: int = 256
    ubatch_size: int = 64
    gpu_layers: int = 999
    temperature: float = 0.2
    max_tokens: int = 800
    reasoning: str = "off"
    extra_args: list[str] | None = None


def safe_generated_profile_key(value: str) -> str:
    key = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    key = re.sub(r"-+", "-", key).strip("-_")
    return key[:80] or "local-model"


def unique_generated_profile_key(base_key: str) -> str:
    yaml_profiles = (load_model_registry().get("chat_profiles", {}) or {})
    key = safe_generated_profile_key(base_key)

    suffix = 2
    candidate = key

    while True:
        generated_match = None

        if generated_chat_profiles_table_exists():
            generated_match = db_one(
                "SELECT id FROM generated_chat_profiles WHERE profile_key = ?",
                (candidate,),
            )

        if candidate not in yaml_profiles and not generated_match:
            return candidate

        candidate = f"{key}-{suffix}"
        suffix += 1


def create_generated_chat_profile_from_local_model(
    model_id: int,
    payload: CreateLocalModelChatProfileRequest | None = None,
) -> dict[str, Any]:
    if payload is None:
        payload = CreateLocalModelChatProfileRequest()

    if not generated_chat_profiles_table_exists():
        raise HTTPException(
            status_code=500,
            detail="generated_chat_profiles table is missing. Run scripts/migrate_generated_chat_profiles.py.",
        )

    row = db_one(
        """
        SELECT *
        FROM local_model_files
        WHERE id = ?
        """,
        (model_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail=f"Local model not found: {model_id}")

    model_path = str(row.get("local_path") or "").strip()

    if not model_path:
        raise HTTPException(status_code=400, detail="Local model has no path.")

    if not Path(model_path).expanduser().exists():
        raise HTTPException(status_code=400, detail=f"Model file no longer exists: {model_path}")

    existing = db_one(
        """
        SELECT *
        FROM generated_chat_profiles
        WHERE model_path = ?
          AND active = 1
        ORDER BY id ASC
        LIMIT 1
        """,
        (model_path,),
    )

    if existing:
        return {
            "created": False,
            "profile_key": existing["profile_key"],
            "profile_id": existing["id"],
            "model_path": existing["model_path"],
            "message": "A generated chat profile already exists for this model.",
        }

    filename = str(row.get("filename") or Path(model_path).name)
    stem = Path(filename).stem
    family = row.get("family_guess") or "Local"
    quant = row.get("quant_guess") or "GGUF"

    requested_key = payload.profile_key or f"local-{stem}"
    profile_key = unique_generated_profile_key(requested_key)
    label = payload.label or f"{family} {quant} ({filename})"
    launcher = str(payload.launcher or LLAMA_COMPLETION).strip()

    extra_args = profile_extra_args({"extra_args": payload.extra_args if payload.extra_args is not None else []})

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO generated_chat_profiles (
                profile_key,
                label,
                model_path,
                launcher,
                ctx_size,
                batch_size,
                ubatch_size,
                gpu_layers,
                temperature,
                max_tokens,
                reasoning,
                extra_args_json,
                source,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """,
            (
                profile_key,
                label,
                model_path,
                launcher,
                max(1024, min(int(payload.ctx_size or 8192), 131072)),
                max(1, int(payload.batch_size or 256)),
                max(1, int(payload.ubatch_size or 64)),
                int(payload.gpu_layers if payload.gpu_layers is not None else 999),
                float(payload.temperature if payload.temperature is not None else 0.2),
                max(64, min(int(payload.max_tokens or 800), 8192)),
                str(payload.reasoning or "off"),
                json.dumps(extra_args),
                "local_inventory",
            ),
        )
        conn.execute(
            """
            UPDATE local_model_files
            SET status = 'registered',
                registered_profile_keys_json = ?,
                notes = COALESCE(notes, 'Registered through generated SQLite chat profile.'),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                json.dumps([profile_key]),
                model_id,
            ),
        )
        conn.commit()
        profile_id = int(cursor.lastrowid)

    return {
        "created": True,
        "profile_key": profile_key,
        "profile_id": profile_id,
        "model_path": model_path,
        "launcher": launcher,
        "extra_args": extra_args,
    }


def generated_chat_profiles_table_exists() -> bool:
    if not DB_PATH.exists():
        return False

    row = db_one(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'generated_chat_profiles'
        """
    )

    return bool(row)


def load_generated_chat_profiles() -> dict[str, dict[str, Any]]:
    if not generated_chat_profiles_table_exists():
        return {}

    rows = db_rows(
        """
        SELECT *
        FROM generated_chat_profiles
        WHERE active = 1
        ORDER BY label ASC, profile_key ASC
        """
    )

    profiles: dict[str, dict[str, Any]] = {}

    for row in rows:
        try:
            extra_args = json.loads(row.get("extra_args_json") or "[]")
        except Exception:
            extra_args = []

        if not isinstance(extra_args, list):
            extra_args = []

        key = str(row["profile_key"])

        profiles[key] = {
            "label": row.get("label") or key,
            "active": bool(row.get("active")),
            "model": row.get("model_path"),
            "launcher": row.get("launcher"),
            "ctx_size": int(row.get("ctx_size") or 8192),
            "batch_size": int(row.get("batch_size") or 256),
            "ubatch_size": int(row.get("ubatch_size") or 64),
            "gpu_layers": int(row.get("gpu_layers") or 999),
            "temperature": float(row.get("temperature") or 0.2),
            "max_tokens": int(row.get("max_tokens") or 800),
            "reasoning": row.get("reasoning") or "off",
            "extra_args": extra_args,
            "source": row.get("source") or "generated",
            "generated_profile_id": row.get("id"),
            "notes": [
                "Generated from local model inventory.",
                "Stored in SQLite, not configs/models.yaml.",
            ],
        }

    return profiles


def generated_chat_profile_keys_by_model_path() -> dict[str, list[str]]:
    if not generated_chat_profiles_table_exists():
        return {}

    rows = db_rows(
        """
        SELECT profile_key, model_path
        FROM generated_chat_profiles
        WHERE active = 1
        ORDER BY profile_key ASC
        """
    )

    mapping: dict[str, list[str]] = {}

    for row in rows:
        model_path = str(row.get("model_path") or "")
        profile_key = str(row.get("profile_key") or "")

        if not model_path or not profile_key:
            continue

        mapping.setdefault(model_path, []).append(profile_key)

    return mapping


def load_local_model_inventory(limit: int = 200) -> dict[str, Any]:
    empty = {
        "available": False,
        "rows": [],
        "count": 0,
        "registered_count": 0,
        "unregistered_count": 0,
        "total_size_bytes": 0,
        "approved_roots": [str(root.expanduser()) for root in approved_model_inventory_roots()],
    }

    if not model_registry_tables_exist():
        return empty

    rows = db_rows(
        """
        SELECT *
        FROM local_model_files
        ORDER BY size_bytes DESC, filename ASC
        LIMIT ?
        """,
        (limit,),
    )

    generated_profile_map = generated_chat_profile_keys_by_model_path()

    for row in rows:
        try:
            row["registered_profile_keys"] = __import__("json").loads(row.get("registered_profile_keys_json") or "[]")
        except Exception:
            row["registered_profile_keys"] = []

        generated_profile_keys = generated_profile_map.get(str(row.get("local_path") or ""), [])
        row["generated_profile_keys"] = generated_profile_keys

        if generated_profile_keys:
            combined_keys = list(dict.fromkeys(row["registered_profile_keys"] + generated_profile_keys))
            row["registered_profile_keys"] = combined_keys

            if row.get("status") == "discovered":
                row["status"] = "registered"

            row["notes"] = row.get("notes") or "Registered through generated SQLite chat profile."

        size_bytes = row.get("size_bytes") or 0
        row["size_gib"] = round(float(size_bytes) / (1024 ** 3), 2)

    registered_count = sum(1 for row in rows if row.get("status") == "registered")
    total_size_bytes = sum(int(row.get("size_bytes") or 0) for row in rows)

    return {
        "available": True,
        "rows": rows,
        "count": len(rows),
        "registered_count": registered_count,
        "unregistered_count": len(rows) - registered_count,
        "total_size_bytes": total_size_bytes,
        "total_size_gib": round(float(total_size_bytes) / (1024 ** 3), 2),
        "approved_roots": [str(root.expanduser()) for root in approved_model_inventory_roots()],
    }


def huggingface_json_request(url: str, timeout_seconds: int = 12) -> Any:
    import json
    import urllib.error
    import urllib.request

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Monolith-Local-AI-Workbench/alpha",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=502,
            detail=f"Hugging Face request failed with HTTP {exc.code}: {detail[:500]}",
        ) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Hugging Face request failed: {exc.reason}",
        ) from exc


def safe_huggingface_repo_id(repo_id: str) -> str:
    repo_id = repo_id.strip()

    if not repo_id or "/" not in repo_id:
        raise ValueError("Invalid Hugging Face repo id")

    if ".." in repo_id or repo_id.startswith("/") or repo_id.endswith("/"):
        raise ValueError("Invalid Hugging Face repo id")

    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_. /")
    if any(char not in allowed for char in repo_id):
        raise ValueError("Invalid Hugging Face repo id")

    return repo_id.replace(" ", "")


def load_local_model_filenames() -> set[str]:
    if not model_registry_tables_exist():
        return set()

    rows = db_rows(
        """
        SELECT filename
        FROM local_model_files
        WHERE status IN ('registered', 'discovered')
        """,
    )

    return {row["filename"].lower() for row in rows if row.get("filename")}


def normalize_huggingface_file_size(value: Any) -> int | None:
    if isinstance(value, int):
        return value

    if isinstance(value, float):
        return int(value)

    return None


def huggingface_sibling_size_bytes(sibling: dict[str, Any]) -> int | None:
    direct_size = normalize_huggingface_file_size(
        sibling.get("size") or sibling.get("size_bytes")
    )
    if direct_size is not None:
        return direct_size

    lfs = sibling.get("lfs")
    if isinstance(lfs, dict):
        return normalize_huggingface_file_size(
            lfs.get("size") or lfs.get("size_bytes")
        )

    return None


def huggingface_model_info(repo_id: str) -> dict[str, Any]:
    import urllib.parse

    safe_repo_id = safe_huggingface_repo_id(repo_id)
    encoded_repo_id = urllib.parse.quote(safe_repo_id, safe="/")
    url = f"https://huggingface.co/api/models/{encoded_repo_id}"

    data = huggingface_json_request(url)
    if not isinstance(data, dict):
        return {}

    return data


def search_huggingface_gguf_models(query: str, limit: int = 10) -> dict[str, Any]:
    import urllib.parse

    query = (query or "").strip()
    if len(query) < 2:
        raise HTTPException(status_code=400, detail="Search query must be at least 2 characters.")

    bounded_limit = max(1, min(int(limit or 10), 20))
    repo_limit = min(bounded_limit, 10)

    search_params = urllib.parse.urlencode(
        {
            "search": query,
            "limit": repo_limit,
        }
    )
    search_url = f"https://huggingface.co/api/models?{search_params}"

    search_data = huggingface_json_request(search_url)
    if not isinstance(search_data, list):
        raise HTTPException(status_code=502, detail="Unexpected Hugging Face search response.")

    local_filenames = load_local_model_filenames()
    candidates: list[dict[str, Any]] = []

    for item in search_data:
        if not isinstance(item, dict):
            continue

        repo_id = item.get("id") or item.get("modelId")
        if not repo_id:
            continue

        try:
            info = huggingface_model_info(str(repo_id))
        except HTTPException:
            continue
        except ValueError:
            continue

        siblings = info.get("siblings") or []
        if not isinstance(siblings, list):
            continue

        for sibling in siblings:
            if not isinstance(sibling, dict):
                continue

            filename = sibling.get("rfilename") or sibling.get("filename")
            if not filename or not str(filename).lower().endswith(".gguf"):
                continue

            filename = str(filename)
            basename = Path(filename).name

            if basename.lower().startswith("mmproj-") or "mmproj" in basename.lower():
                continue

            size_bytes = huggingface_sibling_size_bytes(sibling)

            candidates.append(
                {
                    "repo_id": str(repo_id),
                    "filename": filename,
                    "basename": basename,
                    "family_guess": guess_model_family_from_filename(basename),
                    "quant_guess": guess_quant_from_filename(basename),
                    "architecture_guess": guess_architecture_from_filename(basename),
                    "size_bytes": size_bytes,
                    "size_gib": round(float(size_bytes) / (1024 ** 3), 2) if size_bytes else None,
                    "local_match": basename.lower() in local_filenames,
                    "download_url": f"https://huggingface.co/{repo_id}/resolve/main/{urllib.parse.quote(filename)}",
                    "repo_url": f"https://huggingface.co/{repo_id}",
                }
            )

    candidates.sort(
        key=lambda row: (
            not row["local_match"],
            row["repo_id"].lower(),
            row["basename"].lower(),
        )
    )

    return {
        "ok": True,
        "query": query,
        "repo_limit": repo_limit,
        "candidate_count": len(candidates),
        "candidates": candidates[:100],
        "policy": {
            "metadata_only": True,
            "downloads_enabled": False,
            "config_edits_enabled": False,
            "model_execution_enabled": False,
        },
    }


LLAMA_COMPLETION = os.environ.get(
    "MONOLITH_LLAMA_COMPLETION",
    str(ROOT / "llama.cpp" / "build" / "bin" / "llama-completion"),
)
LLAMA_TOKENIZE = os.environ.get(
    "MONOLITH_LLAMA_TOKENIZE",
    str(ROOT / "llama.cpp" / "build" / "bin" / "llama-tokenize"),
)

GEMMA_12B_Q5 = os.environ.get(
    "MONOLITH_GEMMA_12B_Q5",
    str(ROOT / "models" / "gemma-4-12b-it-UD-Q5_K_XL.gguf"),
)

QWEN35B_A3B = os.environ.get(
    "MONOLITH_QWEN35B_A3B",
    str(ROOT / "models" / "Qwen3.6-35B-A3B-UD-IQ2_M.gguf"),
)

CHAT_PROFILES = load_chat_profiles()


def current_chat_profiles() -> dict[str, dict[str, Any]]:
    return load_chat_profiles()


class EvalRunRequest(BaseModel):
    profile: str
    ctx_size: int = 8192
    max_tokens: int = 600
    temperature: float = 0.2
    include: str = ""


class ContextScalingRunRequest(BaseModel):
    profile: str
    contexts: list[int] = [8192, 12288, 16384]
    prompts: list[str] = []
    max_tokens: int = 800
    temperature: float = 0.2


class AgentBackendEvalSingleRunRequest(BaseModel):
    profile: str
    prompt: str
    ctx_size: int = 8192
    max_tokens: int = 800
    temperature: float = 0.2


class ChatRequest(BaseModel):
    profile: str
    prompt: str
    max_tokens: int = 2048
    mode: str = "auto"


class SaveChatRunRequest(BaseModel):
    profile: str
    mode: str = "auto"
    prompt: str
    response: str
    max_tokens: int = 2048
    elapsed_seconds: float | None = None
    prompt_tokens: int | None = None
    output_tokens: int | None = None
    prompt_eval_tps: float | None = None
    generation_tps: float | None = None
    vram_peak_mib: int | None = None
    notes: str | None = None



class ScoreRunRequest(BaseModel):
    factual_accuracy: int | None = None
    technical_correctness: int | None = None
    safety: int | None = None
    instruction_following: int | None = None
    concision: int | None = None
    hallucination_severity: int | None = None
    overall_trust: int | None = None
    winner_tag: str | None = None
    notes: str | None = None


def build_chat_prompt(user_prompt: str, mode: str = "auto") -> str:
    mode = (mode or "auto").lower().strip()

    if mode == "raw":
        return user_prompt

    if mode == "creative":
        return f"""You are a local writing assistant.

Behavior:
- Produce the requested creative, social, or writing output directly.
- Do not add technical setup instructions unless explicitly requested.
- Keep the output concise when the user asks for social posts, haiku, captions, or short text.
- Do not explain the prompt unless asked.

User:
{user_prompt}

Assistant:
"""

    if mode == "technical":
        return f"""You are a conservative technical AI assistant running locally through Monolith.

Behavior for technical tasks:
- Be precise.
- Prefer stable, reversible changes.
- Do not invent package names, commands, flags, paths, files, APIs, or facts.
- When unsure, say exactly what to verify.
- For Linux, Arch, Sway, Docker, ZFS, networking, homelab, llama.cpp, and local LLM tasks, include verification and rollback when relevant.
- Avoid hype.

User:
{user_prompt}

Assistant:
"""

    return f"""You are a local AI assistant running through Monolith.

Default behavior:
- Answer the user's actual request directly.
- Do not force technical troubleshooting structure onto unrelated prompts.
- If the user asks for creative writing, social posts, haiku, casual text, summaries, or brainstorming, provide that output directly with no unnecessary system-administration framing.
- If the user asks a simple question, answer simply.

For technical Linux, Arch, Sway, Docker, ZFS, networking, homelab, llama.cpp, local LLM, or system-change prompts:
- Be technically precise.
- Prefer stable, reversible changes.
- Do not invent package names, commands, files, paths, flags, or facts.
- When unsure, say what to verify.
- Include verification and rollback steps when the task could affect system stability or data.

For non-technical prompts:
- Do not mention verification, rollback, system stability, Linux, homelab, or local workstation details unless relevant.
- Do not turn the request into a technical checklist.

User:
{user_prompt}

Assistant:
"""


def clean_model_response(text: str) -> str:
    """
    Clean llama.cpp / model-template artifacts before displaying in the web UI.
    """
    cleaned = text.strip()

    # If the model emitted explicit channels, prefer the final/assistant channel.
    final_markers = [
        "<|channel|>final",
        "<|channel|>assistant",
        "<|final|>",
    ]

    for marker in final_markers:
        if marker in cleaned:
            cleaned = cleaned.split(marker)[-1]

    # Remove Qwen-style reasoning blocks.
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<think>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</think>", "", cleaned, flags=re.IGNORECASE)

    # Remove common control/template tokens.
    replacements = [
        "<|channel|>thought",
        "<|channel|>analysis",
        "<|channel|>final",
        "<|channel|>assistant",
        "<|channel|>commentary",
        "<|message|>",
        "<|end|>",
        "<|start|>",
        "<|start_header_id|>",
        "<|end_header_id|>",
        "<|eot_id|>",
        "<end_of_turn>",
        "[end of text]",
    ]

    for marker in replacements:
        cleaned = cleaned.replace(marker, "")

    # Remove normal and malformed channel/control artifacts.
    cleaned = re.sub(r"<\|[^|]+?\|>", "", cleaned)
    cleaned = re.sub(r"<\s*/?\s*channel\s*\|?\s*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\s*\|?\s*channel\s*\|?\s*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*channel\s*\|?\s*", "", cleaned, flags=re.IGNORECASE)

    # Remove leftover leading channel labels.
    cleaned = re.sub(
        r"^\s*(thought|analysis|final|assistant|commentary)\s*\n+",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Remove leading role labels if emitted.
    cleaned = re.sub(r"^\s*Assistant:\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*assistant\s*:\s*", "", cleaned, flags=re.IGNORECASE)

    # If the model echoed Assistant:, keep only the final assistant section.
    if "Assistant:" in cleaned:
        cleaned = cleaned.split("Assistant:")[-1]

    # Remove llama.cpp stats if they leak into stdout.
    cleaned = re.sub(r"\[\s*Prompt:.*?\]", "", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\[\s*Generation:.*?\]", "", cleaned, flags=re.DOTALL)

    # Collapse whitespace.
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = re.sub(r"[ \t]+\n", "\n", cleaned)

    return cleaned.strip()



def parse_llama_perf(stderr_text: str) -> dict[str, Any]:
    """
    Extract llama.cpp speed stats if present.

    Supports both older compact tok/s output and newer common_perf_print lines
    such as:
      prompt eval time = ... ( ..., 3912.60 tokens per second)
      eval time        = ... ( ..., 188.80 tokens per second)
    """
    prompt_tps = None
    generation_tps = None

    prompt_patterns = [
        r"^.*prompt eval time\s*=.*?\(.*?,\s*([0-9.]+)\s*tokens per second\)",
        r"prompt eval time\s*=.*?([0-9.]+)\s*tokens per second",
        r"prompt eval.*?([0-9.]+)\s*tok/s",
    ]

    generation_patterns = [
        r"^.*(?<!prompt )eval time\s*=.*?\(.*?,\s*([0-9.]+)\s*tokens per second\)",
        r"(?<!prompt )eval time\s*=.*?([0-9.]+)\s*tokens per second",
        r"generation.*?([0-9.]+)\s*tok/s",
    ]

    for pattern in prompt_patterns:
        match = re.search(pattern, stderr_text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            prompt_tps = float(match.group(1))
            break

    for pattern in generation_patterns:
        matches = re.findall(pattern, stderr_text, flags=re.IGNORECASE | re.MULTILINE)
        if matches:
            generation_tps = float(matches[-1])
            break

    return {
        "prompt_eval_tps": prompt_tps,
        "generation_tps": generation_tps,
    }



def estimate_tokens(value: str | None) -> int | None:
    """
    Conservative fallback token estimate for dashboard chat runs.

    llama.cpp timing output is not always available from llama-completion.
    This estimate is for dashboard comparison only, not benchmark-grade scoring.
    """
    if not value:
        return None

    text_value = value.strip()

    if not text_value:
        return None

    # Rough LLM token estimate: words plus punctuation/structure overhead.
    word_count = len(re.findall(r"\S+", text_value))
    char_estimate = max(1, round(len(text_value) / 4))
    word_estimate = max(1, round(word_count * 1.3))

    return max(char_estimate, word_estimate)


def fallback_generation_tps(output_tokens: int | None, elapsed_seconds: float | None) -> float | None:
    if not output_tokens or not elapsed_seconds or elapsed_seconds <= 0:
        return None

    return round(output_tokens / elapsed_seconds, 2)



def llama_token_count(model_path: str | None, value: str | None) -> tuple[int | None, str]:
    """
    Count tokens using llama.cpp's llama-tokenize.

    Token counting must never crash Chat. If llama-tokenize emits invalid
    bytes, fails, times out, or the model path is unavailable, fall back to
    the rough estimator.
    """
    if not value or not value.strip():
        return None, "empty"

    if not model_path:
        return estimate_tokens(value), "estimated-no-model-path"

    if not Path(LLAMA_TOKENIZE).exists():
        return estimate_tokens(value), "estimated-no-llama-tokenize"

    if not Path(model_path).exists():
        return estimate_tokens(value), "estimated-model-missing"

    cmd = [
        LLAMA_TOKENIZE,
        "-m", model_path,
        "-p", value,
    ]

    try:
        completed = subprocess.run(
            cmd,
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=60,
        )
    except subprocess.TimeoutExpired:
        return estimate_tokens(value), "estimated-tokenizer-timeout"
    except Exception:
        return estimate_tokens(value), "estimated-tokenizer-exception"

    try:
        stdout_text = completed.stdout.decode("utf-8", errors="replace")
        stderr_text = completed.stderr.decode("utf-8", errors="replace")
    except Exception:
        return estimate_tokens(value), "estimated-tokenizer-decode-error"

    if completed.returncode != 0:
        return estimate_tokens(value), "estimated-tokenizer-error"

    combined = stdout_text + "\n" + stderr_text

    # Token lines look like:
    #      2 -> '<bos>'
    #  54593 -> 'Tell'
    token_lines = re.findall(r"^\s*-?\d+\s+->\s+", combined, flags=re.MULTILINE)

    if not token_lines:
        return estimate_tokens(value), "estimated-tokenizer-parse-failed"

    return len(token_lines), "llama-tokenize"

def sample_total_gpu_vram_mib() -> int | None:
    """
    Sample total used VRAM on the first NVIDIA GPU.

    This is intentionally total GPU memory, not just llama.cpp process memory.
    It matches the dashboard's system-level VRAM view.
    """
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if completed.returncode != 0 or not completed.stdout.strip():
        return None

    try:
        return int(float(completed.stdout.strip().splitlines()[0].strip()))
    except ValueError:
        return None


def run_command_capture_with_vram(cmd: list[str], timeout: int = 300) -> dict[str, Any]:
    """
    Run llama-completion while sampling peak total VRAM.

    stdout/stderr are written to temp files to avoid pipe-buffer deadlocks
    during long generations.
    """
    started_at = time.monotonic()
    peak_vram_mib = sample_total_gpu_vram_mib()
    timed_out = False

    with tempfile.NamedTemporaryFile(mode="w+b") as stdout_file, tempfile.NamedTemporaryFile(mode="w+b") as stderr_file:
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=stdout_file,
            stderr=stderr_file,
            text=False,
        )

        try:
            while True:
                returncode = process.poll()

                current_vram = sample_total_gpu_vram_mib()
                if current_vram is not None:
                    peak_vram_mib = current_vram if peak_vram_mib is None else max(peak_vram_mib, current_vram)

                if returncode is not None:
                    break

                if time.monotonic() - started_at > timeout:
                    timed_out = True
                    process.kill()
                    process.wait(timeout=10)
                    break

                time.sleep(0.5)
        finally:
            elapsed_seconds = round(time.monotonic() - started_at, 2)

        stdout_file.seek(0)
        stderr_file.seek(0)

        stdout_text = stdout_file.read().decode("utf-8", errors="replace")
        stderr_text = stderr_file.read().decode("utf-8", errors="replace")

    return {
        "returncode": -9 if timed_out else process.returncode,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "elapsed_seconds": elapsed_seconds,
        "vram_peak_mib": peak_vram_mib,
        "timed_out": timed_out,
    }


def run_llama_chat(profile_name: str, prompt: str, max_tokens: int, mode: str = "auto") -> dict[str, Any]:
    safe_max_tokens = max(64, min(int(max_tokens), 8192))
    full_prompt = build_chat_prompt(prompt, mode=mode)

    profiles = current_chat_profiles()

    if profile_name not in profiles:
        detail = f"Unknown profile: {profile_name}"
        run_id = save_failed_chat_run(
            profile_name=profile_name,
            prompt=prompt,
            full_prompt=full_prompt,
            mode=mode,
            max_tokens=safe_max_tokens,
            error_reason=detail,
            http_status=400,
            exit_code=400,
        )
        if run_id:
            detail = f"{detail}\nFailed run saved as #{run_id}."
        raise HTTPException(status_code=400, detail=detail)

    profile = profiles[profile_name]
    model_path = profile["model"]
    launcher = resolve_profile_launcher(profile)

    if not launcher_exists(launcher):
        detail = f"llama.cpp launcher not found: {launcher}"
        run_id = save_failed_chat_run(
            profile_name=profile_name,
            prompt=prompt,
            full_prompt=full_prompt,
            mode=mode,
            max_tokens=safe_max_tokens,
            error_reason=detail,
            http_status=500,
            exit_code=127,
        )
        if run_id:
            detail = f"{detail}\nFailed run saved as #{run_id}."
        raise HTTPException(status_code=500, detail=detail)

    if not Path(model_path).exists():
        detail = f"Model not found: {model_path}"
        run_id = save_failed_chat_run(
            profile_name=profile_name,
            prompt=prompt,
            full_prompt=full_prompt,
            mode=mode,
            max_tokens=safe_max_tokens,
            error_reason=detail,
            http_status=500,
            exit_code=2,
        )
        if run_id:
            detail = f"{detail}\nFailed run saved as #{run_id}."
        raise HTTPException(status_code=500, detail=detail)

    cmd = [
        launcher,
        "-m", model_path,
        "-ngl", str(profile.get("gpu_layers", 999)),
        "-c", str(profile["ctx_size"]),
        "-b", str(profile.get("batch_size", 256)),
        "-ub", str(profile.get("ubatch_size", 64)),
        "--reasoning", str(profile.get("reasoning", "off")),
        "-no-cnv",
        "--no-display-prompt",
        "-n", str(safe_max_tokens),
        "-p", full_prompt,
    ]

    cmd.extend(profile_extra_args(profile))

    result = run_command_capture_with_vram(cmd, timeout=300)

    elapsed_seconds = result["elapsed_seconds"]
    response_text = clean_model_response(result["stdout"])
    perf = parse_llama_perf(result["stderr"])

    try:
        prompt_tokens, prompt_token_method = llama_token_count(model_path, full_prompt)
    except Exception:
        prompt_tokens, prompt_token_method = estimate_tokens(full_prompt), "estimated-token-count-exception"

    try:
        output_tokens, output_token_method = llama_token_count(model_path, response_text)
    except Exception:
        output_tokens, output_token_method = estimate_tokens(response_text), "estimated-token-count-exception"

    token_count_method = (
        "llama-tokenize"
        if prompt_token_method == "llama-tokenize" and output_token_method == "llama-tokenize"
        else f"prompt={prompt_token_method};output={output_token_method}"
    )

    if perf["generation_tps"] is None:
        perf["generation_tps"] = fallback_generation_tps(output_tokens, elapsed_seconds)

    if result.get("timed_out"):
        detail = "llama-completion timed out after 300 seconds"
        run_id = save_failed_chat_run(
            profile_name=profile_name,
            prompt=prompt,
            full_prompt=full_prompt,
            mode=mode,
            max_tokens=safe_max_tokens,
            error_reason=detail,
            result=result,
            response_text=response_text,
            http_status=504,
            exit_code=result.get("returncode", -9),
        )
        if run_id:
            detail = (
                f"{detail}\nFailed run saved as #{run_id}. "
                f"Peak VRAM: {result.get('vram_peak_mib')} MiB. "
                f"Elapsed: {elapsed_seconds}s."
            )
        raise HTTPException(status_code=504, detail=detail)

    if result["returncode"] != 0:
        detail = result["stderr"].strip() or response_text or "llama-completion failed"
        detail = detail[-4000:]
        run_id = save_failed_chat_run(
            profile_name=profile_name,
            prompt=prompt,
            full_prompt=full_prompt,
            mode=mode,
            max_tokens=safe_max_tokens,
            error_reason=detail,
            result=result,
            response_text=response_text,
            http_status=500,
            exit_code=result.get("returncode"),
        )
        if run_id:
            detail = (
                f"llama-completion exited with code {result.get('returncode')}.\n"
                f"Failed run saved as #{run_id}.\n"
                f"Peak VRAM: {result.get('vram_peak_mib')} MiB.\n"
                f"Elapsed: {elapsed_seconds}s.\n\n"
                f"{detail}"
            )
        raise HTTPException(status_code=500, detail=detail)

    return {
        "profile": profile_name,
        "label": profile["label"],
        "ctx_size": profile["ctx_size"],
        "mode": mode,
        "response": response_text,
        "elapsed_seconds": elapsed_seconds,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "prompt_eval_tps": perf["prompt_eval_tps"],
        "generation_tps": perf["generation_tps"],
        "vram_peak_mib": result["vram_peak_mib"],
        "token_count_method": token_count_method,
        "stderr_tail": result["stderr"][-2000:],
    }




# ---------------------------------------------------------------------------
# Agent Lab helpers
# ---------------------------------------------------------------------------

def agent_lab_rows(query: str, params: tuple = ()) -> list[dict]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]


def load_agent_sessions(include_closed: bool = False) -> list[dict]:
    if include_closed:
        return agent_lab_rows(
            """
            SELECT *
            FROM agent_sessions
            ORDER BY datetime(created_at) DESC, id DESC
            """
        )

    return agent_lab_rows(
        """
        SELECT *
        FROM agent_sessions
        WHERE closed_at IS NULL
        ORDER BY datetime(created_at) DESC, id DESC
        """
    )


def archive_agent_session(session_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE agent_sessions
            SET closed_at = COALESCE(closed_at, datetime('now')),
                status = CASE
                    WHEN status = 'draft' THEN 'archived'
                    ELSE status
                END,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (session_id,),
        )
        conn.commit()
        return cursor.rowcount > 0


def load_agent_session(session_id: int) -> dict | None:
    rows = agent_lab_rows(
        """
        SELECT *
        FROM agent_sessions
        WHERE id = ?
        """,
        (session_id,),
    )
    return rows[0] if rows else None


def load_agent_session_related(session_id: int) -> dict:
    return {
        "plans": agent_lab_rows(
            """
            SELECT *
            FROM agent_plans
            WHERE session_id = ?
            ORDER BY version DESC, id DESC
            """,
            (session_id,),
        ),
        "proposals": agent_lab_rows(
            """
            SELECT *
            FROM agent_action_proposals
            WHERE session_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (session_id,),
        ),
        "reviews": agent_lab_rows(
            """
            SELECT *
            FROM agent_reviews
            WHERE session_id = ?
            ORDER BY datetime(created_at) DESC, id DESC
            """,
            (session_id,),
        ),
    }



def load_agent_model_profiles() -> list[dict]:
    profiles = load_chat_profiles()
    normalized = []

    for name, profile in profiles.items():
        normalized.append(
            {
                "name": name,
                "label": profile.get("label") or profile.get("name") or name,
            }
        )

    return normalized

def create_agent_session(
    *,
    name: str,
    goal: str,
    model_profile_name: str | None,
    mode: str,
    workspace_label: str | None,
    workspace_path: str | None,
    context_summary: str | None,
    safety_notes: str | None,
) -> int:
    allowed_modes = {"read_only", "proposal_only", "review_only"}
    if mode not in allowed_modes:
        mode = "proposal_only"

    model_label = None
    if model_profile_name:
        for profile in load_agent_model_profiles():
            if profile.get("name") == model_profile_name:
                model_label = profile.get("label") or profile.get("name")
                break

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_sessions (
                name,
                goal,
                model_profile_name,
                model_label,
                mode,
                status,
                workspace_label,
                workspace_path,
                context_summary,
                safety_notes,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'draft', ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (
                name.strip(),
                goal.strip(),
                model_profile_name or None,
                model_label,
                mode,
                workspace_label.strip() if workspace_label else None,
                workspace_path.strip() if workspace_path else None,
                context_summary.strip() if context_summary else None,
                safety_notes.strip() if safety_notes else None,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def setup_status_payload() -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def add_check(status: str, label: str, detail: str, next_action: str) -> None:
        checks.append(
            {
                "status": status,
                "label": label,
                "detail": detail,
                "next_action": next_action,
            }
        )

    db_exists = DB_PATH.exists()
    config_exists = MODELS_CONFIG.exists()
    example_config = ROOT / "configs" / "models.example.yaml"
    example_config_exists = example_config.exists()

    required_tables = {
        "runs": "Run scripts/init_db.py.",
        "local_model_files": "Run scripts/migrate_model_registry.py.",
        "model_download_jobs": "Run scripts/migrate_model_downloader.py.",
        "generated_chat_profiles": "Run scripts/migrate_generated_chat_profiles.py.",
        "context_scaling_runs": "Run scripts/migrate_context_scaling.py.",
        "hermes_eval_runs": "Run scripts/migrate_hermes_eval.py.",
        "agent_sessions": "Run scripts/migrate_agent_lab.py.",
    }

    table_status: dict[str, bool] = {}

    if db_exists:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
                existing_tables = {row[0] for row in rows}

            table_status = {
                table_name: table_name in existing_tables
                for table_name in required_tables
            }
        except Exception as exc:
            add_check(
                "error",
                "Database readable",
                f"Database exists but could not be inspected: {exc}",
                "Check database permissions or recreate the database from the documented setup commands.",
            )
    else:
        table_status = {table_name: False for table_name in required_tables}

    add_check(
        "ok" if db_exists else "error",
        "Database file",
        f"{DB_PATH}",
        "Run python scripts/init_db.py." if not db_exists else "No action needed.",
    )

    for table_name, next_action in required_tables.items():
        exists = table_status.get(table_name, False)
        add_check(
            "ok" if exists else "error",
            f"Database table: {table_name}",
            "Present." if exists else "Missing.",
            "No action needed." if exists else next_action,
        )

    add_check(
        "ok" if config_exists else "error",
        "Models config",
        f"{MODELS_CONFIG}",
        "Copy configs/models.example.yaml to configs/models.yaml and edit local paths."
        if not config_exists
        else "No action needed.",
    )

    add_check(
        "ok" if example_config_exists else "error",
        "Example models config",
        f"{example_config}",
        "Restore configs/models.example.yaml from the repository."
        if not example_config_exists
        else "No action needed.",
    )

    inventory_roots = []
    existing_inventory_roots = 0

    try:
        for root in approved_model_inventory_roots():
            root_exists = root.exists()
            existing_inventory_roots += 1 if root_exists else 0
            inventory_roots.append(
                {
                    "path": str(root),
                    "exists": root_exists,
                }
            )
    except Exception as exc:
        add_check(
            "warn",
            "Model inventory roots",
            f"Could not inspect inventory roots: {exc}",
            "Check MONOLITH_MODEL_INVENTORY_ROOTS.",
        )

    if inventory_roots:
        add_check(
            "ok" if existing_inventory_roots else "warn",
            "Model inventory root paths",
            f"{existing_inventory_roots} of {len(inventory_roots)} configured roots exist.",
            "Create the model directory or set MONOLITH_MODEL_INVENTORY_ROOTS."
            if not existing_inventory_roots
            else "No action needed.",
        )
    else:
        add_check(
            "warn",
            "Model inventory root paths",
            "No inventory roots configured.",
            "Set MONOLITH_MODEL_INVENTORY_ROOTS or use the default ~/Monolith/models path.",
        )

    gguf_count = 0
    for root_info in inventory_roots:
        root = Path(root_info["path"])
        if root.exists():
            try:
                gguf_count += sum(1 for _ in root.rglob("*.gguf"))
            except Exception:
                pass

    add_check(
        "ok" if gguf_count else "warn",
        "Local GGUF files",
        f"{gguf_count} GGUF files found in configured inventory roots.",
        "Place GGUF files under an inventory root or configure a correct model directory."
        if not gguf_count
        else "No action needed.",
    )

    generated_profile_count = 0
    if db_exists and table_status.get("generated_chat_profiles", False):
        try:
            with sqlite3.connect(DB_PATH) as conn:
                generated_profile_count = conn.execute(
                    "SELECT COUNT(*) FROM generated_chat_profiles"
                ).fetchone()[0]
        except Exception:
            generated_profile_count = 0

    yaml_profile_count = 0
    try:
        yaml_profile_count = len(load_model_profiles())
    except Exception:
        yaml_profile_count = 0

    total_profile_count = yaml_profile_count + generated_profile_count

    add_check(
        "ok" if total_profile_count else "warn",
        "Chat profiles",
        f"{yaml_profile_count} YAML profiles and {generated_profile_count} generated profiles available.",
        "Configure a YAML profile or create a generated chat profile from a discovered local model."
        if not total_profile_count
        else "No action needed.",
    )

    llama_completion_path = Path(LLAMA_COMPLETION).expanduser()
    llama_tokenize_path = Path(LLAMA_TOKENIZE).expanduser()
    llama_completion_exists = llama_completion_path.exists()
    llama_tokenize_exists = llama_tokenize_path.exists()

    add_check(
        "ok" if llama_completion_exists else "warn",
        "llama.cpp completion binary",
        f"{llama_completion_path}",
        "Set MONOLITH_LLAMA_COMPLETION or build/install llama.cpp."
        if not llama_completion_exists
        else "No action needed.",
    )

    add_check(
        "ok" if llama_tokenize_exists else "warn",
        "llama.cpp tokenize binary",
        f"{llama_tokenize_path}",
        "Set MONOLITH_LLAMA_TOKENIZE or build/install llama.cpp."
        if not llama_tokenize_exists
        else "No action needed.",
    )

    quant_lab_exists = QUANT_LAB_ROOT.exists()
    add_check(
        "ok" if quant_lab_exists else "warn",
        "Quant Lab root",
        f"{QUANT_LAB_ROOT}",
        "Set MONOLITH_QUANT_LAB_ROOT or create the expected Quant Lab directory if using eval imports."
        if not quant_lab_exists
        else "No action needed.",
    )

    download_root = Path(os.environ.get("MONOLITH_MODEL_DOWNLOAD_ROOT", str(Path.home() / "Monolith" / "models" / "huggingface"))).expanduser()
    download_root_exists = download_root.exists()
    add_check(
        "ok" if download_root_exists else "warn",
        "Model download root",
        f"{download_root}",
        "Create this directory before starting downloads, or set MONOLITH_MODEL_DOWNLOAD_ROOT."
        if not download_root_exists
        else "No action needed.",
    )

    counts = {
        "total": len(checks),
        "ok": sum(1 for check in checks if check["status"] == "ok"),
        "warn": sum(1 for check in checks if check["status"] == "warn"),
        "error": sum(1 for check in checks if check["status"] == "error"),
    }

    if counts["error"]:
        overall_status = "error"
        summary = "Setup is incomplete. Fix error items before normal use."
    elif counts["warn"]:
        overall_status = "warn"
        summary = "Setup is usable but has warnings."
    else:
        overall_status = "ok"
        summary = "Setup checks passed."

    return {
        "overall_status": overall_status,
        "summary": summary,
        "counts": counts,
        "checks": checks,
        "paths": {
            "root": str(ROOT),
            "database": str(DB_PATH),
            "models_config": str(MODELS_CONFIG),
            "quant_lab_root": str(QUANT_LAB_ROOT),
            "download_root": str(download_root),
        },
        "database": {
            "status": "ok" if db_exists else "error",
            "path": str(DB_PATH),
            "exists": db_exists,
            "tables": table_status,
        },
        "models_config": {
            "status": "ok" if config_exists else "error",
            "path": str(MODELS_CONFIG),
            "exists": config_exists,
            "example_path": str(example_config),
            "example_exists": example_config_exists,
        },
        "inventory": {
            "roots": inventory_roots,
            "gguf_count": gguf_count,
        },
        "profiles": {
            "yaml_count": yaml_profile_count,
            "generated_count": generated_profile_count,
            "total_count": total_profile_count,
        },
        "llama_cpp": {
            "completion": str(llama_completion_path),
            "completion_exists": llama_completion_exists,
            "tokenize": str(llama_tokenize_path),
            "tokenize_exists": llama_tokenize_exists,
        },
    }


@app.get("/api/setup/status")
def api_setup_status():
    return setup_status_payload()


@app.get("/setup", response_class=HTMLResponse)
def setup_status_page(request: Request):
    return templates.TemplateResponse(
        request,
        "setup.html",
        {
            "title": "Setup Status",
            "setup": setup_status_payload(),
        },
    )


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    summary = db_one(
        """
        SELECT
            COUNT(*) AS runs,
            SUM(CASE WHEN COALESCE(r.exit_code, 0) = 0 THEN 1 ELSE 0 END) AS successful_runs,
            SUM(CASE WHEN r.exit_code IS NOT NULL AND r.exit_code != 0 THEN 1 ELSE 0 END) AS failed_runs,
            SUM(CASE WHEN EXISTS (SELECT 1 FROM scores s WHERE s.run_id = r.id) THEN 1 ELSE 0 END) AS scored_runs,
            SUM(CASE WHEN NOT EXISTS (SELECT 1 FROM scores s WHERE s.run_id = r.id) THEN 1 ELSE 0 END) AS unscored_runs,
            ROUND(AVG(r.generation_tps), 2) AS avg_generation_tps,
            ROUND(AVG(r.prompt_eval_tps), 2) AS avg_prompt_eval_tps,
            MAX(r.vram_peak_mb) AS max_vram_mb,
            MAX(r.ctx_size) AS max_ctx_size
        FROM runs r
        """
    )

    latest_success = db_one(
        """
        SELECT
            r.id,
            r.timestamp_local,
            r.profile_name,
            r.model_display_name,
            r.prompt_category,
            r.ctx_size,
            r.generation_tps,
            r.total_wall_seconds,
            r.vram_peak_mb,
            r.exit_code,
            s.overall_trust,
            s.winner_tag,
            r.notes
        FROM runs r
        LEFT JOIN scores s ON s.run_id = r.id
        WHERE COALESCE(r.exit_code, 0) = 0
        ORDER BY r.id DESC
        LIMIT 1
        """
    )

    latest_failed = db_one(
        """
        SELECT
            r.id,
            r.timestamp_local,
            r.profile_name,
            r.model_display_name,
            r.prompt_category,
            r.ctx_size,
            r.generation_tps,
            r.total_wall_seconds,
            r.vram_peak_mb,
            r.exit_code,
            s.overall_trust,
            s.winner_tag,
            r.notes
        FROM runs r
        LEFT JOIN scores s ON s.run_id = r.id
        WHERE r.exit_code IS NOT NULL AND r.exit_code != 0
        ORDER BY r.id DESC
        LIMIT 1
        """
    )

    recent = db_rows(
        """
        SELECT
            r.id,
            r.timestamp_local,
            r.launcher,
            r.profile_name,
            r.model_display_name,
            r.prompt_category,
            r.ctx_size,
            r.prompt_tokens,
            r.output_tokens,
            r.prompt_eval_tps,
            r.generation_tps,
            r.total_wall_seconds,
            r.vram_peak_mb,
            r.exit_code,
            s.overall_trust,
            s.winner_tag,
            r.notes
        FROM runs r
        LEFT JOIN scores s ON s.run_id = r.id
        ORDER BY r.id DESC
        LIMIT 8
        """
    )
    recent = attach_prompt_family(recent)

    family_rows = db_rows(
        """
        SELECT
            id,
            launcher,
            prompt_category,
            ctx_size,
            prompt_eval_tps,
            generation_tps,
            vram_peak_mb,
            notes
        FROM runs
        WHERE prompt_category = 'context-scaling'
        ORDER BY id ASC
        """
    )
    family_rows = attach_prompt_family(family_rows)
    family_summary = summarize_by_family(family_rows)

    clean_context_summary = None
    if "summarize_clean_context" in globals():
        clean_context_summary = summarize_clean_context(family_rows)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "summary": summary,
            "latest_success": latest_success,
            "latest_failed": latest_failed,
            "recent": recent,
            "family_summary": family_summary,
            "controlled_context": load_controlled_context_dashboard(),
            "clean_context_summary": clean_context_summary,
        },
    )


def load_controlled_context_dashboard() -> dict[str, Any]:
    """
    Summary data for the /context dashboard from controlled Context Scaling tables.

    Read-only. Does not launch tasks.
    """
    if not context_scaling_tables_exist():
        return {
            "available": False,
            "run_count": 0,
            "result_count": 0,
            "max_context": None,
            "max_peak_vram_mb": None,
            "latest_run": None,
            "latest_results": [],
            "fit_rows": [],
        }

    summary = db_one(
        """
        SELECT
            (SELECT COUNT(*) FROM context_scaling_runs) AS run_count,
            (SELECT COUNT(*) FROM context_scaling_results) AS result_count,
            (SELECT MAX(context_size) FROM context_scaling_results) AS max_context,
            (SELECT MAX(peak_vram_mb) FROM context_scaling_results) AS max_peak_vram_mb
        """
    ) or {}

    latest_run = db_one(
        """
        SELECT *
        FROM context_scaling_runs
        ORDER BY id DESC
        LIMIT 1
        """
    )

    latest_results = db_rows(
        """
        SELECT
            x.id,
            x.context_scaling_run_id,
            x.context_size,
            x.prompt_category,
            x.prompt_filename,
            x.prompt_label,
            x.status,
            x.prompt_eval_tps,
            x.generation_tps,
            x.peak_vram_mb,
            x.exit_code,
            x.error_text,
            x.created_at,
            r.model_profile_name,
            r.model_label,
            r.cache_mode,
            r.status AS run_status
        FROM context_scaling_results x
        JOIN context_scaling_runs r ON r.id = x.context_scaling_run_id
        ORDER BY x.id DESC
        LIMIT 20
        """
    )

    fit_rows = db_rows(
        """
        SELECT
            context_size,
            COUNT(*) AS result_count,
            SUM(CASE WHEN status = 'captured' THEN 1 ELSE 0 END) AS captured_count,
            SUM(CASE WHEN status != 'captured' THEN 1 ELSE 0 END) AS issue_count,
            ROUND(AVG(generation_tps), 2) AS avg_generation_tps,
            ROUND(AVG(prompt_eval_tps), 2) AS avg_prompt_eval_tps,
            MAX(peak_vram_mb) AS max_peak_vram_mb
        FROM context_scaling_results
        GROUP BY context_size
        ORDER BY context_size ASC
        """
    )

    return {
        "available": True,
        "run_count": summary.get("run_count") or 0,
        "result_count": summary.get("result_count") or 0,
        "max_context": summary.get("max_context"),
        "max_peak_vram_mb": summary.get("max_peak_vram_mb"),
        "latest_run": latest_run,
        "latest_results": latest_results,
        "fit_rows": fit_rows,
    }


@app.get("/context", response_class=HTMLResponse)
def context(request: Request):
    rows = db_rows(
        """
        SELECT
            r.id,
            r.timestamp_local,
            r.launcher,
            r.model_display_name,
            r.quant,
            r.profile_name,
            r.ctx_size,
            r.prompt_eval_tps,
            r.generation_tps,
            r.vram_peak_mb,
            r.exit_code,
            r.notes,
            r.prompt_category,
            s.overall_trust,
            s.winner_tag
        FROM runs r
        LEFT JOIN scores s ON s.run_id = r.id
        WHERE r.prompt_category = 'context-scaling'
        ORDER BY r.ctx_size ASC, r.id ASC
        """
    )
    rows = attach_prompt_family(rows)

    chart_rows = [
        row for row in rows
        if row.get("ctx_size") is not None
        and row.get("generation_tps") is not None
        and row.get("prompt_eval_tps") is not None
        and row.get("vram_peak_mb") is not None
        and row.get("prompt_family") != "invalid-or-failed"
    ]

    family_summary = summarize_by_family(rows)

    return templates.TemplateResponse(
        request,
        "context.html",
        {
            "rows": rows,
            "chart_rows": chart_rows,
            "family_summary": family_summary,
            "controlled_context": load_controlled_context_dashboard(),
        },
    )


@app.get("/runs", response_class=HTMLResponse)
def runs(request: Request):
    rows = db_rows(
        """
        SELECT
            r.id,
            r.timestamp_local,
            r.launcher,
            r.profile_name,
            r.model_display_name,
            r.quant,
            r.prompt_category,
            r.ctx_size,
            r.prompt_tokens,
            r.output_tokens,
            r.prompt_eval_tps,
            r.generation_tps,
            r.total_wall_seconds,
            r.vram_peak_mb,
            r.exit_code,
            r.raw_log_path,
            r.response_path,
            s.overall_trust,
            s.winner_tag,
            r.notes
        FROM runs r
        LEFT JOIN scores s ON s.run_id = r.id
        ORDER BY r.id DESC
        LIMIT 200
        """
    )
    rows = attach_prompt_family(rows)

    return templates.TemplateResponse(
        request,
        "runs.html",
        {
            "rows": rows,
        },
    )


@app.get("/runs/{run_id}", response_class=HTMLResponse)
def run_detail(request: Request, run_id: int):
    row = db_one(
        """
        SELECT
            r.*,
            s.factual_accuracy,
            s.technical_correctness,
            s.safety,
            s.instruction_following,
            s.concision,
            s.hallucination_severity,
            s.overall_trust,
            s.winner_tag,
            s.notes AS score_notes
        FROM runs r
        LEFT JOIN scores s ON s.run_id = r.id
        WHERE r.id = ?
        ORDER BY s.id DESC
        """,
        (run_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail="Run not found")

    row["prompt_family"] = classify_prompt_family(row)
    metadata = list(row.items())

    return templates.TemplateResponse(
        request,
        "run_detail.html",
        {
            "row": row,
            "metadata": metadata,
        },
    )


def timestamp_for_filename() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def current_timestamp_local() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")


def profile_run_metadata(profile_name: str) -> dict[str, Any]:
    profile = CHAT_PROFILES.get(profile_name, {})
    label = profile.get("label", profile_name)
    model_path = profile.get("model")
    gguf_filename = Path(model_path).name if model_path else None

    return {
        "launcher": profile.get("launcher") or f"dashboard-chat-{profile_name}",
        "model_key": profile.get("model_key") or profile_name,
        "model_display_name": label,
        "model_family": profile.get("model_family") or profile.get("family"),
        "quant": profile.get("quant"),
        "gguf_filename": gguf_filename,
        "profile_name": profile_name,
        "ctx_size": profile.get("ctx_size"),
    }



def save_failed_chat_run(
    *,
    profile_name: str,
    prompt: str,
    full_prompt: str,
    mode: str,
    max_tokens: int,
    error_reason: str,
    result: dict[str, Any] | None = None,
    response_text: str | None = None,
    http_status: int = 500,
    exit_code: int | None = None,
) -> int | None:
    """
    Persist failed Chat attempts as first-class runs.

    This keeps failed model launches, missing models, bad profiles, timeouts,
    and llama.cpp errors visible in the Runs page with runtime metadata.
    """
    try:
        profile = CHAT_PROFILES.get(profile_name, {})
        model_path = profile.get("model")
        meta = profile_run_metadata(profile_name)

        run_stamp = timestamp_for_filename()
        safe_profile = profile_name.strip().replace("/", "-") or "unknown-profile"
        safe_mode = (mode or "auto").strip().lower().replace("/", "-")

        run_dir = ROOT / "runs" / "chat"
        raw_dir = ROOT / "runs" / "raw-logs"

        run_dir.mkdir(parents=True, exist_ok=True)
        raw_dir.mkdir(parents=True, exist_ok=True)

        prompt_rel = f"runs/chat/{run_stamp}-{safe_profile}-{safe_mode}-failed-prompt.md"
        response_rel = f"runs/chat/{run_stamp}-{safe_profile}-{safe_mode}-failed-response.md"
        raw_rel = f"runs/raw-logs/{run_stamp}-{safe_profile}-{safe_mode}-failed-raw.log"

        prompt_path = ROOT / prompt_rel
        response_path = ROOT / response_rel
        raw_path = ROOT / raw_rel

        stdout_text = (result or {}).get("stdout") or ""
        stderr_text = (result or {}).get("stderr") or ""
        elapsed_seconds = (result or {}).get("elapsed_seconds")
        vram_peak_mb = (result or {}).get("vram_peak_mib")

        if vram_peak_mb is None:
            vram_peak_mb = sample_total_gpu_vram_mib()

        actual_exit_code = (
            exit_code
            if exit_code is not None
            else (result or {}).get("returncode")
        )

        if actual_exit_code is None:
            actual_exit_code = http_status

        visible_failure = response_text or stdout_text.strip() or stderr_text.strip() or error_reason

        failure_report = f"""# Monolith Chat Failure

Profile: {profile_name}
Mode: {mode}
Max tokens: {max_tokens}
HTTP status: {http_status}
Exit code: {actual_exit_code}
Timed out: {(result or {}).get("timed_out", False)}
Elapsed seconds: {elapsed_seconds}
Peak VRAM MiB: {vram_peak_mb}

## Reason

{error_reason}

## Visible output

{visible_failure[-4000:]}

## stderr tail

{stderr_text[-4000:]}

## stdout tail

{stdout_text[-4000:]}
"""

        raw_report = f"""# Monolith failed chat raw log

profile={profile_name}
mode={mode}
max_tokens={max_tokens}
http_status={http_status}
exit_code={actual_exit_code}
elapsed_seconds={elapsed_seconds}
vram_peak_mib={vram_peak_mb}
timed_out={(result or {}).get("timed_out", False)}
model_path={model_path}

===== USER PROMPT =====
{prompt}

===== FULL PROMPT =====
{full_prompt}

===== ERROR REASON =====
{error_reason}

===== STDOUT =====
{stdout_text}

===== STDERR =====
{stderr_text}
"""

        prompt_path.write_text(prompt.strip() + "\n", encoding="utf-8")
        response_path.write_text(failure_report.strip() + "\n", encoding="utf-8")
        raw_path.write_text(raw_report, encoding="utf-8")

        try:
            prompt_tokens, prompt_token_method = llama_token_count(model_path, full_prompt)
        except Exception:
            prompt_tokens, prompt_token_method = estimate_tokens(full_prompt), "estimated-token-count-exception"

        try:
            output_tokens, output_token_method = llama_token_count(model_path, visible_failure)
        except Exception:
            output_tokens, output_token_method = estimate_tokens(visible_failure), "estimated-token-count-exception"

        notes = (
            "Failed FastAPI chat run. "
            f"profile={profile_name} mode={safe_mode} max_tokens={max_tokens} "
            f"http_status={http_status} exit_code={actual_exit_code} "
            f"elapsed_seconds={elapsed_seconds} vram_peak_mib={vram_peak_mb} "
            f"prompt_tokens={prompt_tokens} output_tokens={output_tokens} "
            f"token_methods=prompt:{prompt_token_method},output:{output_token_method} "
            f"reason={error_reason[:240]}"
        )

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute(
                """
                INSERT INTO runs (
                    timestamp_local,
                    hostname,
                    launcher,
                    model_key,
                    model_display_name,
                    model_family,
                    quant,
                    gguf_filename,
                    llama_cpp_build,
                    profile_name,
                    ctx_size,
                    cache_type_k,
                    cache_type_v,
                    batch_size,
                    ubatch_size,
                    gpu_layers,
                    reasoning,
                    mmproj,
                    prompt_file,
                    prompt_category,
                    prompt_text,
                    response_text,
                    prompt_tokens,
                    output_tokens,
                    prompt_eval_tps,
                    generation_tps,
                    total_wall_seconds,
                    vram_peak_mb,
                    exit_code,
                    raw_log_path,
                    response_path,
                    notes
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    current_timestamp_local(),
                    socket.gethostname(),
                    meta["launcher"],
                    meta["model_key"],
                    meta["model_display_name"],
                    meta["model_family"],
                    meta["quant"],
                    meta["gguf_filename"],
                    None,
                    meta["profile_name"],
                    meta["ctx_size"],
                    profile.get("cache_type_k"),
                    profile.get("cache_type_v"),
                    profile.get("batch_size", 256),
                    profile.get("ubatch_size", 64),
                    str(profile.get("gpu_layers", 999)),
                    profile.get("reasoning", "off"),
                    profile.get("mmproj", "none"),
                    prompt_rel,
                    "chat-web-failed",
                    prompt,
                    failure_report,
                    prompt_tokens,
                    output_tokens,
                    None,
                    None,
                    elapsed_seconds,
                    vram_peak_mb,
                    actual_exit_code,
                    raw_rel,
                    response_rel,
                    notes,
                ),
            )

            conn.commit()
            return int(cursor.lastrowid)

    except Exception:
        return None



def save_chat_run(payload: SaveChatRunRequest) -> dict[str, Any]:
    if payload.profile not in CHAT_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {payload.profile}")

    run_stamp = timestamp_for_filename()
    safe_mode = (payload.mode or "auto").strip().lower().replace("/", "-")
    safe_profile = payload.profile.strip().replace("/", "-")

    run_dir = ROOT / "runs" / "chat"
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt_rel = f"runs/chat/{run_stamp}-{safe_profile}-{safe_mode}-prompt.md"
    response_rel = f"runs/chat/{run_stamp}-{safe_profile}-{safe_mode}-response.md"

    prompt_path = ROOT / prompt_rel
    response_path = ROOT / response_rel

    prompt_path.write_text(payload.prompt.strip() + "\n", encoding="utf-8")
    response_path.write_text(payload.response.strip() + "\n", encoding="utf-8")

    meta = profile_run_metadata(payload.profile)

    vram_peak_mb = getattr(payload, "vram_peak_mib", None)

    if vram_peak_mb is None:
        workstation = get_workstation_stats()
        gpu = workstation.get("gpu", {})
        vram_peak_mb = gpu.get("vram_used_mib") if gpu.get("available") else None

    notes_parts = [
        "Saved from FastAPI chat UI.",
        f"mode={safe_mode}",
        f"max_tokens={payload.max_tokens}",
    ]

    if payload.notes:
        notes_parts.append(payload.notes.strip())

    notes = " ".join(notes_parts)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO runs (
                timestamp_local,
                hostname,
                launcher,
                model_key,
                model_display_name,
                model_family,
                quant,
                gguf_filename,
                llama_cpp_build,
                profile_name,
                ctx_size,
                cache_type_k,
                cache_type_v,
                batch_size,
                ubatch_size,
                gpu_layers,
                reasoning,
                mmproj,
                prompt_file,
                prompt_category,
                prompt_text,
                response_text,
                prompt_tokens,
                output_tokens,
                prompt_eval_tps,
                generation_tps,
                total_wall_seconds,
                vram_peak_mb,
                exit_code,
                raw_log_path,
                response_path,
                notes
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                current_timestamp_local(),
                socket.gethostname(),
                meta["launcher"],
                meta["model_key"],
                meta["model_display_name"],
                meta["model_family"],
                meta["quant"],
                meta["gguf_filename"],
                None,
                meta["profile_name"],
                meta["ctx_size"],
                None,
                None,
                256,
                64,
                "999",
                "off",
                "none",
                prompt_rel,
                "chat-web",
                payload.prompt,
                payload.response,
                getattr(payload, "prompt_tokens", None),
                getattr(payload, "output_tokens", None),
                getattr(payload, "prompt_eval_tps", None),
                getattr(payload, "generation_tps", None),
                getattr(payload, "elapsed_seconds", None),
                vram_peak_mb,
                0,
                None,
                response_rel,
                notes,
            ),
        )

        conn.commit()
        run_id = cursor.lastrowid

    return {
        "ok": True,
        "run_id": run_id,
        "prompt_file": prompt_rel,
        "response_path": response_rel,
        "detail_url": f"/runs/{run_id}",
    }





PROMPT_CATEGORY_METADATA = {
    "honesty": {
        "label": "Honesty",
        "purpose": "Tests whether the model admits uncertainty instead of inventing package names, commands, or facts.",
        "scoring_focus": "Honesty under uncertainty, factual restraint, verification workflow.",
        "risk": "high",
    },
    "linux": {
        "label": "Linux ops",
        "purpose": "Tests conservative Arch/Linux/NVIDIA workstation guidance.",
        "scoring_focus": "Technical correctness, safety, rollback planning, practical sequencing.",
        "risk": "high",
    },
    "docker": {
        "label": "Docker/networking",
        "purpose": "Tests troubleshooting for Docker, DNS, NAT, and nftables-style homelab failures.",
        "scoring_focus": "Diagnosis quality, safe fixes, verification, avoiding destructive shortcuts.",
        "risk": "high",
    },
    "zfs": {
        "label": "ZFS/storage",
        "purpose": "Tests whether the model gives cautious storage guidance and clearly labels destructive operations.",
        "scoring_focus": "Data safety, rollback caveats, command accuracy, conservative alternatives.",
        "risk": "critical",
    },
    "coding": {
        "label": "Coding",
        "purpose": "Tests whether the model writes useful, dependency-free, runnable code.",
        "scoring_focus": "Correctness, robustness, standard-library use, error handling.",
        "risk": "medium",
    },
    "config": {
        "label": "Config review",
        "purpose": "Tests whether the model catches realistic operational and security risks in config snippets.",
        "scoring_focus": "Risk identification, practical mitigations, avoiding overreaction.",
        "risk": "high",
    },
    "long-context": {
        "label": "Long-context",
        "purpose": "Tests whether the model retrieves a buried fact from surrounding context.",
        "scoring_focus": "Needle retrieval, instruction following, avoiding unrelated details.",
        "risk": "medium",
    },
    "niche": {
        "label": "Niche factual",
        "purpose": "Tests obscure factual honesty. Ignorance is acceptable; confident fabrication is not.",
        "scoring_focus": "Factual restraint, uncertainty handling, no invented names.",
        "risk": "low",
    },
}


def prompt_category_meta(category: str) -> dict[str, Any]:
    default = {
        "label": category.replace("-", " ").title(),
        "purpose": "Structured local model evaluation prompt.",
        "scoring_focus": "Manual review.",
        "risk": "medium",
    }

    return {
        **default,
        **PROMPT_CATEGORY_METADATA.get(category, {}),
    }


def extract_prompt_title(content: str, fallback: str) -> str:
    for line in content.splitlines():
        line = line.strip()

        if line.startswith("# "):
            title = line.removeprefix("# ").strip()
            return title or fallback

    return fallback


def extract_prompt_summary(content: str) -> str:
    lines = content.splitlines()
    in_heading = False

    for raw in lines:
        line = raw.strip()

        if not line:
            continue

        if line.startswith("#"):
            in_heading = True
            continue

        if in_heading:
            return line

    return ""


def prompt_file_record(path: Path) -> dict[str, Any]:
    rel = path.relative_to(PROMPT_SUITE_ROOT)
    category = rel.parts[0] if len(rel.parts) > 1 else "uncategorized"
    stat = path.stat()
    content = path.read_text(encoding="utf-8", errors="replace")
    meta = prompt_category_meta(category)
    title = extract_prompt_title(content, path.stem.replace("-", " ").title())
    summary = extract_prompt_summary(content)

    return {
        "suite": "core-v2",
        "category": category,
        "category_label": meta["label"],
        "category_purpose": meta["purpose"],
        "scoring_focus": meta["scoring_focus"],
        "risk": meta["risk"],
        "filename": path.name,
        "stem": path.stem,
        "title": title,
        "summary": summary,
        "path": str(path),
        "relative_path": str(rel),
        "size_bytes": stat.st_size,
        "modified_local": datetime.fromtimestamp(stat.st_mtime).astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"),
    }


def load_prompt_library() -> dict[str, Any]:
    if not PROMPT_SUITE_ROOT.exists():
        return {
            "exists": False,
            "root": str(PROMPT_SUITE_ROOT),
            "prompts": [],
            "categories": [],
            "category_summary": [],
        }

    prompts = [
        prompt_file_record(path)
        for path in sorted(PROMPT_SUITE_ROOT.glob("*/*.md"))
        if path.is_file()
    ]

    categories = sorted({item["category"] for item in prompts})

    category_summary = []
    for category in categories:
        category_prompts = [item for item in prompts if item["category"] == category]
        meta = prompt_category_meta(category)
        category_summary.append(
            {
                "category": category,
                "label": meta["label"],
                "purpose": meta["purpose"],
                "scoring_focus": meta["scoring_focus"],
                "risk": meta["risk"],
                "count": len(category_prompts),
                "files": category_prompts,
            }
        )

    return {
        "exists": True,
        "root": str(PROMPT_SUITE_ROOT),
        "prompts": prompts,
        "categories": categories,
        "category_summary": category_summary,
    }


def load_prompt_detail(category: str, filename: str) -> dict[str, Any]:
    safe_category = Path(category).name
    safe_filename = Path(filename).name

    if safe_category != category or safe_filename != filename:
        raise HTTPException(status_code=400, detail="Invalid prompt path")

    if not safe_filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Prompt filename must end with .md")

    path = PROMPT_SUITE_ROOT / safe_category / safe_filename

    try:
        resolved_root = PROMPT_SUITE_ROOT.resolve()
        resolved_path = path.resolve()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Prompt file not found")

    if resolved_root not in resolved_path.parents:
        raise HTTPException(status_code=400, detail="Prompt path escapes prompt root")

    if not resolved_path.exists() or not resolved_path.is_file():
        raise HTTPException(status_code=404, detail="Prompt file not found")

    record = prompt_file_record(resolved_path)
    record["content"] = resolved_path.read_text(encoding="utf-8", errors="replace")

    return record






def active_eval_profiles() -> list[dict[str, Any]]:
    profiles = []

    for key, profile in CHAT_PROFILES.items():
        if profile.get("active") is not True:
            continue

        model_path = profile.get("model")
        model_exists = bool(model_path and Path(model_path).exists())

        profiles.append(
            {
                "key": key,
                "label": profile.get("label", key),
                "model": model_path,
                "ctx_size": profile.get("ctx_size"),
                "quant": profile.get("quant"),
                "model_exists": model_exists,
            }
        )

    return profiles


def format_seconds(seconds: float | int | None) -> str:
    if seconds is None:
        return "calculating"

    seconds = int(max(0, seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"

    return f"{minutes:d}:{seconds:02d}"


def eval_task_snapshot(task_id: str) -> dict[str, Any]:
    with EVAL_TASK_LOCK:
        task = dict(EVAL_TASKS.get(task_id) or {})

    if not task:
        raise HTTPException(status_code=404, detail="Eval task not found")

    started_monotonic = task.get("started_monotonic")
    if started_monotonic:
        elapsed_seconds = round(time.monotonic() - started_monotonic, 1)
    else:
        elapsed_seconds = None

    completed_items = task.get("completed_items") or 0
    total_items = task.get("total_items") or 0

    eta_seconds = None
    if task.get("status") == "running" and completed_items > 0 and elapsed_seconds:
        avg_seconds = elapsed_seconds / completed_items
        eta_seconds = round(max(total_items - completed_items, 0) * avg_seconds, 1)

    task["elapsed_seconds"] = elapsed_seconds
    task["elapsed_display"] = format_seconds(elapsed_seconds)
    task["eta_seconds"] = eta_seconds
    task["eta_display"] = format_seconds(eta_seconds) if eta_seconds is not None else "calculating"
    task.pop("started_monotonic", None)

    return task


def update_eval_task(task_id: str, **updates: Any) -> None:
    with EVAL_TASK_LOCK:
        if task_id not in EVAL_TASKS:
            EVAL_TASKS[task_id] = {}

        EVAL_TASKS[task_id].update(updates)
        EVAL_TASKS[task_id]["updated_at_local"] = current_timestamp_local()


def find_newest_quant_lab_report(before_paths: set[str]) -> Path | None:
    if not QUANT_LAB_RESULTS_DIR.exists():
        return None

    reports = [
        path
        for path in QUANT_LAB_RESULTS_DIR.glob("*-core-v2.md")
        if str(path.resolve()) not in before_paths
    ]

    if not reports:
        return None

    return max(reports, key=lambda item: item.stat().st_mtime)


def import_quant_lab_report_from_app(report_path: Path, notes: str | None = None) -> int | None:
    importer = ROOT / "scripts" / "import-quant-lab-core-v2.py"

    if not importer.exists():
        raise RuntimeError(f"Importer not found: {importer}")

    cmd = [sys.executable, str(importer), str(report_path)]

    if notes:
        cmd.extend(["--notes", notes])

    completed = subprocess.run(
        cmd,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )

    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "Importer failed")

    match = re.search(r"Imported suite_run_id=(\d+)", completed.stdout)
    if not match:
        return None

    return int(match.group(1))


def run_eval_task_worker(task_id: str, profile_key: str, ctx_size: int, max_tokens: int, temperature: float, include: str) -> None:
    profile = CHAT_PROFILES.get(profile_key)

    if not profile:
        update_eval_task(
            task_id,
            status="failed",
            last_message=f"Unknown profile: {profile_key}",
            exit_code=None,
        )
        return

    model_path = profile.get("model")
    label = profile.get("label", profile_key)

    try:
        if not QUANT_LAB_RUNNER.exists():
            raise RuntimeError(f"Quant Lab runner not found: {QUANT_LAB_RUNNER}")

        if not os.access(QUANT_LAB_RUNNER, os.X_OK):
            raise RuntimeError(f"Quant Lab runner is not executable: {QUANT_LAB_RUNNER}")

        if not model_path or not Path(model_path).exists():
            raise RuntimeError(f"Model file not found: {model_path}")

        before_paths = {
            str(path.resolve())
            for path in QUANT_LAB_RESULTS_DIR.glob("*-core-v2.md")
        } if QUANT_LAB_RESULTS_DIR.exists() else set()

        env = os.environ.copy()
        env.update(
            {
                "CTX": str(ctx_size),
                "MAX_TOKENS": str(max_tokens),
                "TEMP": str(temperature),
            }
        )

        if include:
            env["INCLUDE"] = include
        else:
            env.pop("INCLUDE", None)

        cmd = [
            str(QUANT_LAB_RUNNER),
            str(model_path),
            label.replace(" ", "-").replace("/", "-"),
        ]

        update_eval_task(
            task_id,
            status="running",
            started_at_local=current_timestamp_local(),
            started_monotonic=time.monotonic(),
            total_items=1 if include else len(load_prompt_library().get("prompts") or []),
            completed_items=0,
            current_item=include or "core-v2",
            current_model=label,
            command=" ".join(cmd),
            last_message="Starting Quant Lab runner...",
        )

        process = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            text=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            start_new_session=True,
        )

        with EVAL_TASK_LOCK:
            EVAL_TASK_PROCESSES[task_id] = process

        output_lines: list[str] = []
        completed_count = 0

        assert process.stdout is not None

        for line in process.stdout:
            output_lines.append(line)
            stripped = line.strip()

            if stripped.startswith("Running: "):
                completed_count += 1
                update_eval_task(
                    task_id,
                    completed_items=max(completed_count - 1, 0),
                    current_item=stripped.removeprefix("Running: ").strip(),
                    last_message=stripped,
                    stdout_tail="".join(output_lines[-80:]),
                )
            else:
                update_eval_task(
                    task_id,
                    stdout_tail="".join(output_lines[-80:]),
                )

        exit_code = process.wait()

        with EVAL_TASK_LOCK:
            abort_requested = bool(EVAL_TASKS.get(task_id, {}).get("abort_requested"))

        if exit_code != 0:
            update_eval_task(
                task_id,
                status="aborted" if abort_requested else "failed",
                exit_code=exit_code,
                completed_items=completed_count,
                completed_at_local=current_timestamp_local(),
                last_message="Local Eval run aborted by user." if abort_requested else f"Quant Lab runner failed with exit code {exit_code}",
                stdout_tail="".join(output_lines[-120:]),
            )
            return

        update_eval_task(
            task_id,
            completed_items=1 if include else len(load_prompt_library().get("prompts") or []),
            last_message="Runner completed. Looking for generated report...",
            stdout_tail="".join(output_lines[-120:]),
        )

        report_path = find_newest_quant_lab_report(before_paths)

        if not report_path:
            raise RuntimeError("Runner completed, but no new core-v2 report was found")

        suite_run_id = import_quant_lab_report_from_app(
            report_path,
            notes=f"Imported automatically from Monolith eval task {task_id}.",
        )

        update_eval_task(
            task_id,
            status="completed",
            exit_code=0,
            completed_at_local=current_timestamp_local(),
            report_path=str(report_path),
            imported_suite_run_id=suite_run_id,
            suite_run_id=suite_run_id,
            import_id=suite_run_id,
            detail_url=f"/eval/imports/{suite_run_id}" if suite_run_id else None,
            result_url=f"/eval/imports/{suite_run_id}" if suite_run_id else None,
            last_message="Completed and imported Quant Lab report.",
            stdout_tail="".join(output_lines[-120:]),
        )

    except Exception as exc:
        with EVAL_TASK_LOCK:
            abort_requested = bool(EVAL_TASKS.get(task_id, {}).get("abort_requested"))

        update_eval_task(
            task_id,
            status="aborted" if abort_requested else "failed",
            exit_code=-15 if abort_requested else None,
            completed_at_local=current_timestamp_local(),
            last_message="Local Eval run aborted by user." if abort_requested else str(exc),
        )
    finally:
        with EVAL_TASK_LOCK:
            EVAL_TASK_PROCESSES.pop(task_id, None)


def quant_lab_tables_exist() -> bool:
    if not DB_PATH.exists():
        return False

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN ('quant_lab_suite_runs', 'quant_lab_prompt_results')
            """
        ).fetchall()

    return len(rows) == 2


def load_quant_lab_import_summary() -> dict[str, Any]:
    if not quant_lab_tables_exist():
        return {
            "available": False,
            "suite_count": 0,
            "prompt_result_count": 0,
            "latest": [],
        }

    counts = db_one(
        """
        SELECT
            (SELECT COUNT(*) FROM quant_lab_suite_runs) AS suite_count,
            (SELECT COUNT(*) FROM quant_lab_prompt_results) AS prompt_result_count
        """
    ) or {"suite_count": 0, "prompt_result_count": 0}

    latest = db_rows(
        """
        SELECT
            q.id,
            q.imported_at_local,
            q.suite_name,
            q.model_label,
            q.timestamp_local,
            q.host,
            q.backend,
            q.ctx_size,
            q.max_tokens,
            q.temperature,
            q.source_report_path,
            q.source_report_sha256,
            q.notes,
            COUNT(p.id) AS prompt_count,
            ROUND(AVG(p.prompt_eval_tps), 2) AS avg_prompt_eval_tps,
            ROUND(AVG(p.generation_tps), 2) AS avg_generation_tps,
            SUM(CASE WHEN p.passed_basic_capture = 1 THEN 1 ELSE 0 END) AS captured_count
        FROM quant_lab_suite_runs q
        LEFT JOIN quant_lab_prompt_results p ON p.suite_run_id = q.id
        GROUP BY q.id
        ORDER BY q.id DESC
        LIMIT 10
        """
    )

    return {
        "available": True,
        "suite_count": counts.get("suite_count") or 0,
        "prompt_result_count": counts.get("prompt_result_count") or 0,
        "latest": latest,
    }


def clean_eval_output_for_display(value: str | None) -> tuple[str, bool]:
    """
    Display-only cleaner for imported Quant Lab output.

    Raw imported output remains stored unchanged in SQLite and report files.
    This only removes obvious llama.cpp startup/banner/prompt wrapper noise
    from the UI preview.
    """
    raw = value or ""
    if not raw.strip():
        return "", False

    lines = raw.splitlines()
    cleaned: list[str] = []

    skipping_system = False
    saw_model_answer_marker = False

    noise_prefixes = (
        "Loading model",
        "build:",
        "model",
        "modalities:",
        "available commands:",
        "/exit",
        "/regen",
        "/clear",
        "/read",
        "/glob",
        "Exiting",
    )

    noise_contains = (
        "llama.cpp",
        "llama_model_loader",
        "llama_model_load",
        "ggml_",
        "common_init_from_params",
        "srv    load_model",
        "system_info:",
        "sampler seed:",
        "sampler params:",
        "generate:",
        "main:",
    )

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if cleaned and cleaned[-1] != "":
                cleaned.append("")
            continue

        # Drop obvious startup/banner/help noise.
        if stripped.startswith(noise_prefixes):
            continue

        if any(fragment in stripped for fragment in noise_contains):
            continue

        # Drop prompt/perf footer lines from llama.cpp single-turn output.
        if re.match(r"^\[\s*Prompt:\s*[\d.]+\s+t/s\s*\|\s*Generation:\s*[\d.]+\s+t/s\s*\]$", stripped):
            continue

        # Detect and skip folded system prompt wrapper.
        if stripped.startswith("> System instructions:"):
            skipping_system = True
            continue

        if skipping_system:
            # The runner often inserts "User task:" or the actual task/title after system instructions.
            # Stop skipping at likely user-facing answer/task boundaries.
            if (
                stripped.startswith("User task:")
                or stripped.startswith("# ")
                or stripped.startswith("## ")
                or stripped.startswith("Question:")
                or stripped.startswith("Answer:")
                or stripped.startswith("I ")
                or stripped.startswith("The ")
                or stripped.startswith("Here")
            ):
                skipping_system = False
            else:
                continue

        # Remove explicit wrapper labels but keep following content.
        if stripped in {"User task:", "Assistant:", "Model response:", "Response:"}:
            continue

        cleaned.append(line)
        saw_model_answer_marker = True

    clean_text = "\n".join(cleaned).strip()

    # If the cleaner was too aggressive, fall back to raw.
    if not clean_text:
        return raw, False

    return clean_text, clean_text != raw.strip()



def load_quant_lab_import_detail(suite_run_id: int) -> dict[str, Any]:
    if not quant_lab_tables_exist():
        raise HTTPException(status_code=404, detail="Quant Lab import tables not found")

    suite = db_one(
        """
        SELECT *
        FROM quant_lab_suite_runs
        WHERE id = ?
        """,
        (suite_run_id,),
    )

    if not suite:
        raise HTTPException(status_code=404, detail="Quant Lab suite import not found")

    prompts = db_rows(
        """
        SELECT *
        FROM quant_lab_prompt_results
        WHERE suite_run_id = ?
        ORDER BY prompt_order ASC
        """,
        (suite_run_id,),
    )

    for prompt in prompts:
        clean_output, changed = clean_eval_output_for_display(prompt.get("output_text"))
        prompt["clean_output_text"] = clean_output
        prompt["clean_output_changed"] = changed

    summary = db_one(
        """
        SELECT
            COUNT(*) AS prompt_count,
            ROUND(AVG(prompt_eval_tps), 2) AS avg_prompt_eval_tps,
            ROUND(AVG(generation_tps), 2) AS avg_generation_tps,
            SUM(CASE WHEN passed_basic_capture = 1 THEN 1 ELSE 0 END) AS captured_count
        FROM quant_lab_prompt_results
        WHERE suite_run_id = ?
        """,
        (suite_run_id,),
    ) or {}

    return {
        "suite": suite,
        "prompts": prompts,
        "summary": summary,
    }


def sample_gpu_vram_used_mib() -> int | None:
    """
    Return current NVIDIA GPU memory.used in MiB.

    This is intentionally system-level VRAM usage, not per-process VRAM.
    For Monolith Context Scaling, runs are controlled one at a time, so the
    peak is still useful for practical fit testing.
    """
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
        )
    except Exception:
        return None

    if completed.returncode != 0:
        return None

    values: list[int] = []

    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        try:
            values.append(int(float(line)))
        except ValueError:
            continue

    if not values:
        return None

    return max(values)


def start_peak_vram_sampler(process: subprocess.Popen, interval_seconds: float = 0.5) -> dict[str, Any]:
    """
    Start a lightweight background VRAM sampler for a subprocess.

    The returned dict is mutated by the sampler thread and read after the
    subprocess exits.
    """
    state: dict[str, Any] = {
        "peak_vram_mb": sample_gpu_vram_used_mib(),
        "samples": 0,
        "running": True,
    }

    def sampler() -> None:
        while state.get("running") and process.poll() is None:
            value = sample_gpu_vram_used_mib()

            if value is not None:
                current_peak = state.get("peak_vram_mb")
                if current_peak is None or value > int(current_peak):
                    state["peak_vram_mb"] = value

                state["samples"] = int(state.get("samples") or 0) + 1

            time.sleep(interval_seconds)

        # One final sample after process exit, because VRAM can peak near load/end.
        value = sample_gpu_vram_used_mib()
        if value is not None:
            current_peak = state.get("peak_vram_mb")
            if current_peak is None or value > int(current_peak):
                state["peak_vram_mb"] = value

            state["samples"] = int(state.get("samples") or 0) + 1

    thread = threading.Thread(target=sampler, daemon=True)
    thread.start()
    state["thread"] = thread
    return state


def stop_peak_vram_sampler(state: dict[str, Any] | None) -> int | None:
    if not state:
        return None

    state["running"] = False
    thread = state.get("thread")

    if thread is not None:
        try:
            thread.join(timeout=1.5)
        except Exception:
            pass

    value = state.get("peak_vram_mb")
    return int(value) if value is not None else None


def normalize_context_scaling_prompt_path(value: str) -> str:
    candidate = (value or "").strip().lstrip("/")
    candidate = str(Path(candidate))

    allowed = set(CONTEXT_SCALING_DEFAULT_PROMPTS)

    if candidate not in allowed:
        raise HTTPException(status_code=400, detail=f"Prompt is not approved for context scaling: {candidate}")

    path = PROMPT_SUITE_ROOT / candidate

    try:
        resolved_root = PROMPT_SUITE_ROOT.resolve()
        resolved_path = path.resolve()
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail=f"Approved prompt is missing: {candidate}")

    if resolved_root not in resolved_path.parents:
        raise HTTPException(status_code=400, detail="Prompt path escapes prompt root")

    if not resolved_path.exists() or not resolved_path.is_file():
        raise HTTPException(status_code=400, detail=f"Approved prompt is missing: {candidate}")

    return candidate


def validate_context_scaling_request(payload: ContextScalingRunRequest) -> dict[str, Any]:
    if payload.profile not in CHAT_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {payload.profile}")

    profile = CHAT_PROFILES[payload.profile]

    if profile.get("active") is not True:
        raise HTTPException(status_code=400, detail="Profile is not active")

    model_path = profile.get("model")
    if not model_path or not Path(model_path).exists():
        raise HTTPException(status_code=400, detail=f"Model file not found: {model_path}")

    allowed_contexts = set(CONTEXT_SCALING_DEFAULT_LADDER + CONTEXT_SCALING_EXTENDED_LADDER)
    requested_contexts = payload.contexts or CONTEXT_SCALING_DEFAULT_LADDER

    contexts: list[int] = []
    for item in requested_contexts:
        ctx = int(item)
        if ctx not in allowed_contexts:
            raise HTTPException(status_code=400, detail=f"Context size is not approved: {ctx}")
        if ctx not in contexts:
            contexts.append(ctx)

    if not contexts:
        raise HTTPException(status_code=400, detail="At least one context size is required")

    selected_prompts = payload.prompts or CONTEXT_SCALING_DEFAULT_PROMPTS
    prompts = [normalize_context_scaling_prompt_path(item) for item in selected_prompts]

    if not prompts:
        raise HTTPException(status_code=400, detail="At least one prompt is required")

    safe_max_tokens = max(64, min(int(payload.max_tokens), 4096))
    safe_temp = max(0.0, min(float(payload.temperature), 2.0))

    return {
        "profile_key": payload.profile,
        "profile": profile,
        "model_path": model_path,
        "model_label": profile.get("label", payload.profile),
        "quant_label": profile.get("quant"),
        "contexts": contexts,
        "prompts": prompts,
        "max_tokens": safe_max_tokens,
        "temperature": safe_temp,
    }


def create_context_scaling_run_record(config: dict[str, Any]) -> int:
    if not context_scaling_tables_exist():
        raise HTTPException(status_code=500, detail="Context scaling tables not found. Run migration first.")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO context_scaling_runs (
                model_profile_name,
                model_label,
                backend_label,
                quant_label,
                cache_mode,
                context_ladder_json,
                selected_prompts_json,
                temperature,
                max_tokens,
                status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config["profile_key"],
                config["model_label"],
                "llama.cpp / Quant Lab",
                config.get("quant_label"),
                "normal",
                json_dumps_compact(config["contexts"]),
                json_dumps_compact(config["prompts"]),
                config["temperature"],
                config["max_tokens"],
                "queued",
                "Created by Monolith Context Scaling controlled runner.",
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def json_dumps_compact(value: Any) -> str:
    import json
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def update_context_scaling_run_status(run_id: int, status: str, notes: str | None = None) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        if notes is None:
            conn.execute(
                "UPDATE context_scaling_runs SET status = ? WHERE id = ?",
                (status, run_id),
            )
        else:
            conn.execute(
                "UPDATE context_scaling_runs SET status = ?, notes = ? WHERE id = ?",
                (status, notes, run_id),
            )
        conn.commit()


def insert_context_scaling_failure_result(
    run_id: int,
    context_size: int,
    prompt_rel_path: str,
    status: str,
    error_text: str,
    exit_code: int | None = None,
    output_raw: str | None = None,
    peak_vram_mb: int | None = None,
) -> None:
    category, filename = prompt_rel_path.split("/", 1)
    prompt_path = PROMPT_SUITE_ROOT / prompt_rel_path
    prompt_label = prompt_path.stem if prompt_path.exists() else filename

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO context_scaling_results (
                context_scaling_run_id,
                context_size,
                prompt_category,
                prompt_filename,
                prompt_label,
                output_raw,
                output_clean_preview,
                peak_vram_mb,
                exit_code,
                status,
                error_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                context_size,
                category,
                filename,
                prompt_label,
                output_raw,
                None,
                peak_vram_mb,
                exit_code,
                status,
                error_text,
            ),
        )
        conn.commit()


def copy_quant_lab_import_to_context_scaling(
    context_scaling_run_id: int,
    suite_run_id: int,
    context_size: int,
    prompt_rel_path: str,
    exit_code: int,
    peak_vram_mb: int | None = None,
) -> int:
    suite = db_one(
        """
        SELECT *
        FROM quant_lab_suite_runs
        WHERE id = ?
        """,
        (suite_run_id,),
    )

    if not suite:
        raise RuntimeError(f"Imported Quant Lab suite not found: {suite_run_id}")

    rows = db_rows(
        """
        SELECT *
        FROM quant_lab_prompt_results
        WHERE suite_run_id = ?
        ORDER BY prompt_order ASC
        """,
        (suite_run_id,),
    )

    inserted = 0

    with sqlite3.connect(DB_PATH) as conn:
        for row in rows:
            output_raw = row.get("output_text") or ""
            clean_output, _changed = clean_eval_output_for_display(output_raw)

            status = "captured"
            if not output_raw.strip():
                status = "blank-output"
            elif row.get("generation_tps") is None:
                status = "missing-metrics"

            conn.execute(
                """
                INSERT INTO context_scaling_results (
                    context_scaling_run_id,
                    context_size,
                    prompt_category,
                    prompt_filename,
                    prompt_label,
                    output_raw,
                    output_clean_preview,
                    prompt_eval_tps,
                    generation_tps,
                    peak_vram_mb,
                    exit_code,
                    status,
                    error_text,
                    source_report_path,
                    source_report_sha256
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    context_scaling_run_id,
                    context_size,
                    row.get("category"),
                    Path(row.get("prompt_file") or prompt_rel_path).name,
                    row.get("prompt_name"),
                    output_raw,
                    clean_output,
                    row.get("prompt_eval_tps"),
                    row.get("generation_tps"),
                    peak_vram_mb,
                    exit_code,
                    status,
                    None,
                    suite.get("source_report_path"),
                    suite.get("source_report_sha256"),
                ),
            )
            inserted += 1

        conn.commit()

    return inserted


def newest_quant_lab_report_after(before_paths: set[str]) -> Path | None:
    return find_newest_quant_lab_report(before_paths)


def run_context_scaling_task_worker(
    task_id: str,
    context_scaling_run_id: int,
    profile_key: str,
    contexts: list[int],
    prompt_paths: list[str],
    max_tokens: int,
    temperature: float,
) -> None:
    profile = CHAT_PROFILES.get(profile_key)

    if not profile:
        update_eval_task(task_id, status="failed", last_message=f"Unknown profile: {profile_key}")
        update_context_scaling_run_status(context_scaling_run_id, "failed", f"Unknown profile: {profile_key}")
        return

    model_path = profile.get("model")
    model_label = profile.get("label", profile_key)
    total_items = len(contexts) * len(prompt_paths)
    completed_items = 0

    try:
        if not QUANT_LAB_RUNNER.exists():
            raise RuntimeError(f"Quant Lab runner not found: {QUANT_LAB_RUNNER}")

        if not os.access(QUANT_LAB_RUNNER, os.X_OK):
            raise RuntimeError(f"Quant Lab runner is not executable: {QUANT_LAB_RUNNER}")

        if not model_path or not Path(model_path).exists():
            raise RuntimeError(f"Model file not found: {model_path}")

        update_context_scaling_run_status(context_scaling_run_id, "running")

        update_eval_task(
            task_id,
            status="running",
            kind="context-scaling",
            started_at_local=current_timestamp_local(),
            started_monotonic=time.monotonic(),
            total_items=total_items,
            completed_items=0,
            current_item="starting",
            current_model=model_label,
            context_scaling_run_id=context_scaling_run_id,
            result_url=f"/eval/context-scaling/{context_scaling_run_id}",
            detail_url=f"/eval/context-scaling/{context_scaling_run_id}",
            last_message="Starting Context Scaling runner...",
        )

        combined_tail: list[str] = []

        for context_size in contexts:
            for prompt_rel_path in prompt_paths:
                with EVAL_TASK_LOCK:
                    abort_requested = bool(EVAL_TASKS.get(task_id, {}).get("abort_requested"))

                if abort_requested:
                    update_context_scaling_run_status(context_scaling_run_id, "aborted", "Aborted by user.")
                    update_eval_task(
                        task_id,
                        status="aborted",
                        exit_code=-15,
                        completed_at_local=current_timestamp_local(),
                        last_message="Context Scaling run aborted by user.",
                        stdout_tail="".join(combined_tail[-120:]),
                    )
                    return

                category = prompt_rel_path.split("/", 1)[0]
                current_label = f"ctx {context_size} / {prompt_rel_path}"

                before_paths = {
                    str(path.resolve())
                    for path in QUANT_LAB_RESULTS_DIR.glob("*-core-v2.md")
                } if QUANT_LAB_RESULTS_DIR.exists() else set()

                env = os.environ.copy()
                env.update(
                    {
                        "CTX": str(context_size),
                        "MAX_TOKENS": str(max_tokens),
                        "TEMP": str(temperature),
                        "INCLUDE": category,
                    }
                )

                cmd = [
                    str(QUANT_LAB_RUNNER),
                    str(model_path),
                    f"{model_label}-ctx{context_size}-{category}".replace(" ", "-").replace("/", "-"),
                ]

                update_eval_task(
                    task_id,
                    current_item=current_label,
                    current_context=context_size,
                    current_prompt=prompt_rel_path,
                    last_message=f"Running {current_label}",
                    command=" ".join(cmd),
                )

                process = subprocess.Popen(
                    cmd,
                    cwd=str(ROOT),
                    env=env,
                    text=True,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    bufsize=1,
                    start_new_session=True,
                )

                vram_sampler = start_peak_vram_sampler(process)

                with EVAL_TASK_LOCK:
                    EVAL_TASK_PROCESSES[task_id] = process

                step_output: list[str] = []

                assert process.stdout is not None

                for line in process.stdout:
                    step_output.append(line)
                    combined_tail.append(line)
                    update_eval_task(
                        task_id,
                        stdout_tail="".join(combined_tail[-120:]),
                    )

                exit_code = process.wait()
                peak_vram_mb = stop_peak_vram_sampler(vram_sampler)

                with EVAL_TASK_LOCK:
                    EVAL_TASK_PROCESSES.pop(task_id, None)
                    abort_requested = bool(EVAL_TASKS.get(task_id, {}).get("abort_requested"))

                update_eval_task(
                    task_id,
                    peak_vram_mb=peak_vram_mb,
                    last_vram_sample_mb=peak_vram_mb,
                )

                if abort_requested:
                    update_context_scaling_run_status(context_scaling_run_id, "aborted", "Aborted by user.")
                    update_eval_task(
                        task_id,
                        status="aborted",
                        exit_code=-15,
                        completed_at_local=current_timestamp_local(),
                        last_message="Context Scaling run aborted by user.",
                        stdout_tail="".join(combined_tail[-120:]),
                    )
                    return

                if exit_code != 0:
                    insert_context_scaling_failure_result(
                        context_scaling_run_id,
                        context_size,
                        prompt_rel_path,
                        status="failed",
                        error_text=f"Quant Lab runner failed with exit code {exit_code}",
                        exit_code=exit_code,
                        output_raw="".join(step_output),
                        peak_vram_mb=peak_vram_mb,
                    )
                    completed_items += 1
                    update_eval_task(
                        task_id,
                        completed_items=completed_items,
                        last_message=f"Failed {current_label} with exit code {exit_code}",
                        stdout_tail="".join(combined_tail[-120:]),
                    )
                    continue

                report_path = newest_quant_lab_report_after(before_paths)

                if not report_path:
                    insert_context_scaling_failure_result(
                        context_scaling_run_id,
                        context_size,
                        prompt_rel_path,
                        status="missing-report",
                        error_text="Runner completed but no new Quant Lab report was found",
                        exit_code=exit_code,
                        output_raw="".join(step_output),
                        peak_vram_mb=peak_vram_mb,
                    )
                    completed_items += 1
                    update_eval_task(
                        task_id,
                        completed_items=completed_items,
                        last_message=f"No report found for {current_label}",
                        stdout_tail="".join(combined_tail[-120:]),
                    )
                    continue

                suite_run_id = import_quant_lab_report_from_app(
                    report_path,
                    notes=f"Imported automatically from Monolith context-scaling task {task_id}, run {context_scaling_run_id}, context {context_size}, prompt {prompt_rel_path}.",
                )

                if not suite_run_id:
                    insert_context_scaling_failure_result(
                        context_scaling_run_id,
                        context_size,
                        prompt_rel_path,
                        status="import-missing-id",
                        error_text="Importer completed but did not return suite_run_id",
                        exit_code=exit_code,
                        output_raw="".join(step_output),
                        peak_vram_mb=peak_vram_mb,
                    )
                else:
                    copy_quant_lab_import_to_context_scaling(
                        context_scaling_run_id,
                        suite_run_id,
                        context_size,
                        prompt_rel_path,
                        exit_code,
                        peak_vram_mb=peak_vram_mb,
                    )

                completed_items += 1
                update_eval_task(
                    task_id,
                    completed_items=completed_items,
                    last_message=f"Completed {current_label}",
                    stdout_tail="".join(combined_tail[-120:]),
                )

        update_context_scaling_run_status(context_scaling_run_id, "completed")

        update_eval_task(
            task_id,
            status="completed",
            exit_code=0,
            completed_items=completed_items,
            completed_at_local=current_timestamp_local(),
            context_scaling_run_id=context_scaling_run_id,
            result_url=f"/eval/context-scaling/{context_scaling_run_id}",
            detail_url=f"/eval/context-scaling/{context_scaling_run_id}",
            last_message="Context Scaling run completed.",
            stdout_tail="".join(combined_tail[-120:]),
        )

    except Exception as exc:
        with EVAL_TASK_LOCK:
            abort_requested = bool(EVAL_TASKS.get(task_id, {}).get("abort_requested"))

        status = "aborted" if abort_requested else "failed"
        message = "Context Scaling run aborted by user." if abort_requested else str(exc)

        update_context_scaling_run_status(context_scaling_run_id, status, message)
        update_eval_task(
            task_id,
            status=status,
            exit_code=-15 if abort_requested else None,
            completed_at_local=current_timestamp_local(),
            last_message=message,
        )
    finally:
        with EVAL_TASK_LOCK:
            EVAL_TASK_PROCESSES.pop(task_id, None)


def context_scaling_tables_exist() -> bool:
    if not DB_PATH.exists():
        return False

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN ('context_scaling_runs', 'context_scaling_results')
            """
        ).fetchall()

    return len(rows) == 2


def context_scaling_prompt_options() -> list[dict[str, Any]]:
    prompts = []

    for rel_path in CONTEXT_SCALING_DEFAULT_PROMPTS:
        path = PROMPT_SUITE_ROOT / rel_path

        if not path.exists() or not path.is_file():
            prompts.append(
                {
                    "path": rel_path,
                    "category": rel_path.split("/", 1)[0],
                    "filename": rel_path.rsplit("/", 1)[-1],
                    "title": rel_path,
                    "exists": False,
                    "default": True,
                }
            )
            continue

        record = prompt_file_record(path)
        record["path"] = rel_path
        record["exists"] = True
        record["default"] = True
        prompts.append(record)

    return prompts


def load_context_scaling_summary() -> dict[str, Any]:
    if not context_scaling_tables_exist():
        return {
            "available": False,
            "run_count": 0,
            "result_count": 0,
            "latest": [],
        }

    counts = db_one(
        """
        SELECT
            (SELECT COUNT(*) FROM context_scaling_runs) AS run_count,
            (SELECT COUNT(*) FROM context_scaling_results) AS result_count
        """
    ) or {"run_count": 0, "result_count": 0}

    latest = db_rows(
        """
        SELECT
            r.id,
            r.created_at,
            r.model_profile_name,
            r.model_label,
            r.cache_mode,
            r.context_ladder_json,
            r.selected_prompts_json,
            r.temperature,
            r.max_tokens,
            r.status,
            r.notes,
            COUNT(x.id) AS result_count,
            COUNT(DISTINCT x.context_size) AS context_count,
            ROUND(AVG(x.prompt_eval_tps), 2) AS avg_prompt_eval_tps,
            ROUND(AVG(x.generation_tps), 2) AS avg_generation_tps,
            MAX(x.peak_vram_mb) AS max_peak_vram_mb
        FROM context_scaling_runs r
        LEFT JOIN context_scaling_results x ON x.context_scaling_run_id = r.id
        GROUP BY r.id
        ORDER BY r.id DESC
        LIMIT 20
        """
    )

    return {
        "available": True,
        "run_count": counts.get("run_count") or 0,
        "result_count": counts.get("result_count") or 0,
        "latest": latest,
    }


def load_context_scaling_detail(run_id: int) -> dict[str, Any]:
    if not context_scaling_tables_exist():
        raise HTTPException(status_code=404, detail="Context scaling tables not found")

    run = db_one(
        """
        SELECT *
        FROM context_scaling_runs
        WHERE id = ?
        """,
        (run_id,),
    )

    if not run:
        raise HTTPException(status_code=404, detail="Context scaling run not found")

    results = db_rows(
        """
        SELECT *
        FROM context_scaling_results
        WHERE context_scaling_run_id = ?
        ORDER BY context_size ASC, prompt_category ASC, prompt_filename ASC
        """,
        (run_id,),
    )

    contexts = sorted(
        {
            row["context_size"]
            for row in results
            if row.get("context_size") is not None
        }
    )

    prompts = []
    seen = set()

    for row in results:
        key = (row.get("prompt_category"), row.get("prompt_filename"))
        if key in seen:
            continue

        seen.add(key)
        prompts.append(
            {
                "category": row.get("prompt_category"),
                "filename": row.get("prompt_filename"),
                "label": row.get("prompt_label") or row.get("prompt_filename"),
            }
        )

    return {
        "run": run,
        "results": results,
        "contexts": contexts,
        "prompts": prompts,
    }


def context_scaling_options_payload() -> dict[str, Any]:
    return {
        "profiles": active_eval_profiles(),
        "default_context_ladder": CONTEXT_SCALING_DEFAULT_LADDER,
        "extended_context_ladder": CONTEXT_SCALING_EXTENDED_LADDER,
        "allowed_contexts": CONTEXT_SCALING_DEFAULT_LADDER + CONTEXT_SCALING_EXTENDED_LADDER,
        "default_temperature": CONTEXT_SCALING_DEFAULT_TEMP,
        "default_max_tokens": CONTEXT_SCALING_DEFAULT_MAX_TOKENS,
        "default_prompts": CONTEXT_SCALING_DEFAULT_PROMPTS,
        "prompt_options": context_scaling_prompt_options(),
        "cache_modes": ["normal"],
        "mode": "read-only shell",
    }



# ---------------------------------------------------------------------------
# Agent Backend Eval — alpha v0.10.0 read-only shell
# ---------------------------------------------------------------------------

HERMES_PROMPT_ROOT = ROOT / "prompts" / "agent-eval-v1"
HERMES_CONTEXT_DEFAULTS = [8192, 16384, 32768, 65536]
HERMES_CONTEXT_OPTIONAL = [12288, 24576]
HERMES_CONTEXT_ALLOWED = sorted(set(HERMES_CONTEXT_DEFAULTS + HERMES_CONTEXT_OPTIONAL))


def hermes_eval_tables_exist() -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name IN ('hermes_eval_runs', 'hermes_eval_results', 'hermes_eval_scores')
            """
        ).fetchall()

    return len(rows) == 3


def hermes_eval_prompt_options() -> list[dict[str, str]]:
    if not HERMES_PROMPT_ROOT.exists():
        return []

    options: list[dict[str, str]] = []

    excluded = {"README.md", "scoring/rubric.md"}

    for path in sorted(HERMES_PROMPT_ROOT.rglob("*.md")):
        rel_path = path.relative_to(HERMES_PROMPT_ROOT).as_posix()

        if rel_path in excluded:
            continue

        parts = rel_path.split("/", 1)
        category = parts[0] if parts else "uncategorized"
        name = path.stem.replace("-", " ").title()

        options.append(
            {
                "category": category,
                "name": name,
                "path": rel_path,
            }
        )

    return options


def hermes_eval_profile_options() -> list[dict[str, str]]:
    options: list[dict[str, str]] = []

    for key, profile in sorted(CHAT_PROFILES.items()):
        label = key

        if isinstance(profile, dict):
            label = profile.get("label") or profile.get("name") or key

        options.append(
            {
                "key": key,
                "label": str(label),
            }
        )

    return options


def hermes_eval_context_ladders() -> list[dict[str, object]]:
    return [
        {
            "key": "8192-only",
            "label": "8192 only",
            "contexts": [8192],
            "description": "Safe first smoke test.",
        },
        {
            "key": "16384-only",
            "label": "16384 only",
            "contexts": [16384],
            "description": "Single-step high-context probe.",
        },
        {
            "key": "32768-only",
            "label": "32768 only",
            "contexts": [32768],
            "description": "Pre-64k agent stress point.",
        },
        {
            "key": "65536-only",
            "label": "65536 only",
            "contexts": [65536],
            "description": "Agent target context. Use cautiously.",
        },
        {
            "key": "quick-agent",
            "label": "Quick agent ladder",
            "contexts": [8192, 16384, 32768, 65536],
            "description": "Default agent-backend viability ladder.",
        },
        {
            "key": "extended-agent",
            "label": "Extended agent ladder",
            "contexts": [8192, 12288, 16384, 24576, 32768, 65536],
            "description": "Adds intermediate context sizes for fit diagnosis.",
        },
    ]


def load_hermes_eval_summary() -> dict[str, object]:
    empty = {
        "tables_available": False,
        "run_count": 0,
        "result_count": 0,
        "score_count": 0,
        "latest_runs": [],
    }

    if not hermes_eval_tables_exist():
        return empty

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        counts = conn.execute(
            """
            SELECT
                (SELECT COUNT(*) FROM hermes_eval_runs) AS run_count,
                (SELECT COUNT(*) FROM hermes_eval_results) AS result_count,
                (SELECT COUNT(*) FROM hermes_eval_scores) AS score_count
            """
        ).fetchone()

        latest_runs = conn.execute(
            """
            SELECT
                id,
                created_at,
                model_profile_name,
                model_label,
                suite_name,
                status
            FROM hermes_eval_runs
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

    return {
        "tables_available": True,
        "run_count": counts["run_count"] if counts else 0,
        "result_count": counts["result_count"] if counts else 0,
        "score_count": counts["score_count"] if counts else 0,
        "latest_runs": [dict(row) for row in latest_runs],
    }


def hermes_eval_options_payload() -> dict[str, object]:
    return {
        "suite": "agent-eval-v1",
        "target_context": 65536,
        "allowed_contexts": HERMES_CONTEXT_ALLOWED,
        "default_contexts": HERMES_CONTEXT_DEFAULTS,
        "optional_contexts": HERMES_CONTEXT_OPTIONAL,
        "context_ladders": hermes_eval_context_ladders(),
        "prompt_options": hermes_eval_prompt_options(),
        "profile_options": hermes_eval_profile_options(),
        "cache_modes": ["normal"],
        "max_tokens": {
            "default": 800,
            "min": 300,
            "max": 1500,
        },
        "temperature": {
            "default": 0.2,
            "min": 0.0,
            "max": 1.0,
        },
    }


def normalize_agent_eval_prompt_path(value: str) -> str:
    candidate = (value or "").strip().lstrip("/")

    if not candidate:
        raise HTTPException(status_code=400, detail="Prompt is required")

    candidate_path = Path(candidate)

    if candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise HTTPException(status_code=400, detail="Prompt path is not allowed")

    normalized = candidate_path.as_posix()

    if normalized in {"README.md", "scoring/rubric.md"}:
        raise HTTPException(status_code=400, detail=f"Prompt is metadata, not a runnable eval prompt: {normalized}")

    prompt_path = HERMES_PROMPT_ROOT / normalized

    try:
        resolved_root = HERMES_PROMPT_ROOT.resolve()
        resolved_path = prompt_path.resolve()
    except FileNotFoundError:
        raise HTTPException(status_code=400, detail=f"Approved prompt is missing: {normalized}")

    if resolved_root not in resolved_path.parents:
        raise HTTPException(status_code=400, detail="Prompt path escapes prompt root")

    if not resolved_path.exists() or not resolved_path.is_file() or resolved_path.suffix != ".md":
        raise HTTPException(status_code=400, detail=f"Approved prompt is missing: {normalized}")

    return normalized


def validate_agent_backend_eval_single_request(payload: AgentBackendEvalSingleRunRequest) -> dict[str, Any]:
    if payload.profile not in CHAT_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {payload.profile}")

    profile = CHAT_PROFILES[payload.profile]

    if profile.get("active") is not True:
        raise HTTPException(status_code=400, detail="Profile is not active")

    model_path = profile.get("model")
    if not model_path or not Path(model_path).exists():
        raise HTTPException(status_code=400, detail=f"Model file not found: {model_path}")

    if not Path(LLAMA_COMPLETION).exists():
        raise HTTPException(status_code=500, detail=f"llama-completion not found: {LLAMA_COMPLETION}")

    prompt_rel_path = normalize_agent_eval_prompt_path(payload.prompt)
    prompt_path = HERMES_PROMPT_ROOT / prompt_rel_path

    safe_ctx = int(payload.ctx_size or 8192)
    if safe_ctx not in HERMES_CONTEXT_ALLOWED:
        raise HTTPException(status_code=400, detail=f"Context size is not approved: {safe_ctx}")

    safe_max_tokens = max(64, min(int(payload.max_tokens or 800), 1500))
    safe_temp = max(0.0, min(float(payload.temperature if payload.temperature is not None else 0.2), 1.0))

    category, filename = prompt_rel_path.split("/", 1)
    prompt_name = Path(filename).stem

    return {
        "profile_key": payload.profile,
        "profile": profile,
        "model_path": model_path,
        "model_label": profile.get("label", payload.profile),
        "prompt_rel_path": prompt_rel_path,
        "prompt_path": prompt_path,
        "prompt_text": prompt_path.read_text(encoding="utf-8"),
        "prompt_category": category,
        "prompt_name": prompt_name,
        "ctx_size": safe_ctx,
        "max_tokens": safe_max_tokens,
        "temperature": safe_temp,
    }


def create_agent_backend_eval_run_record(config: dict[str, Any]) -> int:
    if not hermes_eval_tables_exist():
        raise HTTPException(status_code=500, detail="Agent Backend Eval tables not found. Run migration first.")

    profile = config["profile"]

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO hermes_eval_runs (
                model_profile_name,
                model_label,
                model_path,
                llama_cli_path,
                suite_name,
                context_ladder_json,
                selected_prompts_json,
                max_tokens,
                temperature,
                gpu_layers,
                cache_settings,
                reasoning_setting,
                status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                config["profile_key"],
                config["model_label"],
                config["model_path"],
                LLAMA_COMPLETION,
                "agent-eval-v1",
                json_dumps_compact([config["ctx_size"]]),
                json_dumps_compact([config["prompt_rel_path"]]),
                config["max_tokens"],
                config["temperature"],
                int(profile.get("gpu_layers", 999)),
                "normal",
                str(profile.get("reasoning", "off")),
                "running",
                "Created by Monolith Agent Backend Eval single-run launcher.",
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_agent_backend_eval_run_status(run_id: int, status: str, notes: str | None = None) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        if notes is None:
            conn.execute(
                "UPDATE hermes_eval_runs SET status = ? WHERE id = ?",
                (status, run_id),
            )
        else:
            conn.execute(
                "UPDATE hermes_eval_runs SET status = ?, notes = ? WHERE id = ?",
                (status, notes, run_id),
            )
        conn.commit()


def insert_agent_backend_eval_result_record(
    run_id: int,
    config: dict[str, Any],
    *,
    status: str,
    exit_code: int | None,
    raw_output: str,
    cleaned_output: str,
    error_text: str | None,
    prompt_eval_tps: float | None,
    generation_tps: float | None,
    total_runtime_sec: float | None,
    peak_vram_mib: int | None,
) -> int:
    output_truncated = 1 if len(raw_output) > 500_000 else 0
    stored_raw_output = raw_output[:500_000]

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO hermes_eval_results (
                run_id,
                prompt_category,
                prompt_name,
                prompt_path,
                context_size,
                status,
                exit_code,
                prompt_eval_tps,
                generation_tps,
                total_runtime_sec,
                peak_vram_mib,
                raw_output,
                cleaned_output,
                output_truncated,
                error_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                config["prompt_category"],
                config["prompt_name"],
                config["prompt_rel_path"],
                config["ctx_size"],
                status,
                exit_code,
                prompt_eval_tps,
                generation_tps,
                total_runtime_sec,
                peak_vram_mib,
                stored_raw_output,
                cleaned_output,
                output_truncated,
                error_text,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def run_agent_backend_eval_single(payload: AgentBackendEvalSingleRunRequest) -> dict[str, Any]:
    config = validate_agent_backend_eval_single_request(payload)
    profile = config["profile"]

    run_id = create_agent_backend_eval_run_record(config)

    prompt_text = config["prompt_text"].strip()
    full_prompt = prompt_text

    cmd = [
        LLAMA_COMPLETION,
        "-m", config["model_path"],
        "-ngl", str(profile.get("gpu_layers", 999)),
        "-c", str(config["ctx_size"]),
        "-b", str(profile.get("batch_size", 256)),
        "-ub", str(profile.get("ubatch_size", 64)),
        "--reasoning", str(profile.get("reasoning", "off")),
        "-no-cnv",
        "--no-display-prompt",
        "-n", str(config["max_tokens"]),
        "--temp", str(config["temperature"]),
        "-p", full_prompt,
    ]

    cmd.extend(profile_extra_args(profile))

    result = run_command_capture_with_vram(cmd, timeout=600)

    raw_output = result.get("stdout") or ""
    stderr_text = result.get("stderr") or ""
    cleaned_output, cleaned_changed = clean_eval_output_for_display(raw_output)
    perf = parse_llama_perf(stderr_text)

    try:
        output_tokens, output_token_method = llama_token_count(config["model_path"], cleaned_output)
    except Exception:
        output_tokens, output_token_method = estimate_tokens(cleaned_output), "estimated-token-count-exception"

    if perf["generation_tps"] is None:
        perf["generation_tps"] = fallback_generation_tps(output_tokens, result.get("elapsed_seconds"))

    timed_out = bool(result.get("timed_out"))
    exit_code = int(result.get("returncode") if result.get("returncode") is not None else -1)

    if timed_out:
        status = "timeout"
        error_text = "llama-completion timed out after 600 seconds"
    elif exit_code != 0:
        status = "failed"
        error_text = (stderr_text.strip() or cleaned_output.strip() or f"llama-completion exited with code {exit_code}")[-4000:]
    elif not cleaned_output.strip():
        status = "blank-output"
        error_text = "Run completed but produced blank output"
    else:
        status = "completed"
        error_text = None

    result_id = insert_agent_backend_eval_result_record(
        run_id,
        config,
        status=status,
        exit_code=exit_code,
        raw_output=raw_output,
        cleaned_output=cleaned_output,
        error_text=error_text,
        prompt_eval_tps=perf["prompt_eval_tps"],
        generation_tps=perf["generation_tps"],
        total_runtime_sec=result.get("elapsed_seconds"),
        peak_vram_mib=result.get("vram_peak_mib"),
    )

    update_agent_backend_eval_run_status(
        run_id,
        "completed" if status == "completed" else status,
        error_text,
    )

    return {
        "ok": status == "completed",
        "run_id": run_id,
        "result_id": result_id,
        "status": status,
        "profile": config["profile_key"],
        "model_label": config["model_label"],
        "suite": "agent-eval-v1",
        "prompt": config["prompt_rel_path"],
        "ctx_size": config["ctx_size"],
        "max_tokens": config["max_tokens"],
        "temperature": config["temperature"],
        "elapsed_seconds": result.get("elapsed_seconds"),
        "prompt_eval_tps": perf["prompt_eval_tps"],
        "generation_tps": perf["generation_tps"],
        "peak_vram_mib": result.get("vram_peak_mib"),
        "cleaned_changed": cleaned_changed,
        "output_tokens": output_tokens,
        "output_token_method": output_token_method,
        "output_preview": cleaned_output[:4000],
        "stderr_tail": stderr_text[-2000:],
        "error_text": error_text,
    }


@app.post("/api/eval/agent-backend/run-single")
def api_agent_backend_eval_run_single(payload: AgentBackendEvalSingleRunRequest):
    return run_agent_backend_eval_single(payload)


@app.get("/api/eval/agent-backend/options")
@app.get("/api/eval/hermes/options")
def api_hermes_eval_options():
    return hermes_eval_options_payload()


@app.get("/eval/agent-backend", response_class=HTMLResponse)
@app.get("/eval/hermes", response_class=HTMLResponse)
def eval_hermes(request: Request):
    return templates.TemplateResponse(
        request,
        "eval_hermes.html",
        {
            "title": "Agent Backend Eval",
            "active_testbench_tab": "hermes",
            "summary": load_hermes_eval_summary(),
            "options": hermes_eval_options_payload(),
        },
    )



@app.get("/api/eval/context-scaling/options")
def api_context_scaling_options():
    return context_scaling_options_payload()


@app.post("/api/eval/context-scaling/run")
def api_context_scaling_run(payload: ContextScalingRunRequest):
    config = validate_context_scaling_request(payload)
    context_scaling_run_id = create_context_scaling_run_record(config)
    task_id = str(uuid.uuid4())

    update_eval_task(
        task_id,
        id=task_id,
        kind="context-scaling",
        status="queued",
        created_at_local=current_timestamp_local(),
        profile=config["profile_key"],
        model_label=config["model_label"],
        ctx_size=None,
        max_tokens=config["max_tokens"],
        temperature=config["temperature"],
        contexts=config["contexts"],
        prompts=config["prompts"],
        total_items=len(config["contexts"]) * len(config["prompts"]),
        completed_items=0,
        context_scaling_run_id=context_scaling_run_id,
        result_url=f"/eval/context-scaling/{context_scaling_run_id}",
        detail_url=f"/eval/context-scaling/{context_scaling_run_id}",
        last_message="Queued Context Scaling run.",
    )

    thread = threading.Thread(
        target=run_context_scaling_task_worker,
        args=(
            task_id,
            context_scaling_run_id,
            config["profile_key"],
            config["contexts"],
            config["prompts"],
            config["max_tokens"],
            config["temperature"],
        ),
        daemon=True,
    )
    thread.start()

    return {
        "ok": True,
        "task_id": task_id,
        "context_scaling_run_id": context_scaling_run_id,
        "status_url": f"/api/eval/context-scaling/tasks/{task_id}",
        "result_url": f"/eval/context-scaling/{context_scaling_run_id}",
    }


@app.get("/api/eval/context-scaling/tasks/{task_id}")
def api_context_scaling_task_status(task_id: str):
    return eval_task_snapshot(task_id)


@app.get("/eval/context-scaling", response_class=HTMLResponse)
def eval_context_scaling(request: Request):
    summary = load_context_scaling_summary()
    options = context_scaling_options_payload()

    return templates.TemplateResponse(
        request,
        "eval_context_scaling.html",
        {
            "summary": summary,
            "options": options,
        },
    )


@app.get("/eval/context-scaling/{run_id}", response_class=HTMLResponse)
def eval_context_scaling_detail(request: Request, run_id: int):
    detail = load_context_scaling_detail(run_id)

    return templates.TemplateResponse(
        request,
        "eval_context_scaling_detail.html",
        {
            "run": detail["run"],
            "results": detail["results"],
            "contexts": detail["contexts"],
            "prompts": detail["prompts"],
        },
    )


@app.get("/eval", response_class=HTMLResponse)
def local_eval(request: Request):
    library = load_prompt_library()
    import_summary = load_quant_lab_import_summary()

    return templates.TemplateResponse(
        request,
        "eval.html",
        {
            "library": library,
            "prompt_root": str(PROMPT_SUITE_ROOT),
            "import_summary": import_summary,
            "eval_profiles": active_eval_profiles(),
            "setup": setup_status_payload(),
        },
    )


@app.get("/eval/imports/{suite_run_id}", response_class=HTMLResponse)
def eval_import_detail(request: Request, suite_run_id: int):
    detail = load_quant_lab_import_detail(suite_run_id)

    return templates.TemplateResponse(
        request,
        "eval_import_detail.html",
        {
            "suite": detail["suite"],
            "prompts": detail["prompts"],
            "summary": detail["summary"],
        },
    )




@app.post("/api/eval/run-core-v2")
def api_eval_run_core_v2(payload: EvalRunRequest):
    if payload.profile not in CHAT_PROFILES:
        raise HTTPException(status_code=400, detail=f"Unknown profile: {payload.profile}")

    profile = CHAT_PROFILES[payload.profile]

    if profile.get("active") is not True:
        raise HTTPException(status_code=400, detail="Profile is not active")

    model_path = profile.get("model")
    if not model_path or not Path(model_path).exists():
        raise HTTPException(status_code=400, detail=f"Model file not found: {model_path}")

    safe_ctx = max(1024, min(int(payload.ctx_size), 65536))
    safe_max_tokens = max(64, min(int(payload.max_tokens), 4096))
    safe_temp = max(0.0, min(float(payload.temperature), 2.0))
    safe_include = (payload.include or "").strip()

    allowed_includes = {"", "coding", "config", "docker", "honesty", "linux", "long-context", "niche", "zfs"}
    if safe_include not in allowed_includes:
        raise HTTPException(status_code=400, detail="Invalid include/category filter")

    task_id = str(uuid.uuid4())

    update_eval_task(
        task_id,
        status="queued",
        created_at_local=current_timestamp_local(),
        profile=payload.profile,
        model_label=profile.get("label", payload.profile),
        ctx_size=safe_ctx,
        max_tokens=safe_max_tokens,
        temperature=safe_temp,
        include=safe_include or "all",
        total_items=1 if safe_include else len(load_prompt_library().get("prompts") or []),
        completed_items=0,
        last_message="Queued.",
        id=task_id,
    )

    thread = threading.Thread(
        target=run_eval_task_worker,
        args=(task_id, payload.profile, safe_ctx, safe_max_tokens, safe_temp, safe_include),
        daemon=True,
    )
    thread.start()

    return {
        "ok": True,
        "task_id": task_id,
        "status_url": f"/api/eval/tasks/{task_id}",
    }






def terminate_process_group(pid: int, timeout_seconds: float = 2.0) -> dict[str, Any]:
    """
    Terminate a process group conservatively, then escalate to SIGKILL
    if it does not exit. The eval runner is started with start_new_session=True,
    so the runner shell and child llama-cli should share a process group.
    """
    result: dict[str, Any] = {
        "pid": pid,
        "terminated": False,
        "killed": False,
        "error": None,
    }

    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        result["terminated"] = True
        result["error"] = "process already exited"
        return result
    except Exception as exc:
        result["error"] = f"could not get process group: {exc}"
        return result

    try:
        os.killpg(pgid, signal.SIGTERM)
        result["terminated"] = True
    except ProcessLookupError:
        result["terminated"] = True
        result["error"] = "process group already exited"
        return result
    except Exception as exc:
        result["error"] = f"SIGTERM failed: {exc}"
        return result

    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return result
        except Exception:
            break

        time.sleep(0.1)

    try:
        os.killpg(pgid, signal.SIGKILL)
        result["killed"] = True
    except ProcessLookupError:
        pass
    except Exception as exc:
        result["error"] = f"SIGKILL failed: {exc}"

    return result


def list_stale_eval_process_candidates() -> list[dict[str, Any]]:
    """
    Find likely stale Local Eval processes. This intentionally does not target
    arbitrary GPU processes. It only returns commands that look like Monolith /
    Quant Lab eval runner activity.
    """
    try:
        completed = subprocess.run(
            ["ps", "-eo", "pid=,ppid=,pgid=,stat=,cmd="],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5,
        )
    except Exception:
        return []

    if completed.returncode != 0:
        return []

    candidates: list[dict[str, Any]] = []

    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split(None, 4)
        if len(parts) < 5:
            continue

        pid_text, ppid_text, pgid_text, stat, cmd = parts

        try:
            pid = int(pid_text)
            ppid = int(ppid_text)
            pgid = int(pgid_text)
        except ValueError:
            continue

        own_pid = os.getpid()
        if pid == own_pid:
            continue

        cmd_lower = cmd.lower()

        looks_like_eval_runner = (
            "run-core-v2-suite.sh" in cmd_lower
            or "quant-lab" in cmd_lower
            or "core-v2" in cmd_lower
        )

        looks_like_llama_eval = (
            "llama-cli" in cmd_lower
            and (
                "--single-turn" in cmd_lower
                or "--simple-io" in cmd_lower
                or "--no-display-prompt" in cmd_lower
                or "core-v2" in cmd_lower
                or "quant-lab" in cmd_lower
            )
        )

        if not (looks_like_eval_runner or looks_like_llama_eval):
            continue

        candidates.append(
            {
                "pid": pid,
                "ppid": ppid,
                "pgid": pgid,
                "stat": stat,
                "cmd": cmd,
            }
        )

    return candidates


@app.post("/api/eval/tasks/{task_id}/abort")
def api_eval_task_abort(task_id: str):
    with EVAL_TASK_LOCK:
        task = EVAL_TASKS.get(task_id)
        process = EVAL_TASK_PROCESSES.get(task_id)

        if not task:
            raise HTTPException(status_code=404, detail="Eval task not found")

        status = task.get("status")

        if status in {"completed", "failed", "aborted"}:
            return eval_task_snapshot(task_id)

        task["abort_requested"] = True
        task["status"] = "aborting"
        task["last_message"] = "Abort requested. Stopping Quant Lab runner..."
        task["updated_at_local"] = current_timestamp_local()

    cleanup_result = None

    if process and process.poll() is None:
        cleanup_result = terminate_process_group(process.pid, timeout_seconds=2.0)

    update_eval_task(
        task_id,
        status="aborted",
        exit_code=-15,
        completed_at_local=current_timestamp_local(),
        last_message="Local Eval run aborted by user.",
        cleanup_result=cleanup_result,
    )

    with EVAL_TASK_LOCK:
        EVAL_TASK_PROCESSES.pop(task_id, None)

    return eval_task_snapshot(task_id)




@app.post("/api/eval/cleanup-stale")
def api_eval_cleanup_stale():
    candidates = list_stale_eval_process_candidates()
    cleaned: list[dict[str, Any]] = []

    for candidate in candidates:
        pid = int(candidate["pid"])

        # Do not terminate the current web process.
        if pid == os.getpid():
            continue

        result = terminate_process_group(pid, timeout_seconds=2.0)
        cleaned.append(
            {
                "pid": pid,
                "cmd": candidate["cmd"],
                "result": result,
            }
        )

    return {
        "ok": True,
        "candidate_count": len(candidates),
        "cleaned_count": len(cleaned),
        "cleaned": cleaned,
    }


@app.get("/api/eval/tasks/{task_id}")
def api_eval_task_status(task_id: str):
    return eval_task_snapshot(task_id)


@app.get("/eval/prompts/{category}/{filename}", response_class=HTMLResponse)
def eval_prompt_detail(request: Request, category: str, filename: str):
    prompt = load_prompt_detail(category, filename)

    return templates.TemplateResponse(
        request,
        "eval_prompt_detail.html",
        {
            "prompt": prompt,
        },
    )


class ModelDownloadPlanRequest(BaseModel):
    source_repo_id: str
    source_filename: str
    size_bytes: int | None = None
    local_match: bool = False
    overwrite_existing: bool = False
    notes: str | None = None


def model_downloader_tables_exist() -> bool:
    if not DB_PATH.exists():
        return False

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'model_download_jobs'
            """
        ).fetchall()

    return len(rows) == 1


def approved_model_download_root() -> Path:
    return env_path(
        "MONOLITH_MODEL_DOWNLOAD_ROOT",
        Path.home() / "Monolith/models/huggingface",
    )


def safe_download_repo_dir(repo_id: str) -> str:
    safe_repo_id = safe_huggingface_repo_id(repo_id)

    parts = safe_repo_id.split("/")
    if len(parts) != 2:
        raise HTTPException(status_code=400, detail="Expected Hugging Face repo id in owner/name form.")

    owner, repo = parts
    safe = f"{owner}--{repo}"

    if ".." in safe or "/" in safe or safe.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid repository-derived destination directory.")

    return safe


def safe_source_gguf_filename(source_filename: str) -> str:
    source_filename = (source_filename or "").strip()

    if not source_filename:
        raise HTTPException(status_code=400, detail="Source filename is required.")

    if source_filename.startswith("/") or ".." in Path(source_filename).parts:
        raise HTTPException(status_code=400, detail="Invalid source filename.")

    basename = Path(source_filename).name

    if not basename.lower().endswith(".gguf"):
        raise HTTPException(status_code=400, detail="Only GGUF files can be planned for download.")

    lowered = basename.lower()
    if lowered.startswith("mmproj-") or "mmproj" in lowered:
        raise HTTPException(status_code=400, detail="mmproj files are excluded from model download planning.")

    if basename in {"", ".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid source filename.")

    return basename


def planned_download_destination(repo_id: str, source_filename: str) -> dict[str, str]:
    root = approved_model_download_root().expanduser()
    repo_dir = safe_download_repo_dir(repo_id)
    filename = safe_source_gguf_filename(source_filename)

    destination_dir = root / repo_dir
    destination_path = destination_dir / filename

    root_resolved = root.resolve(strict=False)
    destination_resolved = destination_path.resolve(strict=False)

    try:
        destination_resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Planned destination escapes approved download root.") from exc

    return {
        "destination_root": str(root_resolved),
        "destination_dir": str(destination_dir.resolve(strict=False)),
        "destination_path": str(destination_resolved),
        "filename": filename,
    }


def huggingface_resolve_url(repo_id: str, source_filename: str) -> str:
    import urllib.parse

    safe_repo_id = safe_huggingface_repo_id(repo_id)
    safe_source_filename = source_filename.strip()

    if safe_source_filename.startswith("/") or ".." in Path(safe_source_filename).parts:
        raise HTTPException(status_code=400, detail="Invalid source filename.")

    encoded_filename = urllib.parse.quote(safe_source_filename, safe="/")
    return f"https://huggingface.co/{safe_repo_id}/resolve/main/{encoded_filename}"


def format_bytes_compact(value: int | float | None) -> str:
    if value is None:
        return "unknown"

    value = float(value)
    units = ["B", "KiB", "MiB", "GiB", "TiB"]

    for unit in units:
        if abs(value) < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.2f} {unit}"
        value /= 1024.0

    return f"{value:.2f} TiB"


def format_duration_compact(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"

    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:d}:{secs:02d}"


def parse_local_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    value = value.strip()

    # current_timestamp_local() stores values like:
    # 2026-06-10 19:02:36 EDT
    if value.endswith(" EDT") or value.endswith(" EST"):
        value = value.rsplit(" ", 1)[0]

    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def enrich_model_download_job(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)

    bytes_downloaded = int(item.get("bytes_downloaded") or 0)
    expected_size = item.get("expected_size_bytes") or item.get("size_bytes")

    if expected_size is not None:
        expected_size = int(expected_size)

    if expected_size is None and item.get("status") == "completed":
        expected_size = bytes_downloaded

    item["bytes_downloaded_display"] = format_bytes_compact(bytes_downloaded)
    item["expected_size_display"] = format_bytes_compact(expected_size)

    if expected_size and expected_size > 0:
        item["progress_percent"] = round(min(100.0, (bytes_downloaded / expected_size) * 100.0), 1)
        item["progress_display"] = f"{item['bytes_downloaded_display']} / {item['expected_size_display']} · {item['progress_percent']}%"
    else:
        item["progress_percent"] = None
        item["progress_display"] = item["bytes_downloaded_display"]

    started_at = parse_local_timestamp(item.get("started_at"))
    completed_at = parse_local_timestamp(item.get("completed_at"))
    now = datetime.now()

    if started_at and completed_at:
        elapsed_seconds = (completed_at - started_at).total_seconds()
    elif started_at:
        elapsed_seconds = (now - started_at).total_seconds()
    else:
        elapsed_seconds = None

    item["elapsed_seconds"] = int(elapsed_seconds) if elapsed_seconds is not None else None
    item["runtime_display"] = format_duration_compact(elapsed_seconds)

    if elapsed_seconds and elapsed_seconds > 0 and bytes_downloaded > 0:
        rate_bps = bytes_downloaded / elapsed_seconds
    else:
        rate_bps = None

    item["transfer_rate_bps"] = int(rate_bps) if rate_bps else None
    item["transfer_rate_display"] = f"{format_bytes_compact(rate_bps)}/s" if rate_bps else "—"

    if (
        item.get("status") == "running"
        and expected_size
        and rate_bps
        and bytes_downloaded < expected_size
    ):
        eta_seconds = (expected_size - bytes_downloaded) / rate_bps
    else:
        eta_seconds = None

    item["eta_seconds"] = int(eta_seconds) if eta_seconds is not None else None
    item["eta_display"] = format_duration_compact(eta_seconds)

    size_bytes = expected_size or bytes_downloaded or None
    item["size_gib"] = round(float(size_bytes) / (1024 ** 3), 2) if size_bytes else None
    item["destination_exists"] = Path(item["destination_path"]).expanduser().exists()

    return item


def load_model_download_jobs(limit: int = 50) -> list[dict[str, Any]]:
    if not model_downloader_tables_exist():
        return []

    rows = db_rows(
        """
        SELECT *
        FROM model_download_jobs
        ORDER BY id DESC
        LIMIT ?
        """,
        (max(1, min(int(limit or 50), 200)),),
    )

    return [enrich_model_download_job(row) for row in rows]


def plan_model_download_job(payload: ModelDownloadPlanRequest) -> dict[str, Any]:
    if not model_downloader_tables_exist():
        raise HTTPException(status_code=500, detail="Model downloader tables not found. Run migration first.")

    repo_id = safe_huggingface_repo_id(payload.source_repo_id)
    source_filename = payload.source_filename.strip()
    destination = planned_download_destination(repo_id, source_filename)
    source_url = huggingface_resolve_url(repo_id, source_filename)
    filename = destination["filename"]

    destination_path = Path(destination["destination_path"])
    destination_exists = destination_path.exists()

    if destination_exists and not payload.overwrite_existing:
        raise HTTPException(
            status_code=409,
            detail="Destination file already exists. Refusing to plan overwrite.",
        )

    existing = db_one(
        """
        SELECT *
        FROM model_download_jobs
        WHERE destination_path = ?
        """,
        (destination["destination_path"],),
    )

    if existing and not payload.overwrite_existing:
        raise HTTPException(
            status_code=409,
            detail="A download job already exists for this destination path.",
        )

    now = current_timestamp_local()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO model_download_jobs (
                created_at,
                updated_at,
                status,
                source_type,
                source_repo_id,
                source_filename,
                source_url,
                destination_root,
                destination_dir,
                destination_path,
                filename,
                size_bytes,
                expected_size_bytes,
                family_guess,
                quant_guess,
                architecture_guess,
                local_match,
                overwrite_existing,
                bytes_downloaded,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                now,
                "planned",
                "huggingface",
                repo_id,
                source_filename,
                source_url,
                destination["destination_root"],
                destination["destination_dir"],
                destination["destination_path"],
                filename,
                payload.size_bytes,
                payload.size_bytes,
                guess_model_family_from_filename(filename),
                guess_quant_from_filename(filename),
                guess_architecture_from_filename(filename),
                1 if payload.local_match or destination_exists else 0,
                1 if payload.overwrite_existing else 0,
                0,
                payload.notes,
            ),
        )

        conn.commit()
        job_id = cursor.lastrowid

    row = db_one(
        """
        SELECT *
        FROM model_download_jobs
        WHERE id = ?
        """,
        (job_id,),
    )

    if not row:
        raise HTTPException(status_code=500, detail="Planned job was not found after insert.")

    row["destination_exists"] = destination_exists
    row["download_enabled"] = False
    row["policy"] = {
        "planning_only": True,
        "downloads_enabled": False,
        "config_edits_enabled": False,
        "model_execution_enabled": False,
        "approved_download_root": str(approved_model_download_root().expanduser()),
    }

    return row


MODEL_DOWNLOAD_TASKS: dict[int, threading.Thread] = {}
MODEL_DOWNLOAD_TASK_LOCK = threading.Lock()


def get_model_download_job(job_id: int) -> dict[str, Any]:
    if not model_downloader_tables_exist():
        raise HTTPException(status_code=500, detail="Model downloader tables not found. Run migration first.")

    row = db_one(
        """
        SELECT *
        FROM model_download_jobs
        WHERE id = ?
        """,
        (job_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail=f"Download job not found: {job_id}")

    return row


def update_model_download_job(job_id: int, **fields: Any) -> None:
    if not fields:
        return

    allowed = {
        "updated_at",
        "started_at",
        "completed_at",
        "status",
        "bytes_downloaded",
        "expected_size_bytes",
        "error_text",
        "notes",
    }

    unknown = set(fields) - allowed
    if unknown:
        raise ValueError(f"Unsupported download job update fields: {sorted(unknown)}")

    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = tuple(fields[key] for key in fields)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            f"""
            UPDATE model_download_jobs
            SET {assignments}
            WHERE id = ?
            """,
            values + (job_id,),
        )
        conn.commit()


def assert_download_destination_is_safe(destination_path: str) -> Path:
    root = approved_model_download_root().expanduser().resolve(strict=False)
    destination = Path(destination_path).expanduser().resolve(strict=False)

    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("Download destination escapes approved download root.") from exc

    if destination.suffix.lower() != ".gguf":
        raise RuntimeError("Download destination must be a GGUF file.")

    if destination.name.lower().startswith("mmproj-") or "mmproj" in destination.name.lower():
        raise RuntimeError("mmproj files are excluded from download execution.")

    return destination


def download_model_job(job_id: int) -> None:
    import urllib.error
    import urllib.request

    job = get_model_download_job(job_id)
    now = current_timestamp_local()

    try:
        destination = assert_download_destination_is_safe(job["destination_path"])
        part_path = destination.with_name(destination.name + ".part")

        if destination.exists() and not int(job.get("overwrite_existing") or 0):
            raise RuntimeError("Destination file already exists. Refusing to overwrite.")

        destination.parent.mkdir(parents=True, exist_ok=True)

        update_model_download_job(
            job_id,
            updated_at=now,
            started_at=now,
            completed_at=None,
            status="running",
            bytes_downloaded=0,
            error_text=None,
        )

        request = urllib.request.Request(
            job["source_url"],
            headers={
                "User-Agent": "Monolith-Local-AI-Workbench/alpha",
            },
            method="GET",
        )

        bytes_downloaded = 0
        last_update = time.time()

        with urllib.request.urlopen(request, timeout=30) as response:
            content_length = response.headers.get("Content-Length")
            if content_length and not job.get("expected_size_bytes"):
                try:
                    expected_size_from_response = int(content_length)
                    update_model_download_job(
                        job_id,
                        updated_at=current_timestamp_local(),
                        expected_size_bytes=expected_size_from_response,
                    )
                    job["expected_size_bytes"] = expected_size_from_response
                except ValueError:
                    pass

            with part_path.open("wb") as handle:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break

                    handle.write(chunk)
                    bytes_downloaded += len(chunk)

                    if time.time() - last_update >= 1.0:
                        update_model_download_job(
                            job_id,
                            updated_at=current_timestamp_local(),
                            bytes_downloaded=bytes_downloaded,
                        )
                        last_update = time.time()

        expected_size = job.get("expected_size_bytes") or job.get("size_bytes")
        if expected_size and bytes_downloaded != int(expected_size):
            raise RuntimeError(
                f"Downloaded size mismatch: expected {expected_size} bytes, got {bytes_downloaded} bytes."
            )

        part_path.replace(destination)

        completed_at = current_timestamp_local()
        update_model_download_job(
            job_id,
            updated_at=completed_at,
            completed_at=completed_at,
            status="completed",
            bytes_downloaded=bytes_downloaded,
            error_text=None,
        )

        try:
            scan_local_model_inventory()
        except Exception as exc:
            update_model_download_job(
                job_id,
                updated_at=current_timestamp_local(),
                notes=f"Download completed. Local inventory rescan failed: {exc}",
            )

    except Exception as exc:
        failed_at = current_timestamp_local()
        update_model_download_job(
            job_id,
            updated_at=failed_at,
            completed_at=failed_at,
            status="failed",
            error_text=str(exc),
        )
    finally:
        with MODEL_DOWNLOAD_TASK_LOCK:
            MODEL_DOWNLOAD_TASKS.pop(job_id, None)


def start_model_download_job(job_id: int) -> dict[str, Any]:
    job = get_model_download_job(job_id)
    status = job.get("status")

    if status not in {"planned", "failed"}:
        raise HTTPException(
            status_code=409,
            detail=f"Download job cannot be started from status: {status}",
        )

    destination = assert_download_destination_is_safe(job["destination_path"])

    if destination.exists() and not int(job.get("overwrite_existing") or 0):
        raise HTTPException(
            status_code=409,
            detail="Destination file already exists. Refusing to overwrite.",
        )

    with MODEL_DOWNLOAD_TASK_LOCK:
        if job_id in MODEL_DOWNLOAD_TASKS:
            raise HTTPException(status_code=409, detail="Download job is already running.")

        thread = threading.Thread(
            target=download_model_job,
            args=(job_id,),
            daemon=True,
            name=f"monolith-model-download-{job_id}",
        )
        MODEL_DOWNLOAD_TASKS[job_id] = thread
        thread.start()

    started = get_model_download_job(job_id)
    started["destination_exists"] = Path(started["destination_path"]).expanduser().exists()
    started["download_enabled"] = True
    return started


@app.post("/api/models/downloads/{job_id}/start")
def api_models_downloads_start(job_id: int):
    return {
        "ok": True,
        "job": start_model_download_job(job_id),
    }


@app.get("/api/models/downloads")
def api_models_downloads(limit: int = 50):
    return {
        "ok": True,
        "downloads_enabled": False,
        "approved_download_root": str(approved_model_download_root().expanduser()),
        "jobs": load_model_download_jobs(limit),
    }


@app.post("/api/models/downloads/plan")
def api_models_downloads_plan(payload: ModelDownloadPlanRequest):
    return {
        "ok": True,
        "job": plan_model_download_job(payload),
    }


@app.get("/api/models/discover/huggingface")
def api_models_discover_huggingface(q: str, limit: int = 10):
    return search_huggingface_gguf_models(q, limit)


@app.post("/api/models/local-inventory/scan")
def api_models_local_inventory_scan():
    return scan_local_model_inventory()


@app.post("/api/models/downloads/clear-planned")
def api_models_downloads_clear_planned():
    if not model_downloader_tables_exist():
        raise HTTPException(
            status_code=500,
            detail="model_download_jobs table is missing. Run scripts/migrate_model_downloader.py.",
        )

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            DELETE FROM model_download_jobs
            WHERE status = 'planned'
            """
        )
        conn.commit()
        deleted = int(cursor.rowcount or 0)

    return {
        "deleted": deleted,
        "message": f"Cleared {deleted} planned download job(s).",
    }


@app.post("/api/models/local/{model_id}/create-chat-profile")
def api_models_local_create_chat_profile(
    model_id: int,
    payload: CreateLocalModelChatProfileRequest | None = None,
):
    return create_generated_chat_profile_from_local_model(model_id, payload)


def load_local_model_detail(model_id: int) -> dict[str, Any]:
    if not model_registry_tables_exist():
        raise HTTPException(
            status_code=500,
            detail="local_model_files table is missing. Run scripts/migrate_model_registry.py.",
        )

    row = db_one(
        """
        SELECT *
        FROM local_model_files
        WHERE id = ?
        """,
        (model_id,),
    )

    if not row:
        raise HTTPException(status_code=404, detail=f"Local model not found: {model_id}")

    try:
        row["registered_profile_keys"] = json.loads(row.get("registered_profile_keys_json") or "[]")
    except Exception:
        row["registered_profile_keys"] = []

    generated_profile_map = generated_chat_profile_keys_by_model_path()
    row["generated_profile_keys"] = generated_profile_map.get(str(row.get("local_path") or ""), [])

    if row["generated_profile_keys"]:
        row["registered_profile_keys"] = list(
            dict.fromkeys(row["registered_profile_keys"] + row["generated_profile_keys"])
        )

    if row["registered_profile_keys"] and row.get("status") == "discovered":
        row["status"] = "registered"

    size_bytes = int(row.get("size_bytes") or 0)
    row["size_gib"] = round(float(size_bytes) / (1024 ** 3), 2)
    row["path_exists"] = Path(str(row.get("local_path") or "")).expanduser().exists()

    return row


def load_model_download_job_detail(job_id: int) -> dict[str, Any]:
    if not model_downloader_tables_exist():
        raise HTTPException(
            status_code=500,
            detail="model_download_jobs table is missing. Run scripts/migrate_model_downloader.py.",
        )

    row = get_model_download_job(job_id)

    if not row:
        raise HTTPException(status_code=404, detail=f"Download job not found: {job_id}")

    return enrich_model_download_job(row)


@app.get("/models/local/{model_id}", response_class=HTMLResponse)
def model_local_detail(request: Request, model_id: int):
    row = load_local_model_detail(model_id)

    return templates.TemplateResponse(
        request,
        "model_local_detail.html",
        {
            "row": row,
        },
    )


@app.get("/models/downloads/{job_id}", response_class=HTMLResponse)
def model_download_detail(request: Request, job_id: int):
    job = load_model_download_job_detail(job_id)

    return templates.TemplateResponse(
        request,
        "model_download_detail.html",
        {
            "job": job,
        },
    )


@app.get("/models", response_class=HTMLResponse)
def models(request: Request):
    rows = load_models_for_page()
    chat_rows = [row for row in rows if row.get("kind") == "chat_profile"]
    catalog_rows = [row for row in rows if row.get("kind") != "chat_profile"]
    local_inventory = load_local_model_inventory()
    download_jobs = load_model_download_jobs(25)

    found_count = sum(1 for row in rows if row.get("path_status", {}).get("exists"))
    missing_count = sum(
        1
        for row in rows
        if row.get("path_status", {}).get("configured")
        and not row.get("path_status", {}).get("exists")
    )
    active_count = sum(1 for row in chat_rows if row.get("active") is True)

    return templates.TemplateResponse(
        request,
        "models.html",
        {
            "rows": rows,
            "chat_rows": chat_rows,
            "catalog_rows": catalog_rows,
            "local_inventory": local_inventory,
            "download_jobs": download_jobs,
            "found_count": found_count,
            "missing_count": missing_count,
            "active_count": active_count,
            "registry_path": str(MODELS_CONFIG),
            "setup": setup_status_payload(),
        },
    )


@app.get("/workstation", response_class=HTMLResponse)
def workstation(request: Request):
    stats = get_workstation_stats()

    return templates.TemplateResponse(
        request,
        "workstation.html",
        {
            "stats": stats,
        },
    )


@app.get("/chat", response_class=HTMLResponse)
def chat(request: Request):
    return templates.TemplateResponse(
        request,
        "chat.html",
        {
            "profiles": current_chat_profiles(),
            "setup": setup_status_payload(),
        },
    )


@app.post("/api/chat")
def api_chat(payload: ChatRequest):
    return run_llama_chat(
        profile_name=payload.profile,
        prompt=payload.prompt,
        max_tokens=payload.max_tokens,
        mode=payload.mode,
    )


@app.post("/api/chat/save-run")
def api_chat_save_run(payload: SaveChatRunRequest):
    return save_chat_run(payload)


def clamp_score(value: int | None) -> int | None:
    if value is None:
        return None

    return max(0, min(10, int(value)))


def score_run(run_id: int, payload: ScoreRunRequest) -> dict[str, Any]:
    existing = db_one("SELECT id FROM runs WHERE id = ?", (run_id,))

    if not existing:
        raise HTTPException(status_code=404, detail="Run not found")

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO scores (
                run_id,
                timestamp_local,
                factual_accuracy,
                technical_correctness,
                safety,
                instruction_following,
                concision,
                hallucination_severity,
                overall_trust,
                winner_tag,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                current_timestamp_local(),
                clamp_score(payload.factual_accuracy),
                clamp_score(payload.technical_correctness),
                clamp_score(payload.safety),
                clamp_score(payload.instruction_following),
                clamp_score(payload.concision),
                clamp_score(payload.hallucination_severity),
                clamp_score(payload.overall_trust),
                (payload.winner_tag or "").strip() or None,
                (payload.notes or "").strip() or None,
            ),
        )

        conn.commit()
        score_id = cursor.lastrowid

    return {
        "ok": True,
        "score_id": score_id,
        "run_id": run_id,
        "detail_url": f"/runs/{run_id}",
    }


@app.post("/api/runs/{run_id}/score")
def api_score_run(run_id: int, payload: ScoreRunRequest):
    return score_run(run_id, payload)


def read_meminfo() -> dict[str, int]:
    values = {}

    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as handle:
            for line in handle:
                key, raw_value = line.split(":", 1)
                value_kib = int(raw_value.strip().split()[0])
                values[key] = value_kib
    except (FileNotFoundError, ValueError, IndexError):
        return {}

    return values


def _read_linux_meminfo() -> dict[str, int]:
    meminfo_path = Path("/proc/meminfo")
    if not meminfo_path.exists():
        return {}

    values: dict[str, int] = {}
    try:
        for line in meminfo_path.read_text().splitlines():
            if ":" not in line:
                continue
            key, raw_value = line.split(":", 1)
            parts = raw_value.strip().split()
            if not parts:
                continue
            values[key] = int(parts[0])
    except (OSError, ValueError):
        return {}

    return values


def _get_memory_stats() -> dict[str, Any]:
    meminfo = _read_linux_meminfo()
    total_kib = meminfo.get("MemTotal")
    available_kib = meminfo.get("MemAvailable")

    if not total_kib or available_kib is None:
        return {
            "available": False,
            "used_mib": None,
            "total_mib": None,
            "used_percent": None,
            "error": "memory stats unavailable",
        }

    used_kib = max(total_kib - available_kib, 0)
    return {
        "available": True,
        "used_mib": round(used_kib / 1024),
        "total_mib": round(total_kib / 1024),
        "used_percent": round((used_kib / total_kib) * 100, 1) if total_kib else None,
        "error": None,
    }


def _get_cpu_stats() -> dict[str, Any]:
    cpu_count = os.cpu_count() or 1

    try:
        load_1m, load_5m, load_15m = os.getloadavg()
        load_available = True
        error = None
    except (AttributeError, OSError):
        load_1m = load_5m = load_15m = None
        load_available = False
        error = "load average unavailable"

    return {
        "available": load_available,
        "cores": cpu_count,
        "load_1m": round(load_1m, 2) if load_1m is not None else None,
        "load_5m": round(load_5m, 2) if load_5m is not None else None,
        "load_15m": round(load_15m, 2) if load_15m is not None else None,
        "load_percent": round((load_1m / cpu_count) * 100, 1) if load_1m is not None and cpu_count else None,
        "error": error,
    }


def _get_disk_stats(path: str = "/") -> dict[str, Any]:
    try:
        usage = shutil.disk_usage(path)
    except OSError as exc:
        return {
            "available": False,
            "path": path,
            "used_gib": None,
            "total_gib": None,
            "free_gib": None,
            "used_percent": None,
            "error": str(exc),
        }

    used = usage.total - usage.free
    return {
        "available": True,
        "path": path,
        "used_gib": round(used / (1024 ** 3), 1),
        "total_gib": round(usage.total / (1024 ** 3), 1),
        "free_gib": round(usage.free / (1024 ** 3), 1),
        "used_percent": round((used / usage.total) * 100, 1) if usage.total else None,
        "error": None,
    }


def _get_gpu_stats() -> dict[str, Any]:
    gpu = {
        "available": False,
        "vendor": None,
        "util_percent": None,
        "vram_used_mib": None,
        "vram_total_mib": None,
        "vram_used_percent": None,
        "temperature_c": None,
        "power_w": None,
        "error": "GPU monitor unavailable",
    }

    nvidia_query = [
        "nvidia-smi",
        "--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
        "--format=csv,noheader,nounits",
    ]

    try:
        completed = subprocess.run(
            nvidia_query,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=2,
        )
        if completed.returncode == 0 and completed.stdout.strip():
            first_gpu = completed.stdout.strip().splitlines()[0]
            parts = [part.strip() for part in first_gpu.split(",")]
            util = float(parts[0])
            vram_used = float(parts[1])
            vram_total = float(parts[2])
            temperature = float(parts[3])
            power = float(parts[4]) if parts[4] not in {"", "[Not Supported]"} else None
            return {
                "available": True,
                "vendor": "nvidia",
                "util_percent": round(util, 1),
                "vram_used_mib": round(vram_used),
                "vram_total_mib": round(vram_total),
                "vram_used_percent": round((vram_used / vram_total) * 100, 1) if vram_total else None,
                "temperature_c": round(temperature, 1),
                "power_w": round(power, 1) if power is not None else None,
                "error": None,
            }

        gpu["error"] = completed.stderr.strip()[-500:] or "nvidia-smi returned no GPU data"
    except FileNotFoundError:
        gpu["error"] = "nvidia-smi not found"
    except subprocess.TimeoutExpired:
        gpu["error"] = "nvidia-smi timed out"
    except (ValueError, IndexError) as exc:
        gpu["error"] = f"failed to parse nvidia-smi output: {exc}"

    return gpu


def get_workstation_stats() -> dict[str, Any]:
    return {
        "host": {
            "hostname": platform.node() or "unknown",
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "cpu": _get_cpu_stats(),
        "memory": _get_memory_stats(),
        "disk": _get_disk_stats("/"),
        "gpu": _get_gpu_stats(),
        "sampled_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }

@app.get("/api/workstation-stats")
def api_workstation_stats():
    return get_workstation_stats()


@app.get("/file", response_class=PlainTextResponse)
def read_file(path: str):
    candidate = (ROOT / path).resolve()

    if ROOT not in candidate.parents and candidate != ROOT:
        raise HTTPException(status_code=400, detail="Path outside project root")

    if not candidate.exists():
        raise HTTPException(status_code=404, detail="File not found")

    if candidate.is_dir():
        raise HTTPException(status_code=400, detail="Path is a directory")

    return candidate.read_text(encoding="utf-8", errors="replace")


@app.get("/api/context")
def api_context():
    rows = db_rows(
        """
        SELECT
            id,
            timestamp_local,
            launcher,
            ctx_size,
            prompt_eval_tps,
            generation_tps,
            vram_peak_mb,
            prompt_category,
            notes
        FROM runs
        WHERE prompt_category = 'context-scaling'
        ORDER BY ctx_size ASC, id ASC
        """
    )

    return attach_prompt_family(rows)


# ---------------------------------------------------------------------------
# Agent Lab routes
# ---------------------------------------------------------------------------

@app.get("/agents", response_class=HTMLResponse)
def agent_lab_home(request: Request):
    return templates.TemplateResponse(
        request,
        "agents.html",
        {
            "title": "Agent Lab",
            "sessions": load_agent_sessions(),
        },
    )


@app.get("/agents/new", response_class=HTMLResponse)
def agent_lab_new(request: Request):
    return templates.TemplateResponse(
        request,
        "agents_new.html",
        {
            "title": "New Agent Session",
            "model_profiles": load_agent_model_profiles(),
        },
    )


@app.post("/agents/new")
async def agent_lab_create(request: Request):
    from urllib.parse import parse_qs

    raw_body = (await request.body()).decode("utf-8")
    parsed = parse_qs(raw_body, keep_blank_values=True)

    def field(name: str, default: str = "") -> str:
        values = parsed.get(name)
        if not values:
            return default
        return values[-1].strip()

    session_id = create_agent_session(
        name=field("name"),
        goal=field("goal"),
        model_profile_name=field("model_profile_name") or None,
        mode=field("mode", "proposal_only"),
        workspace_label=field("workspace_label") or None,
        workspace_path=field("workspace_path") or None,
        context_summary=field("context_summary") or None,
        safety_notes=field("safety_notes") or None,
    )
    return RedirectResponse(url=f"/agents/{session_id}", status_code=303)


@app.post("/agents/{session_id}/archive")
def agent_lab_archive(session_id: int):
    archived = archive_agent_session(session_id)
    if not archived:
        raise HTTPException(status_code=404, detail=f"Agent session not found: {session_id}")

    return RedirectResponse(url="/agents", status_code=303)


@app.get("/agents/{session_id}", response_class=HTMLResponse)
def agent_lab_detail(request: Request, session_id: int):
    session = load_agent_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")

    related = load_agent_session_related(session_id)

    return templates.TemplateResponse(
        request,
        "agent_detail.html",
        {
            "title": f"Agent Session #{session_id}",
            "session": session,
            "plans": related["plans"],
            "proposals": related["proposals"],
            "reviews": related["reviews"],
        },
    )

#!/usr/bin/env python3
"""TCSA economical task router: advisory only, no model or network calls.

Never assumes that an executor exists. Sensitive data is never exported by this tool.
"""
import argparse
import json
from pathlib import Path

DETERMINISTIC_KINDS = frozenset({"inventory", "hash", "diff", "build", "test", "package", "readback", "search"})

def decide(task):
    kind = str(task.get("kind", "unknown")).lower()
    previous = int(task.get("sameApproachFailures", 0))
    new_evidence = bool(task.get("newDiagnosticEvidence", False))
    restricted = bool(task.get("protectedOperation", False))
    deterministic = bool(task.get("deterministicAvailable", kind in DETERMINISTIC_KINDS))
    local = bool(task.get("localModelAvailable", False))
    critical = str(task.get("risk", "low")).lower() in {"high", "critical"}
    explicit = bool(task.get("expertReviewRequested", False))
    cloud_scope = bool(task.get("approvedRemoteDataScope", False))
    cloud_authorized = bool(task.get("remoteExpertAuthorized", False))
    budget = int(task.get("remoteCallsRemaining", 0))
    base = {"schema": "tcsa.router.decision.v1", "dryRun": True,
            "networkCallsMade": 0, "reason": "", "route": None,
            "note": "Recommendation only; do not infer a running agent or accepted job"}
    if restricted:
        base.update(route="BLOCKED", reason="PROTECTED_ACTION_REQUIRES_SEPARATE_AUTHORITY_AND_ROLLBACK")
    elif previous >= 2 and not new_evidence:
        base.update(route="BLOCKED", reason="STALE_RETRY_REQUIRES_NEW_EVIDENCE")
    elif deterministic and not critical and not explicit:
        base.update(route="L0_DETERMINISTIC", reason="REPRODUCIBLE_TOOL_WORK")
    elif local and not critical and not explicit and previous < 2:
        base.update(route="L1_LOCAL_MODEL", reason="LOCAL_VERIFIED_EXECUTOR_REQUIRED")
    elif cloud_authorized and cloud_scope and budget > 0:
        base.update(route="L2_REMOTE_EXPERT", reason="EXPERT_JUDGMENT_WITH_AUTHORIZED_SCOPE_AND_BUDGET")
    elif local and not critical:
        base.update(route="L1_LOCAL_MODEL", reason="FURTHER_LOCAL_DIAGNOSTICS_REQUIRED")
    else:
        base.update(route="BLOCKED", reason="NO_SAFE_EXECUTOR_OR_REMOTE_AUTHORIZATION")
    return base

def main():
    parser = argparse.ArgumentParser(description="Select lowest-cost suitable work route; no execution")
    parser.add_argument("task_json", type=Path)
    args = parser.parse_args()
    task = json.loads(args.task_json.read_text(encoding="utf-8"))
    print(json.dumps(decide(task), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

"""Setup diagnostics — verify that all prerequisites are met.

Run with:  copilot-teams-doctor
       or: python -m bridge.doctor
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

from bridge import config


def _check(label: str, ok: bool, detail: str = ""):
    icon = "✅" if ok else "❌"
    msg = f"  {icon} {label}"
    if detail:
        msg += f"  ({detail})"
    print(msg)
    return ok


def main():
    print("\n🔍 Copilot Teams Bridge — Doctor\n")
    all_ok = True

    # 1. Python version
    v = sys.version_info
    all_ok &= _check(
        f"Python {v.major}.{v.minor}.{v.micro}",
        v >= (3, 10),
        "3.10+ required",
    )

    # 2. Copilot CLI
    copilot_path = shutil.which("copilot")
    all_ok &= _check(
        "Copilot CLI installed",
        copilot_path is not None,
        copilot_path or "not found in PATH",
    )

    # 3. GitHub auth
    gh_auth = False
    try:
        r = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, timeout=5
        )
        gh_auth = r.returncode == 0
    except Exception:
        pass
    all_ok &= _check("GitHub CLI authenticated", gh_auth)

    # 4. Teams webhook
    has_webhook = bool(config.TEAMS_WEBHOOK_URL)
    all_ok &= _check(
        "TEAMS_WEBHOOK_URL configured",
        has_webhook,
        "set in .env or environment" if not has_webhook else "set",
    )

    # 5. Teams commands directory
    dir_ok = bool(config.TEAMS_COMMANDS_DIR) and os.path.isdir(config.TEAMS_COMMANDS_DIR)
    all_ok &= _check(
        "TEAMS_COMMANDS_DIR exists",
        dir_ok,
        config.TEAMS_COMMANDS_DIR or "not set",
    )

    # 6. Data directory writable
    data_ok = False
    try:
        os.makedirs(config.DATA_DIR, exist_ok=True)
        test_file = os.path.join(config.DATA_DIR, ".doctor-test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.unlink(test_file)
        data_ok = True
    except Exception:
        pass
    all_ok &= _check("Data directory writable", data_ok, config.DATA_DIR)

    # 7. Allowed senders
    senders = config.ALLOWED_SENDERS
    _check(
        "Allowed senders",
        bool(senders),
        ", ".join(senders) if senders else "⚠️  EMPTY — all senders allowed",
    )

    # 8. Copilot allow-all mode
    _check(
        "Copilot safe mode",
        not config.COPILOT_ALLOW_ALL,
        "safe (approval required)" if not config.COPILOT_ALLOW_ALL else "⚠️  AUTOPILOT — allow-all enabled",
    )

    # 9. Test webhook connectivity
    if has_webhook:
        from bridge.teams_sender import send_text
        result = send_text("🔍 Doctor check — if you see this, the webhook works!")
        all_ok &= _check("Webhook connectivity", result["success"], result.get("error", ""))

    # Summary
    print()
    if all_ok:
        print("✅ All checks passed! Run `copilot-teams-bridge` to start.\n")
    else:
        print("❌ Some checks failed. Fix the issues above and run again.\n")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

import base64
import re
import os
import requests

WORKFLOW_FILE = ".github/workflows/garimpar.yml"


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _base() -> str:
    owner = os.environ["GITHUB_OWNER"]
    repo = os.environ["GITHUB_REPO"]
    return f"https://api.github.com/repos/{owner}/{repo}"


def _get_workflow_id() -> int:
    resp = requests.get(f"{_base()}/actions/workflows", headers=_headers(), timeout=10)
    resp.raise_for_status()
    for wf in resp.json().get("workflows", []):
        if "garimpar" in wf["path"]:
            return wf["id"]
    raise ValueError("Workflow 'garimpar' não encontrado no repositório.")


def get_status() -> dict:
    wf_id = _get_workflow_id()
    resp = requests.get(f"{_base()}/actions/workflows/{wf_id}", headers=_headers(), timeout=10)
    resp.raise_for_status()
    data = resp.json()

    # lê o cron atual do arquivo
    cron = _read_cron()
    brt_hour, brt_min = _cron_to_brt(cron)

    return {
        "state": data["state"],          # "active" | "disabled_manually"
        "cron": cron,
        "horario_brt": f"{brt_hour:02d}:{brt_min:02d}",
    }


def enable() -> None:
    wf_id = _get_workflow_id()
    resp = requests.put(f"{_base()}/actions/workflows/{wf_id}/enable", headers=_headers(), timeout=10)
    resp.raise_for_status()


def disable() -> None:
    wf_id = _get_workflow_id()
    resp = requests.put(f"{_base()}/actions/workflows/{wf_id}/disable", headers=_headers(), timeout=10)
    resp.raise_for_status()


def trigger() -> None:
    wf_id = _get_workflow_id()
    branch = os.environ.get("GITHUB_BRANCH", "main")
    resp = requests.post(
        f"{_base()}/actions/workflows/{wf_id}/dispatches",
        headers=_headers(),
        json={"ref": branch},
        timeout=10,
    )
    resp.raise_for_status()


def set_schedule(hour: int, minute: int = 0) -> None:
    # converte BRT → UTC (BRT = UTC-3)
    utc_hour = (hour + 3) % 24
    new_cron = f"{minute} {utc_hour} * * *"
    _update_cron(new_cron)


def _read_cron() -> str:
    resp = requests.get(f"{_base()}/contents/{WORKFLOW_FILE}", headers=_headers(), timeout=10)
    resp.raise_for_status()
    content = base64.b64decode(resp.json()["content"]).decode("utf-8")
    m = re.search(r'cron:\s*"([^"]+)"', content)
    return m.group(1) if m else "?"


def _update_cron(new_cron: str) -> None:
    resp = requests.get(f"{_base()}/contents/{WORKFLOW_FILE}", headers=_headers(), timeout=10)
    resp.raise_for_status()
    file_data = resp.json()
    content = base64.b64decode(file_data["content"]).decode("utf-8")

    updated = re.sub(r'(cron:\s*")[^"]+(")', rf'\g<1>{new_cron}\g<2>', content)
    encoded = base64.b64encode(updated.encode("utf-8")).decode("utf-8")

    requests.put(
        f"{_base()}/contents/{WORKFLOW_FILE}",
        headers=_headers(),
        json={
            "message": f"chore: atualizar cron para '{new_cron}' via bot",
            "content": encoded,
            "sha": file_data["sha"],
            "branch": os.environ.get("GITHUB_BRANCH", "main"),
        },
        timeout=10,
    ).raise_for_status()


def _cron_to_brt(cron: str) -> tuple[int, int]:
    parts = cron.split()
    if len(parts) < 2:
        return 0, 0
    try:
        utc_min = int(parts[0])
        utc_hour = int(parts[1])
        brt_hour = (utc_hour - 3) % 24
        return brt_hour, utc_min
    except ValueError:
        return 0, 0

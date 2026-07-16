from __future__ import annotations

import hashlib
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_API_BASE = "https://labs.hackthebox.com/api/"
DEFAULT_USER_AGENT = "htb-mcp/0.1.0"
ZIP_PASSWORD = b"hackthebox"


class HtbApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class HtbApiConfig:
    token: str
    api_base_url: str = DEFAULT_API_BASE
    user_agent: str = DEFAULT_USER_AGENT
    verify_ssl: bool = True


class _StripAuthOnCrossHostRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is None:
            return None

        source = urllib.parse.urlsplit(req.full_url)
        target = urllib.parse.urlsplit(newurl)
        if source.netloc != target.netloc:
            redirected.remove_header("Authorization")
        return redirected


def _url(config: HtbApiConfig, endpoint: str, api_version: str = "v4") -> str:
    base = config.api_base_url.rstrip("/") + "/"
    return urllib.parse.urljoin(base, f"{api_version}/{endpoint.lstrip('/')}")


def _headers(config: HtbApiConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.token}",
        "User-Agent": config.user_agent,
        "Accept": "application/json",
    }


def _ssl_context(config: HtbApiConfig) -> ssl.SSLContext | None:
    if config.verify_ssl:
        return None
    return ssl._create_unverified_context()


def _decode_error(error: urllib.error.HTTPError) -> str:
    body = error.read()
    if not body:
        return str(error)
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return body.decode("utf-8", errors="replace")
    if isinstance(data, dict):
        return str(data.get("message") or data)
    return str(data)


def _http_error_message(
    error: urllib.error.HTTPError, method: str, url: str
) -> str:
    detail = _decode_error(error)
    return f"{method} {url} failed with HTTP {error.code}: {detail}"


def request_json(
    config: HtbApiConfig,
    method: str,
    endpoint: str,
    payload: dict[str, Any] | None = None,
    *,
    api_version: str = "v4",
) -> dict[str, Any]:
    body = None
    headers = _headers(config)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        _url(config, endpoint, api_version=api_version),
        data=body,
        headers=headers,
        method=method,
    )

    while True:
        try:
            with urllib.request.urlopen(
                request, context=_ssl_context(config), timeout=30
            ) as response:
                data = response.read()
            return json.loads(data.decode("utf-8")) if data else {}
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                time.sleep(1)
                continue
            raise HtbApiError(
                _http_error_message(exc, method, request.full_url)
            ) from exc
        except urllib.error.URLError as exc:
            raise HtbApiError(f"{method} {request.full_url} failed: {exc.reason}") from exc


def request_bytes(
    config: HtbApiConfig, endpoint: str, *, api_version: str = "v4"
) -> bytes:
    request = urllib.request.Request(
        _url(config, endpoint, api_version=api_version),
        headers=_headers(config),
        method="GET",
    )
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=_ssl_context(config)),
        _StripAuthOnCrossHostRedirect(),
    )
    while True:
        try:
            with opener.open(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                time.sleep(1)
                continue
            raise HtbApiError(
                _http_error_message(exc, "GET", request.full_url)
            ) from exc
        except urllib.error.URLError as exc:
            raise HtbApiError(f"GET {request.full_url} failed: {exc.reason}") from exc


def _safe_extract_zip(
    archive: zipfile.ZipFile, destination: Path, password: bytes | None = None
) -> None:
    destination = destination.resolve()
    for member in archive.infolist():
        member_path = Path(member.filename)
        if member_path.is_absolute():
            raise HtbApiError(
                f"Refusing to extract absolute archive path: {member.filename}"
            )
        target_path = (destination / member.filename).resolve()
        try:
            target_path.relative_to(destination)
        except ValueError as exc:
            raise HtbApiError(
                f"Refusing to extract archive path outside destination: {member.filename}"
            ) from exc
    archive.extractall(destination, pwd=password)


def _extract_list_payload(data: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("info", "data", "machines", "challenges"):
        items = data.get(key)
        if isinstance(items, list):
            return [item for item in items if isinstance(item, dict)]
    raise HtbApiError(
        f"HTB API response did not contain a list payload: keys={sorted(data.keys())}"
    )


def _with_query(endpoint: str, **params: Any) -> str:
    query = {
        key: value
        for key, value in params.items()
        if value is not None and value != ""
    }
    if not query:
        return endpoint
    return f"{endpoint}?{urllib.parse.urlencode(query)}"


def list_machines(config: HtbApiConfig) -> list[dict[str, Any]]:
    last_error: HtbApiError | None = None
    candidates = [
        ("machines?per_page=100", None, "GET", "v5"),
        ("machine/paginated?per_page=100", None, "GET", "v4"),
        ("machine/list", None, "GET", "v4"),
    ]
    for endpoint, payload, method, version in candidates:
        try:
            data = request_json(config, method, endpoint, payload, api_version=version)
            return _extract_list_payload(data)
        except HtbApiError as exc:
            last_error = exc
    raise last_error or HtbApiError("Unable to list machines.")


def get_machine(config: HtbApiConfig, machine_id_or_name: int | str) -> dict[str, Any]:
    if isinstance(machine_id_or_name, int) or str(machine_id_or_name).isdigit():
        machine_id = int(machine_id_or_name)
        for machine in list_machines(config):
            if int(machine.get("id", -1)) == machine_id:
                return machine
        raise HtbApiError(f"No machine with id {machine_id} was found.")

    data = request_json(
        config,
        "GET",
        f"machine/profile/{urllib.parse.quote(str(machine_id_or_name), safe='')}",
    )
    info = data.get("info")
    if not isinstance(info, dict):
        raise HtbApiError(f'No machine named "{machine_id_or_name}" was found.')
    return info


def get_active_machine(config: HtbApiConfig) -> dict[str, Any] | None:
    data = request_json(config, "GET", "machine/active", api_version="v4")
    info = data.get("info")
    return info if isinstance(info, dict) else None


def start_machine(config: HtbApiConfig, machine_id: int) -> dict[str, Any]:
    request_json(
        config, "POST", "vm/spawn", {"machine_id": machine_id}, api_version="v4"
    )
    for _ in range(120):
        machine = get_active_machine(config)
        if (
            machine
            and int(machine.get("id", -1)) == machine_id
            and machine.get("ip")
            and not machine.get("isSpawning")
        ):
            return machine
        time.sleep(1)
    raise HtbApiError("Timed out waiting for the machine to start.")


def submit_machine_flag(
    config: HtbApiConfig, flag: str, machine_id: int | None = None
) -> dict[str, Any]:
    target_id = machine_id
    if target_id is None:
        active = get_active_machine(config)
        if not active or active.get("id") is None:
            raise HtbApiError(
                "No active machine found. Start a machine first or provide its id."
            )
        target_id = int(active["id"])
    return request_json(
        config, "POST", "machine/own", {"id": target_id, "flag": flag}, api_version="v5"
    )


def list_challenges(config: HtbApiConfig) -> list[dict[str, Any]]:
    last_error: HtbApiError | None = None
    candidates = [
        ("challenges?per_page=100", None, "GET", "v4"),
        ("challenge/list", None, "GET", "v4"),
        ("challenge/paginated", {"per_page": 100}, "POST", "v4"),
    ]
    for endpoint, payload, method, version in candidates:
        try:
            data = request_json(config, method, endpoint, payload, api_version=version)
            return _extract_list_payload(data)
        except HtbApiError as exc:
            last_error = exc
    raise last_error or HtbApiError("Unable to list challenges.")


def get_challenge(
    config: HtbApiConfig, challenge_id_or_name: int | str
) -> dict[str, Any]:
    value = urllib.parse.quote(str(challenge_id_or_name), safe="")
    data = request_json(config, "GET", f"challenge/info/{value}", api_version="v4")
    challenge = data.get("challenge")
    if not isinstance(challenge, dict):
        raise HtbApiError("HTB API response did not contain a challenge object.")
    return challenge


def start_challenge_instance(config: HtbApiConfig, challenge_id: int) -> dict[str, Any]:
    request_json(
        config,
        "POST",
        "container/start",
        {"containerable_id": challenge_id},
        api_version="v4",
    )
    for _ in range(120):
        challenge = get_challenge(config, challenge_id)
        if challenge.get("docker_ip"):
            return challenge
        time.sleep(1)
    raise HtbApiError("Timed out waiting for the challenge instance to start.")


def download_challenge_zip(
    config: HtbApiConfig,
    challenge: dict[str, Any],
    destination: Path,
    *,
    unzip: bool = True,
    clear: bool = True,
) -> Path:
    challenge_id = int(challenge["id"])
    name = str(challenge.get("name") or challenge_id).strip().replace(" ", "_")
    destination.mkdir(parents=True, exist_ok=True)
    zip_path = destination / f"{name}.zip"

    data = request_bytes(config, f"challenge/download/{challenge_id}", api_version="v4")
    zip_path.write_bytes(data)

    expected_sha = str(challenge.get("sha256") or "").strip()
    if expected_sha:
        actual_sha = hashlib.sha256(data).hexdigest()
        if actual_sha != expected_sha:
            raise HtbApiError(
                f"Download hash mismatch: expected {expected_sha}, got {actual_sha}."
            )

    if unzip:
        with zipfile.ZipFile(zip_path) as archive:
            _safe_extract_zip(archive, destination, password=ZIP_PASSWORD)
        if clear:
            zip_path.unlink()

    return zip_path


def prepare_challenge(
    config: HtbApiConfig,
    challenge_id_or_name: int | str,
    destination: Path,
    *,
    start_instance: bool = True,
) -> dict[str, Any]:
    challenge = get_challenge(config, challenge_id_or_name)
    has_download = bool(challenge.get("download"))
    has_docker = bool(challenge.get("docker"))

    result: dict[str, Any] = {
        "challenge": challenge,
        "downloaded_to": None,
        "instance": None,
    }

    if has_download:
        download_challenge_zip(config, challenge, destination, unzip=True, clear=True)
        result["downloaded_to"] = str(destination.resolve())

    if start_instance and has_docker:
        started = start_challenge_instance(config, int(challenge["id"]))
        ports = started.get("docker_ports") or []
        host = started.get("docker_ip")
        result["instance"] = {
            "host": host,
            "ports": ports,
            "target": f"{host}:{ports[0]}" if host and ports else host,
        }

    if not has_download and not (start_instance and has_docker):
        raise HtbApiError(
            f'Challenge "{challenge.get("name", challenge_id_or_name)}" has no downloadable files or startable instance.'
        )

    return result


def submit_challenge_flag(
    config: HtbApiConfig, challenge_id: int, flag: str, difficulty: int = 1
) -> dict[str, Any]:
    return request_json(
        config,
        "POST",
        "challenge/own",
        {"flag": flag, "challenge_id": challenge_id, "difficulty": difficulty * 10},
        api_version="v4",
    )


def list_sherlocks(
    config: HtbApiConfig,
    *,
    keyword: str | None = None,
    per_page: int = 100,
    page: int = 1,
) -> dict[str, Any]:
    endpoint = _with_query(
        "sherlocks",
        per_page=per_page,
        page=page,
        keyword=keyword.strip() if keyword else None,
    )
    return request_json(config, "GET", endpoint, api_version="v4")


def get_sherlocks(config: HtbApiConfig, *, keyword: str | None = None) -> list[dict[str, Any]]:
    data = list_sherlocks(config, keyword=keyword)
    return _extract_list_payload(data)


def get_sherlock(config: HtbApiConfig, sherlock_id_or_name: int | str) -> dict[str, Any]:
    if isinstance(sherlock_id_or_name, int) or str(sherlock_id_or_name).isdigit():
        sherlock_id = int(sherlock_id_or_name)
        for sherlock in get_sherlocks(config):
            if int(sherlock.get("id", -1)) == sherlock_id:
                return sherlock
        raise HtbApiError(f"No sherlock with id {sherlock_id} was found.")

    name = str(sherlock_id_or_name).strip()
    if not name:
        raise HtbApiError("Sherlock name cannot be empty.")

    for sherlock in get_sherlocks(config, keyword=name):
        if str(sherlock.get("name", "")).strip().casefold() == name.casefold():
            return sherlock
    raise HtbApiError(f'No sherlock named "{name}" was found.')


def get_sherlock_play(config: HtbApiConfig, sherlock_id_or_name: int | str) -> dict[str, Any]:
    sherlock = get_sherlock(config, sherlock_id_or_name)
    data = request_json(config, "GET", f"sherlocks/{int(sherlock['id'])}/play", api_version="v4")
    play = data.get("data")
    if not isinstance(play, dict):
        raise HtbApiError("HTB API response did not contain a sherlock play payload.")
    return play


def list_sherlock_tasks(
    config: HtbApiConfig, sherlock_id_or_name: int | str
) -> list[dict[str, Any]]:
    sherlock = get_sherlock(config, sherlock_id_or_name)
    data = request_json(config, "GET", f"sherlocks/{int(sherlock['id'])}/tasks", api_version="v4")
    return _extract_list_payload(data)


def submit_sherlock_task_flag(
    config: HtbApiConfig,
    sherlock_id_or_name: int | str,
    task_id: int,
    flag: str,
) -> dict[str, Any]:
    sherlock = get_sherlock(config, sherlock_id_or_name)
    return request_json(
        config,
        "POST",
        f"sherlocks/{int(sherlock['id'])}/tasks/{task_id}/flag",
        {"flag": flag},
        api_version="v4",
    )

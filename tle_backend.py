from __future__ import annotations

from typing import Any

import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

CELESTRAK_NAME_URL = "https://celestrak.org/NORAD/elements/gp.php"
CELESTRAK_ACTIVE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=active&FORMAT=tle"
SPACETRACK_LOGIN_URL = "https://www.space-track.org/ajaxauth/login"
SPACETRACK_QUERY_URLS = [
    "https://www.space-track.org/basicspacedata/query/class/tle_latest/OBJECT_NAME/{query}/ORDINAL/1/orderby/EPOCH%20desc/format/json",
    "https://www.space-track.org/basicspacedata/query/class/gp/OBJECT_NAME/{query}/orderby/EPOCH%20desc/limit/200/format/json",
    "https://www.space-track.org/basicspacedata/query/class/gp/OBJECT_NAME/~~{query}/orderby/EPOCH%20desc/limit/200/format/json",
]
SPACETRACK_NORAD_QUERY_URLS = [
    "https://www.space-track.org/basicspacedata/query/class/tle_latest/NORAD_CAT_ID/{norad}/ORDINAL/1/orderby/EPOCH%20desc/format/json",
    "https://www.space-track.org/basicspacedata/query/class/gp/NORAD_CAT_ID/{norad}/orderby/EPOCH%20desc/limit/200/format/json",
]


def parse_tle_text(tle_text: str) -> list[dict[str, Any]]:
    lines = [line.strip() for line in tle_text.splitlines() if line.strip()]
    entries: list[dict[str, Any]] = []

    i = 0
    while i < len(lines):
        # 3-line TLE: NAME, line1, line2
        if i + 2 < len(lines):
            name = lines[i]
            line1 = lines[i + 1]
            line2 = lines[i + 2]

            if line1.startswith("1 ") and line2.startswith("2 "):
                entries.append(
                    {
                        "name": name,
                        "line1": line1,
                        "line2": line2,
                        "noradId": line1[2:7].strip(),
                    }
                )
                i += 3
                continue

        # 2-line TLE: line1, line2 (common from some APIs)
        if i + 1 < len(lines) and lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
            line1 = lines[i]
            line2 = lines[i + 1]
            entries.append(
                {
                    "name": f"NORAD {line1[2:7].strip()}",
                    "line1": line1,
                    "line2": line2,
                    "noradId": line1[2:7].strip(),
                }
            )
            i += 2
            continue

        i += 1

    return entries


def dedupe(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, Any]] = []

    for item in entries:
        key = (str(item.get("noradId", "")), str(item.get("name", "")))
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


def fetch_celestrak_by_name(query: str) -> list[dict[str, Any]]:
    response = requests.get(
        CELESTRAK_NAME_URL,
        params={"NAME": query, "FORMAT": "tle"},
        timeout=20,
    )
    response.raise_for_status()
    parsed = parse_tle_text(response.text)
    for item in parsed:
        item["source"] = "CelesTrak"
    return dedupe(parsed)


def fetch_celestrak_by_norad(norad_id: str) -> list[dict[str, Any]]:
    response = requests.get(
        CELESTRAK_NAME_URL,
        params={"CATNR": norad_id, "FORMAT": "tle"},
        timeout=20,
    )
    response.raise_for_status()
    parsed = parse_tle_text(response.text)
    for item in parsed:
        item["source"] = "CelesTrak"
    return dedupe(parsed)


def fetch_celestrak_active() -> list[dict[str, Any]]:
    response = requests.get(CELESTRAK_ACTIVE_URL, timeout=25)
    response.raise_for_status()
    parsed = parse_tle_text(response.text)
    for item in parsed:
        item["source"] = "CelesTrak"
    return dedupe(parsed)


def parse_spacetrack_json(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        return []

    parsed: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue

        line1 = str(row.get("TLE_LINE1") or "").strip()
        line2 = str(row.get("TLE_LINE2") or "").strip()
        if not line1.startswith("1 ") or not line2.startswith("2 "):
            continue

        norad = str(row.get("NORAD_CAT_ID") or "").strip() or line1[2:7].strip()
        name = str(row.get("OBJECT_NAME") or "").strip() or f"NORAD {norad}"

        parsed.append(
            {
                "name": name,
                "line1": line1,
                "line2": line2,
                "noradId": norad,
                "source": "Space-Track",
            }
        )

    return dedupe(parsed)


def ensure_spacetrack_login(session: requests.Session, username: str, password: str) -> None:
    login = session.post(
        SPACETRACK_LOGIN_URL,
        data={"identity": username, "password": password},
        timeout=20,
    )

    if login.status_code >= 400:
        raise RuntimeError(f"Space-Track login failed (HTTP {login.status_code})")

    # Space-Track can return HTTP 200 even when auth fails.
    cookie_keys = {k.lower() for k in session.cookies.keys()}
    if "chocolatechip" not in cookie_keys:
        preview = (login.text or "").strip().replace("\n", " ")[:140]
        if preview:
            raise RuntimeError(f"Space-Track login rejected: {preview}")
        raise RuntimeError("Space-Track login rejected. Verify username/password and account access.")


def fetch_spacetrack_by_name(query: str, username: str, password: str) -> list[dict[str, Any]]:
    if not username or not password:
        raise ValueError("Space-Track credentials are required")

    session = requests.Session()
    ensure_spacetrack_login(session, username, password)

    encoded_query = requests.utils.quote(query.strip(), safe="")

    last_error: Exception | None = None
    for url_template in SPACETRACK_QUERY_URLS:
        url = url_template.format(query=encoded_query)
        try:
            resp = session.get(url, timeout=25)
            if resp.status_code >= 400:
                raise RuntimeError(f"Space-Track query failed (HTTP {resp.status_code})")

            parsed = parse_spacetrack_json(resp.json())
            if parsed:
                return dedupe(parsed)
            last_error = RuntimeError("No Space-Track TLE matches for that name")
        except Exception as exc:
            last_error = exc

    if last_error is None:
        raise RuntimeError("Unable to search Space-Track")
    raise RuntimeError(str(last_error))


def fetch_spacetrack_by_norad(norad_id: str, username: str, password: str) -> list[dict[str, Any]]:
    if not username or not password:
        raise ValueError("Space-Track credentials are required")

    session = requests.Session()
    ensure_spacetrack_login(session, username, password)

    last_error: Exception | None = None
    for url_template in SPACETRACK_NORAD_QUERY_URLS:
        url = url_template.format(norad=requests.utils.quote(norad_id.strip(), safe=""))
        try:
            resp = session.get(url, timeout=25)
            if resp.status_code >= 400:
                raise RuntimeError(f"Space-Track query failed (HTTP {resp.status_code})")

            parsed = parse_spacetrack_json(resp.json())
            if parsed:
                return dedupe(parsed)
            last_error = RuntimeError("No Space-Track TLE matches for that NORAD ID")
        except Exception as exc:
            last_error = exc

    if last_error is None:
        raise RuntimeError("Unable to search Space-Track")
    raise RuntimeError(str(last_error))


@app.get("/")
def root() -> Any:
    return send_from_directory(".", "polarization_cal_v5.html")


@app.get("/api/health")
def health() -> Any:
    return jsonify({"ok": True})


@app.post("/api/tle/search")
def api_tle_search() -> Any:
    payload = request.get_json(silent=True) or {}
    source = str(payload.get("source", "celestrak")).strip().lower()
    query = str(payload.get("query", "")).strip()
    mode = str(payload.get("mode", "name")).strip().lower()

    if not query:
        return jsonify({"error": "Missing query"}), 400

    try:
        if source == "celestrak":
            results = fetch_celestrak_by_norad(query) if mode == "norad" else fetch_celestrak_by_name(query)
        elif source == "celestrak-active":
            active = fetch_celestrak_active()
            results = [item for item in active if query.lower() in item.get("name", "").lower()]
        elif source == "spacetrack":
            username = str(payload.get("username", "")).strip()
            password = str(payload.get("password", ""))
            results = fetch_spacetrack_by_norad(query, username, password) if mode == "norad" else fetch_spacetrack_by_name(query, username, password)
        else:
            return jsonify({"error": "Invalid source. Use celestrak or spacetrack."}), 400

        return jsonify({"results": results})
    except requests.HTTPError as exc:
        code = exc.response.status_code if exc.response is not None else 502
        return jsonify({"error": f"Upstream HTTP error {code}"}), 502
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": str(exc)}), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)

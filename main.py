import os
import sys
import argparse
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv

# Load environment variables from .env (if present)
load_dotenv()

# ---------------------------- Config ---------------------------- #
PIXELA_ENDPOINT = "https://pixe.la/v1/users"
USERNAME = os.getenv("USERNAME")
TOKEN = os.getenv("TOKEN")
GRAPH_ID = os.getenv("GRAPH_ID", "graph1")

# Validate minimal configuration for operations that require auth
HEADERS = {"X-USER-TOKEN": TOKEN} if TOKEN else {}
HTTP_TIMEOUT = 15
USER_AGENT = {"User-Agent": "PixelaHabitTracker/1.0 (+github.com/DEX-01-CODER)"}


def resolve_graph_id(override: Optional[str] = None) -> str:
    """Return the graph id to use: CLI override if given, else env GRAPH_ID."""
    gid = (override or GRAPH_ID).strip() if (override or GRAPH_ID) else None
    if not gid:
        raise SystemExit("GRAPH_ID is required (set in .env or pass --graph <id>)")
    return gid


def require_env(*keys: str) -> None:
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        raise SystemExit(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Create a .env file with at least: USERNAME, TOKEN, GRAPH_ID"
        )


# ---------------------------- API Helpers ---------------------------- #

def api_call(method: str, url: str, **kwargs):
    """Call Pixela API with sane defaults and error messaging."""
    kwargs.setdefault("timeout", HTTP_TIMEOUT)
    headers = kwargs.pop("headers", {})
    headers = {**USER_AGENT, **headers}
    try:
        resp = requests.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp
    except requests.HTTPError as e:
        # Try to provide Pixela's message if present
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise SystemExit(f"HTTP error {resp.status_code}: {detail}\n{e}")
    except requests.RequestException as e:
        raise SystemExit(f"Network error: {e}")


# ---------------------------- Operations ---------------------------- #

def create_user() -> None:
    require_env("USERNAME", "TOKEN")
    payload = {
        "token": TOKEN,
        "username": USERNAME,
        "agreeTermsOfService": "yes",
        "notMinor": "yes",
    }
    resp = api_call("POST", PIXELA_ENDPOINT, json=payload)
    print(resp.text)


def create_graph(name: str = "Habit Tracker", unit: str = "unit", gtype: str = "int", color: str = "sora", graph_id: Optional[str] = None) -> None:
    require_env("USERNAME", "TOKEN", "GRAPH_ID")
    gid = resolve_graph_id(graph_id)
    url = f"{PIXELA_ENDPOINT}/{USERNAME}/graphs"
    payload = {
        "id": gid,
        "name": name,
        "unit": unit,
        "type": gtype,  # "int" or "float"
        "color": color,  # one of: shibafu, momiji, sora, ichou, ajisai, kuro
    }
    resp = api_call("POST", url, json=payload, headers=HEADERS)
    print(resp.text)
    print(f"Graph URL: https://pixe.la/v1/users/{USERNAME}/graphs/{gid}.html")


def add_pixel(quantity: str, date_str: Optional[str] = None, graph_id: Optional[str] = None) -> None:
    require_env("USERNAME", "TOKEN", "GRAPH_ID")
    gid = resolve_graph_id(graph_id)
    # Pixela expects YYYYMMDD
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%Y%m%d")
        except ValueError:
            raise SystemExit("date must be in YYYYMMDD format (e.g., 20251021)")
    else:
        dt = datetime.now()
    payload = {"date": dt.strftime("%Y%m%d"), "quantity": str(quantity)}
    url = f"{PIXELA_ENDPOINT}/{USERNAME}/graphs/{gid}"
    resp = api_call("POST", url, json=payload, headers=HEADERS)
    print(resp.text)


def update_pixel(quantity: str, date_str: str, graph_id: Optional[str] = None) -> None:
    require_env("USERNAME", "TOKEN", "GRAPH_ID")
    gid = resolve_graph_id(graph_id)
    try:
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        raise SystemExit("date must be in YYYYMMDD format (e.g., 20251021)")
    payload = {"quantity": str(quantity)}
    url = f"{PIXELA_ENDPOINT}/{USERNAME}/graphs/{gid}/{date_str}"
    resp = api_call("PUT", url, json=payload, headers=HEADERS)
    print(resp.text)


def delete_pixel(date_str: str, graph_id: Optional[str] = None) -> None:
    require_env("USERNAME", "TOKEN", "GRAPH_ID")
    gid = resolve_graph_id(graph_id)
    try:
        datetime.strptime(date_str, "%Y%m%d")
    except ValueError:
        raise SystemExit("date must be in YYYYMMDD format (e.g., 20251021)")
    url = f"{PIXELA_ENDPOINT}/{USERNAME}/graphs/{gid}/{date_str}"
    resp = api_call("DELETE", url, headers=HEADERS)
    print(resp.text)


# ---------------------------- CLI ---------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Pixela Habit Tracker — create user/graph and add/update/delete daily pixels. Use --graph to override GRAPH_ID from .env.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("create-user", help="Create Pixela user (uses USERNAME, TOKEN from .env)")

    pg = sub.add_parser("create-graph", help="Create a graph")
    pg.add_argument("--name", default="Habit Tracker")
    pg.add_argument("--unit", default="commit", help="e.g., commit, km, pages")
    pg.add_argument("--type", dest="gtype", default="int", choices=["int", "float"])
    pg.add_argument("--color", default="sora", choices=["shibafu", "momiji", "sora", "ichou", "ajisai", "kuro"])
    pg.add_argument("--graph", dest="graph_id", help="graph id to create/use (defaults to GRAPH_ID from .env)")

    pa = sub.add_parser("add", help="Add a pixel for a date (default: today)")
    pa.add_argument("quantity", help="quantity value (string or number)")
    pa.add_argument("--date", dest="date_str", help="YYYYMMDD (default: today)")
    pa.add_argument("--graph", dest="graph_id", help="graph id to use (defaults to GRAPH_ID from .env)")

    pu = sub.add_parser("update", help="Update a pixel's quantity for a date")
    pu.add_argument("date", help="YYYYMMDD")
    pu.add_argument("quantity")
    pu.add_argument("--graph", dest="graph_id", help="graph id to use (defaults to GRAPH_ID from .env)")

    pd = sub.add_parser("delete", help="Delete a pixel for a date")
    pd.add_argument("date", help="YYYYMMDD")
    pd.add_argument("--graph", dest="graph_id", help="graph id to use (defaults to GRAPH_ID from .env)")

    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.cmd == "create-user":
        create_user()
    elif args.cmd == "create-graph":
        create_graph(name=args.name, unit=args.unit, gtype=args.gtype, color=args.color, graph_id=args.graph_id)
    elif args.cmd == "add":
        add_pixel(quantity=args.quantity, date_str=args.date_str, graph_id=args.graph_id)
    elif args.cmd == "update":
        update_pixel(quantity=args.quantity, date_str=args.date, graph_id=args.graph_id)
    elif args.cmd == "delete":
        delete_pixel(date_str=args.date, graph_id=args.graph_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

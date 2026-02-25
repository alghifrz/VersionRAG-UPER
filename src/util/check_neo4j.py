import os
from pathlib import Path

from dotenv import load_dotenv
from neo4j import GraphDatabase


def _load_env() -> None:
    """
    Load env from src/.env if present; otherwise rely on process environment.
    We intentionally do not print secrets.
    """
    src_dir = Path(__file__).resolve().parents[1]
    env_path = src_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        # Fallback: try default load behavior (cwd)
        load_dotenv()


def _masked(value: str | None) -> str:
    if not value:
        return "(missing)"
    return value[:4] + "..." + value[-4:] if len(value) >= 10 else "***"


def check(uri_key: str, user_key: str, pass_key: str) -> None:
    uri = os.getenv(uri_key)
    user = os.getenv(user_key)
    pwd = os.getenv(pass_key)

    missing = [k for k, v in [(uri_key, uri), (user_key, user), (pass_key, pwd)] if not v]
    if missing:
        raise SystemExit(f"Missing env var(s): {', '.join(missing)}")

    # Print only non-sensitive info (and masked password marker)
    print(f"Using {uri_key}={uri}")
    print(f"Using {user_key}={user}")
    print(f"Using {pass_key}={_masked(pwd)}")

    driver = GraphDatabase.driver(uri, auth=(user, pwd))
    driver.verify_connectivity()
    driver.close()


if __name__ == "__main__":
    _load_env()

    print("Checking Neo4j LOCAL-style env (NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD)...")
    check("NEO4J_URI", "NEO4J_USER", "NEO4J_PASSWORD")

    print("\nChecking KG (Aura-named) env (NEO4J_URI_AURA/NEO4J_USERNAME_AURA/NEO4J_PASSWORD_AURA)...")
    check("NEO4J_URI_AURA", "NEO4J_USERNAME_AURA", "NEO4J_PASSWORD_AURA")

    print("\n✅ Neo4j connectivity OK")



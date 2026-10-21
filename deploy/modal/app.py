"""The Qapital API on Modal (https://modal.com): serverless, so it costs nothing while nobody uses it.

One container at most, because running jobs and rate limits live in memory; it starts on the first request (the
website shows saved runs meanwhile), downloads the newest price snapshot, and stops after 10 quiet minutes. Settings
come from the Modal secret "qapital-api": DATABASE_URL and QAPITAL_CORS_ORIGINS.
Deploy from the repo root (the deploy workflow does this after CI passes on main):
  uv run --extra api --with modal==1.6.0 modal deploy deploy/modal/app.py"""

import os
from pathlib import Path

import modal

# The repo folder, for building the image; inside the container this file sits at /root/app.py with no repo around it.
ROOT = Path(__file__).resolve().parents[2] if modal.is_local() else Path("/")
DATA = "/root/data"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .uv_sync(str(ROOT), extras=["api"], uv_version="0.13.0")
    .env(
        {
            "QAPITAL_DATA": DATA,
            "QAPITAL_SNAPSHOT_REPO": "sameeksha15/Qapital",
            "QAPITAL_TRUST_PROXY": "1",
            "QAPITAL_WORKERS": "2",
        }
    )
    .add_local_dir(ROOT / "data" / "universes", f"{DATA}/universes")
    .add_local_dir(ROOT / "data" / "costs", f"{DATA}/costs")
    .add_local_python_source("qapital")
)

app = modal.App("qapital-api")


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("qapital-api")],
    cpu=2.0,
    memory=2048,
    max_containers=1,
    scaledown_window=600,
    timeout=3600,
)
@modal.concurrent(max_inputs=50)
@modal.asgi_app(label="qapital-api")
def api():
    from qapital.api.main import Config, create_app
    from qapital.data.remote import sync_snapshot

    config = Config.from_env()
    if config.snapshot_repo:
        try:  # have prices before the first request; the app keeps checking for newer ones every few hours
            sync_snapshot(config.snapshot_repo, config.source.snapshots_dir)
        except Exception as error:
            print(f"Couldn't download the price snapshot yet: {error}")
    os.makedirs(config.source.snapshots_dir, exist_ok=True)
    return create_app(config)

from celery import Celery
import os
from igscraper.config import load_config

config_path = os.getenv("IGSCRAPER_CONFIG", "config.toml")
config = load_config(config_path)

app = Celery(
    "igscraper",
    broker=config.celery.broker_url,
    backend=config.celery.result_backend,
    include=["igscraper.mycelery.tasks"]
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
)

app.autodiscover_tasks(["igscraper.mycelery"])


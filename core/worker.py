"""Hooks that run inside the Celery worker process."""

from typing import Any

from celery.signals import worker_ready


@worker_ready.connect
def on_worker_ready(**_: Any) -> None:
    """Report GPU availability and flag jobs the previous run left unfinished."""
    from .services import worker_started
    from .utils import detect_gpu_in_subprocess

    # Never probe CUDA here: this is the prefork parent (see detect_gpu_in_subprocess).
    worker_started(gpu_available=detect_gpu_in_subprocess())

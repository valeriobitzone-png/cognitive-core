"""Explicit, fail-closed runtime settings."""
from dataclasses import dataclass, field
from pathlib import Path
import math
import re


@dataclass
class Settings:
    home: Path = field(default_factory=lambda: Path.home() / ".cognitive-core")
    namespace: str = "default"
    enable_web: bool = False
    enable_local_model: bool = False
    local_model_url: str = "http://127.0.0.1:8080/v1/chat/completions"
    local_model_name: str = "local-decision-model"
    external_paid_calls_allowed: bool = False  # hard block: no client implemented
    max_web_requests_per_day: int = 30
    max_web_requests_per_job: int = 8
    max_jobs_per_day: int = 20
    max_text_bytes: int = 350_000
    model_timeout_seconds: int = 12
    request_timeout_seconds: int = 12
    domain_allowlist: tuple[str, ...] = ()
    searxng_url: str = ""  # optional self-hosted / opted-in public instance
    llm_min_relevance: float = 0.40
    owner: str = "local"

    def __post_init__(self):
        self.home = Path(self.home)
        if not self.namespace or len(self.namespace) > 80:
            raise ValueError("invalid namespace")
        for value in (self.namespace, self.owner):
            if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_.:@/-]{1,128}', value):
                raise ValueError('invalid owner or namespace')
        if self.external_paid_calls_allowed:
            raise ValueError("External paid model calls are forbidden in v0.1")
        if self.max_web_requests_per_job < 0 or self.max_web_requests_per_day < 0:
            raise ValueError("invalid web budget")
        if self.max_jobs_per_day < 0 or self.max_text_bytes <= 0:
            raise ValueError("invalid budget")
        for name in ('max_web_requests_per_job', 'max_web_requests_per_day', 'max_jobs_per_day', 'max_text_bytes'):
            if type(getattr(self, name)) is not int:
                raise ValueError('budgets must be integers')
        for value in (self.request_timeout_seconds, self.model_timeout_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 60:
                raise ValueError('timeout must be finite and within 0..60 seconds')

    @property
    def db_path(self) -> Path:
        return self.home / "vault.sqlite3"

    @property
    def worldcore_path(self) -> Path:
        return self.home / 'worldcore.sqlite3'

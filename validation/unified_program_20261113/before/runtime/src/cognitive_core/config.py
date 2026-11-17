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
    local_model_gguf: str = ""
    local_model_binary: str = "llama-completion"
    local_decision_state: str = ""
    max_model_calls_per_day: int = 10
    max_model_tokens: int = 64
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
    execution_mode: str = "interactive"
    autonomous_web_opt_in: bool = False
    max_runtime_disk_bytes: int = 128_000_000
    max_import_bytes: int = 16_000_000
    max_import_files: int = 1000
    max_import_records: int = 10000
    max_cycle_seconds: float = 10
    max_cycle_sources: int = 5
    max_cycle_ticks_per_day: int = 100
    local_model_jinja: bool = False
    max_model_file_bytes: int = 1_000_000_000

    curiosity_policy: str = "information_only"
    max_curiosity_units_per_day: int = 24

    def __post_init__(self):
        self.home = Path(self.home)
        if self.curiosity_policy not in ("legacy","observe","information_only"):
            raise ValueError("invalid curiosity policy")
        if type(self.max_curiosity_units_per_day) is not int or not 0<=self.max_curiosity_units_per_day<=1000:
            raise ValueError("curiosity units must be 0..1000")
        if type(self.local_model_jinja) is not bool:
            raise ValueError("model template choice must be boolean")
        if type(self.max_model_file_bytes) is not int or not 1<=self.max_model_file_bytes<=4_000_000_000:
            raise ValueError("model file budget must be 1..4GB")
        if type(self.max_model_calls_per_day) is not int or not 0<=self.max_model_calls_per_day<=100:
            raise ValueError('model calls must be 0..100 per day')
        if type(self.max_model_tokens) is not int or not 32<=self.max_model_tokens<=128:
            raise ValueError('model output must be 32..128 tokens')
        for value in (self.local_model_gguf,self.local_model_binary,self.local_decision_state):
            if not isinstance(value,str) or '\x00' in value:
                raise ValueError('invalid local model path')
        if self.execution_mode not in ('interactive','autonomous'):
            raise ValueError('invalid execution authority')
        if type(self.autonomous_web_opt_in) is not bool:
            raise ValueError('autonomous web opt-in must be boolean')
        for name in ('max_runtime_disk_bytes','max_import_bytes','max_import_files',
                     'max_import_records','max_cycle_sources','max_cycle_ticks_per_day'):
            if type(getattr(self,name)) is not int or getattr(self,name)<1:
                raise ValueError('invalid '+name)
        if self.max_cycle_sources>20:
            raise ValueError('cycle source limit exceeds 20')
        if type(self.max_cycle_seconds) not in (int,float) or not math.isfinite(self.max_cycle_seconds) or not 0<self.max_cycle_seconds<=60:
            raise ValueError('invalid cycle time budget')
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

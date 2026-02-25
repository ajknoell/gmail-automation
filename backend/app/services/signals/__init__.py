# Import collectors to trigger registration
from app.services.signals.registry import get_collector, get_all_collectors, register_collector  # noqa
from app.services.signals.job_posting import JobPostingCollector  # noqa
from app.services.signals.news import NewsCollector  # noqa

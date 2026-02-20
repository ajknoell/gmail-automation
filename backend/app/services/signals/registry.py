"""
Signal collector registry — pluggable system for registering
and looking up signal collection plugins.
"""

# ─── Collector Registry ──────────────────────────────────────────────
_COLLECTORS = {}


def register_collector(source_type):
    """Decorator to register a signal collector by source type."""
    def decorator(cls):
        _COLLECTORS[source_type] = cls()
        return cls
    return decorator


def get_collector(source_type):
    """Look up a collector by source type."""
    return _COLLECTORS.get(source_type)


def get_all_collectors():
    """Return all registered collectors."""
    return dict(_COLLECTORS)

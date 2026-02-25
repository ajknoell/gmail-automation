"""
Base class for all signal collectors.
Each collector detects a specific type of intent signal.
"""


class SignalCollector:
    """Base class for signal collection plugins."""

    source_type = None  # Override in subclass

    def collect(self, contact, workspace_id, config=None):
        """
        Collect signals for a single contact.

        Args:
            contact: Contact model instance
            workspace_id: Workspace ID
            config: Optional dict of source-specific configuration

        Returns:
            List of Signal model instances (unsaved)
        """
        raise NotImplementedError

    def score_intent(self, signal_data):
        """
        Score the intent strength of a signal.

        Args:
            signal_data: Dict of signal-specific data

        Returns:
            Float 0.0-1.0
        """
        return 0.5

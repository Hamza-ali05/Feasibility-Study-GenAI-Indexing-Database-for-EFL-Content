"""Security evaluation package for the EFL IndexDB feasibility study.

Defensive OWASP-aligned testing of the local API only.
"""

from research.security_eval.security_auditor import SecurityAuditor

__all__ = ["SecurityAuditor"]

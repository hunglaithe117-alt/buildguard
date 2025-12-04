"""Compat wrapper for shared logging utilities."""

from buildguard_common.logger import OTelJSONFormatter, setup_logging

__all__ = ["OTelJSONFormatter", "setup_logging"]

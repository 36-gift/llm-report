"""
Custom exceptions for the LLM report tool.
"""


class LLMReportError(Exception):
    """Base exception for all LLM report tool errors."""

    pass


class ConfigurationError(LLMReportError):
    """Raised when there's an issue with configuration."""

    pass


class ScrapingError(LLMReportError):
    """Raised when there's an issue with web scraping."""

    pass


class APIError(LLMReportError):
    """Raised when there's an issue with external API calls."""

    pass


class ProcessingError(LLMReportError):
    """Raised when there's an issue with data processing."""

    pass


class ReportGenerationError(LLMReportError):
    """Raised when there's an issue with report generation."""

    pass


class ValidationError(LLMReportError):
    """Raised when data validation fails."""

    pass


class RetryExhaustedError(LLMReportError):
    """Raised when all retry attempts have been exhausted."""

    pass

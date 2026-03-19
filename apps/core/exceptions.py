"""
Custom DRF exception handler.
Stub — full implementation added in a later phase.
"""

from rest_framework.views import exception_handler


def custom_exception_handler(exc, context):
    """
    Custom exception handler that wraps DRF's default handler.
    Returns a standardised error response shape.
    """
    response = exception_handler(exc, context)
    return response

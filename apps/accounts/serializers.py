"""
Accounts serializers.
Stub — full implementation added in Phase 2 (auth module).
"""

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extends the default JWT serializer.
    Custom claims and validation logic will be added in Phase 2.
    """

    pass

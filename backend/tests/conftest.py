import os


# Tests use isolated, non-production values so application settings never need
# hard-coded credentials in source code.
os.environ.setdefault("JWT_SECRET", "test-only-jwt-secret-not-for-production")
os.environ.setdefault(
    "CREDENTIAL_ENCRYPTION_KEY",
    "test-only-credential-key-not-for-production",
)
os.environ.setdefault("DEMO_OPERATOR_PASSWORD", "test-only-operator-password")
os.environ.setdefault("DEMO_MERCHANT_PASSWORD", "test-only-merchant-password")

from __future__ import annotations

import os


os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
# 32+ bytes so PyJWT does not warn about insecure HMAC key length (RFC 7518 §3.2).
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes!!")

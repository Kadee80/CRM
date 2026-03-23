import hashlib
import hmac


def verify_webhook_signature(
  signing_secret: str,
  payload: bytes,
  timestamp: str,
  signature_header: str,
) -> bool:
  message = f"{timestamp}.{payload.decode('utf-8')}".encode("utf-8")
  expected = hmac.new(signing_secret.encode("utf-8"), message, hashlib.sha256).hexdigest()
  return hmac.compare_digest(expected, signature_header)


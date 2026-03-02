import time
import requests
import jwt
from jwt.algorithms import RSAAlgorithm

class CognitoJWTValidator:
    def __init__(self, region, user_pool_id, audience=None):
        self.region = region
        self.user_pool_id = user_pool_id
        self.issuer = f"https://cognito-idp.{region}.amazonaws.com/{user_pool_id}"
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self.audience = audience
        self._jwks_cache = None
        self._jwks_cache_expiry = 0

    def _download_jwks(self):
        resp = requests.get(self.jwks_url)
        resp.raise_for_status()
        return resp.json()["keys"]

    def _get_jwks(self):
        """Return cached JWKS unless older than 12 hours."""
        if time.time() > self._jwks_cache_expiry:
            self._jwks_cache = self._download_jwks()
            self._jwks_cache_expiry = time.time() + 43200  # 12 hours
        return self._jwks_cache

    def _get_public_key(self, kid):
        jwks = self._get_jwks()
        for key in jwks:
            if key["kid"] == kid:
                return RSAAlgorithm.from_jwk(key)
        raise Exception(f"No matching JWK found for kid: {kid}")

    def verify(self, token):
        try:
            header = jwt.get_unverified_header(token)
        except jwt.JWTError as e:
            raise Exception(f"Invalid JWT format: {e}")

        if "kid" not in header:
            raise Exception("Missing 'kid' in JWT header")

        public_key = self._get_public_key(header["kid"])

        options = {
            "verify_aud": self.audience is not None,
            "verify_signature": True
        }

        try:
            payload = jwt.decode(
                token,
                public_key,
                algorithms=["RS256"],
                issuer=self.issuer,
                audience=self.audience,
                options=options
            )
            return payload

        except jwt.ExpiredSignatureError:
            raise Exception("Token has expired")
        except jwt.InvalidIssuerError:
            raise Exception("Invalid token issuer")
        except jwt.InvalidAudienceError:
            raise Exception("Invalid audience")
        except jwt.InvalidTokenError as e:
            raise Exception(f"Token verification failed: {e}")

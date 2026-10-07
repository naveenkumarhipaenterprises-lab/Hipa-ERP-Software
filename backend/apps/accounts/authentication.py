from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed

# Claim holding User.token_version when the token was issued (tokens from before this existed count as 0)
TOKEN_VERSION_CLAIM = "ver"


class VersionedJWTAuthentication(JWTAuthentication):
    """
    SimpleJWT, plus: a token stops working once the user logs out or changes / resets the password.
    The user row is loaded for every request anyway, so this costs no extra query.
    """

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if validated_token.get(TOKEN_VERSION_CLAIM, 0) != user.token_version:
            raise AuthenticationFailed("Your session has ended. Please sign in again.", code="token_revoked")
        return user

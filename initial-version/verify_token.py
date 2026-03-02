from cognito_validator import CognitoJWTValidator
# import jwt
# from jwt.algorithms import RSAAlgorithm
# import requests

token = "eyJraWQiOiJQSDU0QkhkQTNUVkhuXC9rUThwMCtOSGFDTlFjV3FEb3Z5WVZcL1VFVnZDK009IiwiYWxnIjoiUlMyNTYifQ.eyJzdWIiOiIycXI3cjBocmxycTMxYXVmNGdvY2U4YW43bCIsImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC5jYS1jZW50cmFsLTEuYW1hem9uYXdzLmNvbVwvY2EtY2VudHJhbC0xX3A1WGY4UGs1WiIsInVzZXI6YWNjb3VudCI6IjEyMzQ1Njc4OTAiLCJ2ZXJzaW9uIjoyLCJjbGllbnRfaWQiOiIycXI3cjBocmxycTMxYXVmNGdvY2U4YW43bCIsInVzZXI6Z3JvdXBzIjpbIkEiLCJCIiwiQ2hhcmxpZSJdLCJ0b2tlbl91c2UiOiJhY2Nlc3MiLCJ1c2VyOnJvbGUiOiJzaGlwcGVyIiwic2NvcGUiOiJodHRwczpcL1wvYXBpLmF0cy5oZWFsdGhjYXJlXC9nZW5lcmF0ZV90b2tlbiIsImF1dGhfdGltZSI6MTc2NDI2MDc0NSwiZXhwIjoxNzY0MzQ3MTQ1LCJpYXQiOjE3NjQyNjA3NDUsImp0aSI6IjU1N2NiYWM0LWFlOTAtNGQ0MS05MDk5LTQ0ZmVhN2RlZjhiZSJ9.RZGymJAOUl3ybbMbyWxydOkBO_0FzUgxKz3JRWELakF64zIvKvvysQRZvqysMrf5Ppkt5wBhIbYHUXhKrUH5qG3OrUz6CxspnY8p7JU96OlI0wK-o9bNXeX2yM6Kv5cJOdE3IXQjWnSpZKPjfsnprKHfT-TWe-gevdt8Ur-6PmBwGKXnqcSdQ9nx78hNnm2onjp2Tv4yuXTcTeowOW8VS_32Uv25HDlEA2YXLqwZ9bAadE3YR7zrSGAsMJ5WoXvS3y9qM00ihH0YX--D_LQ2KQi8GO3ki24yaCLECYpyblgiYEhQKJtH0xP6oTiELGl0uIP4jbH6n0ZwfnVwuZSwew"

validator = CognitoJWTValidator(
    region="ca-central-1",
    user_pool_id="ca-central-1_p5Xf8Pk5Z",
    audience=None  # OR your app client ID
)

try:
    claims = validator.verify(token)
    print("Token is valid!")
    print(claims)
except Exception as e:
    print("Invalid token:", e)



# # 1. Decode header only (no verification)
# header = jwt.get_unverified_header(token)
# print("HEADER:", header)
# kid = header['kid']
#
# # Decode payload only (no verification)
# #payload = jwt.decode(token, options={"verify_signature": False})
# #print("PAYLOAD:", payload)
#
# # 2. Fetch JWKS from Cognito
# jwks_url = "https://cognito-idp.ca-central-1.amazonaws.com/ca-central-1_p5Xf8Pk5Z/.well-known/jwks.json"
# jwks = requests.get(jwks_url).json()["keys"]
#
#
# # 3. Find the JWK with the matching kid
# key = next(k for k in jwks if k["kid"] == kid)
#
# # 4. Convert the JWK to a PEM-formatted public key
# public_key = RSAAlgorithm.from_jwk(key)
#
# # 5. Decode and verify the token
# payload = jwt.decode(
#     token,
#     public_key,
#     algorithms=["RS256"],
#     issuer="https://cognito-idp.ca-central-1.amazonaws.com/ca-central-1_p5Xf8Pk5Z",
#     options={"verify_aud": False}  # Disable aud verification unless you need it
# )
#
# print(payload)

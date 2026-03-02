import json
import jwt
import boto3
import os
import logging
from datetime import datetime, timedelta, date
import urllib.request
import urllib.error
import urllib.parse

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')


def lambda_handler(event, context):
    try:
        logger.info(f"Received event: {json.dumps(event)}")

        # Will receive body payload like this in JSON - have to convert that to a form encoded body
        # {
        #     "grant_type": "client_credentials",
        #     "client_id": "224c4h151012ftl8nfsbbhk5rg",
        #     "client_secret": "1k2uuqqva9ujs5ol2at7u2gi4ov8p19vs3r4ei8qf3bd4rabidrj",
        #     "audience": "https://test.api.ats.healthcare"
        # }

        body_str = event.get("body", None)
        if body_str is None:
            return error_response(status_code=400, message="Missing body")

        body = json.loads(body_str)
        client_id = body['client_id']
        client_secret = body['client_secret']
        audience = body['audience']

        cache_key = client_id

        # Check cache first
        cached_token = get_cached_token(client_id, audience)
        if cached_token:
            logger.info(f"Token found in cache for client_id: {client_id}")
            return success_response(cached_token)
        else:
            logger.info(f"Token NOT found in cache for client_id: {client_id}")


        # Get new token using client credentials grant
        token_response = get_cognito_token_client_credentials(client_id=client_id, client_secret=client_secret, audience=audience)
        if not token_response:
            return error_response(500, 'Failed to obtain token from Cognito')

        # Store in cache
        store_token_cache(client_id, audience, token_response['access_token'])
        logger.info(f"New token obtained and cached for client_id: {client_id}")

        return success_response(token_response)

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return error_response(500, 'Internal server error')


def get_cached_token(client_id, audience):
    table = dynamodb.Table(os.environ['TOKEN_CACHE_TABLE'])
    cache_key = f"{client_id}|{audience}"
    try:
        response = table.get_item(Key={'PK': cache_key, 'SK': 'cache'})
        if 'Item' in response:
            # Check if token is still valid (not expired)
            ttl = response['Item'].get('ttl', 0)
            current_time = int(datetime.now().timestamp())
            if ttl > current_time:
                exp = response['Item'].get('exp', current_time)
                expires_in = int(exp - current_time)
                return {'access_token': response['Item']['token'], 'expires_in': expires_in, 'token_type': 'Bearer'}
            else:
                logger.info(f"Cached token expired for key: {cache_key}")
    except Exception as e:
        logger.error(f"Error retrieving cached token: {str(e)}")
    return None


# def get_partner_config(partner_id):
#     table = dynamodb.Table(os.environ['PARTNER_CONFIG_TABLE'])
#     try:
#         response = table.get_item(Key={'partner_id': partner_id})
#         return response.get('Item')
#     except Exception as e:
#         logger.error(f"Error retrieving partner config: {str(e)}")
#         return None


def get_cognito_token_client_credentials(client_id: str, client_secret: str, audience: str):
    try:
        # This should be a configuration - including the entire URL to avoid the region hardcode problem below.
        domain = "m2m-token-202511241354"

        token_url = f"https://{domain}.auth.ca-central-1.amazoncognito.com/oauth2/token"

        # Prepare request data - include the scope that maps to the audience and request to issue a token
        data = f"grant_type=client_credentials&scope={audience}/generate_token"

        # Create Basic Auth header
        import base64
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        # Make the OAuth request
        req = urllib.request.Request(
            token_url,
            data=data.encode(),
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {encoded_credentials}'
            }
        )

        with urllib.request.urlopen(req) as response:
            response_data = json.loads(response.read().decode())
            print(response_data)
            access_token = response_data.get('access_token')

            if access_token:
                logger.info("Successfully obtained access token from Cognito")
                return response_data
            else:
                logger.error("No access token in Cognito response")
                return None

    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error obtaining Cognito token: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        logger.error(f"Error obtaining Cognito token: {str(e)}")
        return None


def store_token_cache(client_id, audience, token):
    table = dynamodb.Table(os.environ['TOKEN_CACHE_TABLE'])

    decoded_token = jwt.decode(token, options={"verify_signature": False})
    exp = decoded_token.get('exp')
    logger.info(F"Token expires at {exp}")

    # Set a dynamic TTL that is at 95% of the time between now and the expiry time of the token

    delta = (exp - datetime.now().timestamp()) * 95 // 100
    print(f"This is the delta: {delta}")

    # Set TTL to 50 minutes (token expires in 1 hour)
    # Set TTL to be 90% of the time between now and the expiry time of the token (currently 1 day, but should be dynamic)
    ttl = int((datetime.now() + timedelta(seconds=delta)).timestamp())
    print(f"This is the TTL: {ttl}")

    # The cache should include audience as a second key to avoid potential cross audience usage

    cache_key = f"{client_id}|{audience}"

    try:
        table.put_item(
            Item={
                'PK': cache_key,
                'SK': 'cache',
                'token': token,
                'exp': exp,
                'ttl': ttl,
                'created_at': datetime.now().isoformat()
            }
        )
        logger.info(f"Token cached successfully for cache_key: {cache_key}")
    except Exception as e:
        logger.error(f"Error storing token in cache: {str(e)}")

    # Capture a count of token requests this customer has made
    # Include the date in the sort key to help partition the data (should add TTL attribute)

    try:
        update_result = table.update_item(
            Key={'PK': cache_key, 'SK': f'requested|{date.today().isoformat()}'},
            ExpressionAttributeNames={'#COUNTER': 'counter'},
            ExpressionAttributeValues={':inc': 1, ':start': 0},
            UpdateExpression=f"SET #COUNTER = if_not_exists(#COUNTER, :start) + :inc"
        )
        print(update_result)
    except Exception as e:
        logger.error(e)
        logger.error(f"Error updating counter for cache_key: {cache_key}")


def success_response(token):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps(token)
    }


def error_response(status_code, message):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'error': message,
            'timestamp': datetime.now().isoformat()
        })
    }
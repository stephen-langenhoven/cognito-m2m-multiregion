import json
import boto3
import os
import logging
from datetime import datetime, timedelta
import base64
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

        # Extract partner_id from query parameters
        query_params = event.get('queryStringParameters') or {}
        partner_id = query_params.get('partner_id')

        if not partner_id:
            return error_response(400, 'Missing partner_id parameter')

        cache_key = f"{partner_id}_token"

        # Check cache first
        cached_token = get_cached_token(cache_key)
        if cached_token:
            logger.info(f"Token found in cache for partner: {partner_id}")
            return success_response(cached_token, 'cache')

        # Cache miss - get partner configuration
        partner_config = get_partner_config(partner_id)
        if not partner_config:
            logger.warning(f"Partner configuration not found: {partner_id}")
            return error_response(404, 'Partner configuration not found')

        # Get new token using client credentials grant
        token = get_cognito_token_client_credentials()
        if not token:
            return error_response(500, 'Failed to obtain token from Cognito')

        # Store in cache
        store_token_cache(cache_key, token, partner_id)
        logger.info(f"New token obtained and cached for partner: {partner_id}")

        return success_response(token, 'cognito')

    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        return error_response(500, 'Internal server error')


def get_cached_token(cache_key):
    table = dynamodb.Table(os.environ['TOKEN_CACHE_TABLE'])
    try:
        response = table.get_item(Key={'cache_key': cache_key})
        if 'Item' in response:
            # Check if token is still valid (not expired)
            ttl = response['Item'].get('ttl', 0)
            if ttl > int(datetime.now().timestamp()):
                return response['Item']['token']
            else:
                logger.info(f"Cached token expired for key: {cache_key}")
    except Exception as e:
        logger.error(f"Error retrieving cached token: {str(e)}")
    return None


def get_partner_config(partner_id):
    table = dynamodb.Table(os.environ['PARTNER_CONFIG_TABLE'])
    try:
        response = table.get_item(Key={'partner_id': partner_id})
        return response.get('Item')
    except Exception as e:
        logger.error(f"Error retrieving partner config: {str(e)}")
        return None


def get_cognito_token_client_credentials():
    try:
        # Get partner configuration to retrieve client credentials
        partner_config = get_partner_config("test-partner-001")  # In production, this would be dynamic
        if not partner_config:
            logger.error("Partner configuration not found for token request")
            return None

        # Prepare OAuth 2.0 client credentials request
        client_id = partner_config['cognito_client_id']
        client_secret = partner_config['cognito_client_secret']
        domain = partner_config.get('cognito_domain', 'default-domain')

        token_url = f"https://{domain}.auth.ca-central-1.amazoncognito.com/oauth2/token"

        # Prepare request data
        data = "grant_type=client_credentials&scope=token-service-api/read token-service-api/write token-service-api/cache"

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
            access_token = response_data.get('access_token')

            if access_token:
                logger.info("Successfully obtained access token from Cognito")
                return access_token
            else:
                logger.error("No access token in Cognito response")
                return None

    except urllib.error.HTTPError as e:
        logger.error(f"HTTP error obtaining Cognito token: {e.code} - {e.read().decode()}")
        return None
    except Exception as e:
        logger.error(f"Error obtaining Cognito token: {str(e)}")
        return None


def store_token_cache(cache_key, token, partner_id):
    table = dynamodb.Table(os.environ['TOKEN_CACHE_TABLE'])
    # Set TTL to 50 minutes (token expires in 1 hour)
    ttl = int((datetime.now() + timedelta(minutes=50)).timestamp())

    try:
        table.put_item(
            Item={
                'cache_key': cache_key,
                'token': token,
                'partner_id': partner_id,
                'ttl': ttl,
                'created_at': datetime.now().isoformat()
            }
        )
        logger.info(f"Token cached successfully for partner: {partner_id}")
    except Exception as e:
        logger.error(f"Error storing token in cache: {str(e)}")


def success_response(token, source):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'access_token': token,
            'source': source,
            'timestamp': datetime.now().isoformat()
        })
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
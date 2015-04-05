__author__ = 'igorsf@gmail.com (Igor Fridman)'

import requests
import datetime
import logging
import uuid
import time
import json
import base64
import rsa
from requests.auth import HTTPBasicAuth

logger = logging.getLogger(__name__)

# Constant strings for OAuth2 flow
# The OAuth authority
AUTHORITY = 'https://login.microsoftonline.com'

# The authorize URL that initiates the OAuth2 client credential flow for admin consent
AUTHORIZE_URL = '{0}{1}'.format(AUTHORITY, '/common/oauth2/authorize?{0}')

# The token issuing endpoint
TOKEN_URL = '{0}{1}'.format(AUTHORITY, '/{0}/oauth2/token')

RESOURCE = 'https://outlook.office365.com/'

# Set to False to bypass SSL verification
# Useful for capturing API calls in Fiddler
VERIFY_SSL = True

REFRESH_STATUS_CODES = [401]


class Error(Exception):
    """Base error for this module."""


class AccessTokenRefreshError(Error):
    """Error trying to refresh an expired access token."""


class SignedJwtAssertionCredentials(requests.auth.AuthBase):

    def __init__(self, client_id, key, thumbprint, tenant_id, user_agent=None):
        self.client_id = client_id
        self.thumbprint = thumbprint
        self.tenant_id = tenant_id
        self.key = key
        self.user_agent = user_agent
        self.access_token = None
        self.token_expiry = None

    def __call__(self, r):
        """
        Append authentication headers to each request.
        Refresh access_tokens when a 401 is received on a request.

        :param r:
        :return:
        """

        if not self.access_token or self.access_token_expired:
            logger.info('Attempting refresh to obtain initial access_token')
            self._access_token()

        request_id = str(uuid.uuid4())

        r.headers = self._build_auth_headers(request_id, "$count" in r.url)

        logger.debug("Appended auth headers {0} to request {1}".format(request_id, r.headers))

        r.register_hook('response', self.response_hook)

        return r

    def _build_auth_headers(self, request_id, is_count=False):
        """
        Build authentication headers dic
        :param request_id:
        :return: dictionary of authentication headers
        """

        headers = {}

        if self.user_agent:
            headers['User-Agent'] = self.user_agent

        # $count requests do not support json accept headers..
        if not is_count:
            headers['Accept'] = 'application/json'

        headers['Authorization'] = 'Bearer {0}'.format(self.access_token)
        headers['client-request-id'] = request_id
        headers['return-client-request-id'] = 'true'

        return headers

    def response_hook(self, r, **kwargs):
        if r.status_code in REFRESH_STATUS_CODES:
            logger.info('Refreshing due to a %s', r.content)
            return self._refresh(r)
        return r

    def _refresh(self, r, **kwargs):
        """
        Attempt to refresh access token
        :return:
        """

        # Fetch new access token
        self._access_token()

        request_id = str(uuid.uuid4())

        # Consume content and release the original connection
        # to allow our new request to reuse the same one.
        r.content
        r.raw.release_conn()
        prep = r.request.copy()

        prep.headers = self._build_auth_headers(request_id)

        logger.debug("Retrying request {0} with new token {1}".format(prep, self.access_token))

        _r = r.connection.send(prep, **kwargs)
        _r.history.append(r)
        _r.request = prep

        return _r

    def _token_url(self):
        return TOKEN_URL.format(self.tenant_id)

    def _access_token(self):
        """
        Obtains access token and its expiration information
        """

        # Construct the required post data
        # See http://www.cloudidentity.com/blog/2015/02/06/requesting-an-aad-token-with-a-certificate-without-adal/

        post_form = {
            'resource': RESOURCE,
            'client_id': self.client_id,
            'client_assertion_type': 'urn:ietf:params:oauth:client-assertion-type:jwt-bearer',
            'client_assertion': self._assertion(),
            'grant_type': 'client_credentials',
            # 'redirect_uri': redirect_uri, # not required in blog post
        }

        r = requests.post(self._token_url(), data=post_form, verify=VERIFY_SSL)
        logger.debug('Received response from token endpoint.')

        if r.status_code == requests.codes.ok:
            d = r.json()
            logger.debug(d)
            self.token_response = d
            self.access_token = d['access_token']
            if 'expires_in' in d:
                self.token_expiry = datetime.timedelta(seconds=int(d['expires_in'])) + datetime.datetime.utcnow()
            else:
                self.token_expiry = None
        else:
            # An {'error':...} response body means the token is expired or revoked,
            # so we flag the credentials as such.
            logger.info('Failed to retrieve access token: %s', r.content)
            error_msg = 'Invalid response %s.' % r.status_code
            raise AccessTokenRefreshError(error_msg)

        logger.debug('access token: {0}'.format(self.access_token))

    def _assertion(self):
        # Create a GUID for the jti claim
        id = str(uuid.uuid4())

        # Build the header
        client_assertion_header = {
            'alg': 'RS256',
            'x5t': self.thumbprint,
        }

        # Create a UNIX epoch time value for now - 5 minutes
        # Why -5 minutes? To allow for time skew between the local machine
        # and the server.
        now = int(time.time()) - 300

        # Create a UNIX epoch time value for now + 10 minutes
        ten_mins_from_now = now + 900

        # Build the payload per
        # http://www.cloudidentity.com/blog/2015/02/06/requesting-an-aad-token-with-a-certificate-without-adal/
        client_assertion_payload = dict(sub=self.client_id, iss=self.client_id, jti=id, exp=ten_mins_from_now, nbf=now,
                                        aud=self._token_url()   )

        string_assertion = json.dumps(client_assertion_payload)
        logger.debug('Assertion: {0}'.format(string_assertion))

        # Generate the stringified header blob
        assertion_blob = self._assertion_blob(client_assertion_header, client_assertion_payload)

        # Sign the data
        signature = self._signature(assertion_blob)

        # Concatenate the blob with the signature
        # Final product should look like:
        # <base64-encoded-header>.<base64-encoded-payload>.<base64-encoded-signature>
        client_assertion = '{0}.{1}'.format(assertion_blob, signature)
        logger.debug('CLIENT ASSERTION: {0}'.format(client_assertion))

        return client_assertion

    def _assertion_blob(self, header, payload):
        # Generate the blob, which looks like:
        # <base64-encoded-header>.<base64-encoded-payload>
        header_string = json.dumps(header).encode('utf-8')
        encoded_header = base64.urlsafe_b64encode(header_string).decode('utf-8').strip('=')
        logger.debug('ENCODED HEADER: {0}'.format(encoded_header))

        payload_string = json.dumps(payload).encode('utf-8')
        encoded_payload = base64.urlsafe_b64encode(payload_string).decode('utf-8').strip('=')
        logger.debug('ENCODED PAYLOAD: {0}'.format(encoded_payload))

        assertion_blob = '{0}.{1}'.format(encoded_header, encoded_payload)
        return assertion_blob

    def _signature(self, message):
        logger.debug('KEY FILE: {0}'.format(self.key))

        private_key = rsa.PrivateKey.load_pkcs1(self.key)

        # Sign the data with the private key
        signature = rsa.sign(message.encode('utf-8'), private_key, 'SHA-256')

        logger.debug('SIGNATURE: {0}'.format(signature))

        # Base64-encode the signature and remove any trailing '='
        encoded_signature = base64.urlsafe_b64encode(signature)
        encoded_signature_string = encoded_signature.decode('utf-8').strip('=')

        logger.debug('ENCODED SIGNATURE: {0}'.format(encoded_signature_string))
        return encoded_signature_string

    @property
    def access_token_expired(self):
        """True if the credential is expired or invalid.

        If the token_expiry isn't set, we assume the token doesn't expire.
        """
        if not self.token_expiry:
            return False

        now = datetime.datetime.utcnow()
        if now >= self.token_expiry:
            logger.info('access_token is expired. Now: %s, token_expiry: %s', now, self.token_expiry)
            return True
        return False

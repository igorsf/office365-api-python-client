__author__ = 'igorsf@gmail.com (Igor Fridman)'

import logging
import logging.config
import unittest

from client import SignedJwtAssertionCredentials

from service import OutlookService

"""Find Azure AD tenant in the "tid" claim within the JWT id_token from consent flow."""
TENANT_ID = 'Office 365 TENANT ID which you can obtain from consent flow'


""" The client ID (register app in Azure AD to get this value) """
CLIENT_ID='PASTE_YOUR_GENERATED_CLIENT_ID_HERE'

""" The full path to your private key file. This file should be in RSA private key format. """
CERT_FILE_PATH = "PASTE_YOUR_PRIVATE_KEY_FULL_PATH"

""" The thumbprint for the certificate that corresponds to your private key. """
CERT_FILE_THUMBPRINT = 'PASTE_YOUR_THUMBPRINT'

""" The application user agent """
APP_USER_AGENT = 'PASTE_YOUR_APPLICATION_USER_AGENT'

""" User context used to run tests """
USER_EMAIL = 'PASTE_TEST_EMAIL_ADDRESS_TO_QUERY'


logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("client").setLevel(logging.INFO)


class OutlookServiceTestCase(unittest.TestCase):

    def setUp(self):
        """
        Build and return an Outlook service object authorized with the service app
        that act on behalf of the given user.
        """

        f = file(CERT_FILE_PATH, 'rb')
        key = f.read()
        f.close()

        credentials = SignedJwtAssertionCredentials(CLIENT_ID, key, CERT_FILE_THUMBPRINT, TENANT_ID,
                                                    APP_USER_AGENT)

        self.service = OutlookService(credentials);

    def test_count_inbox(self):
         # count inbox
        inbox_count = self.service.messages().count(USER_EMAIL)
        logger.debug("inbox count of messages {0}".format(inbox_count))
        self.assertIsNotNone(inbox_count)

    def test_fetch_messages(self):

        # Use query parameters to only request properties we use, to sort by time received, and to limit
        # the results to 10 items.
        query_params = '?$select=From,Subject,DateTimeReceived' \
                       '&$orderby=DateTimeReceived desc' \
                       '&$top=20' \
                       '&$filter=DateTimeReceived ge 2015-03-28T00:00:00Z'

        # list messages in the inbox
        r = self.service.messages().list(USER_EMAIL, query_params)
        logger.debug("list of messages {0}".format(r))
        self.assertIn('value', r)

    def test_fetch_message(self):

        # test random message
        query_params = '?$select=id&$top=1'
        r = self.service.messages().list(USER_EMAIL, query_params)
        message_id = r.get('value')[0].get('Id')
        self.assertIsNotNone(message_id)

        # test fetch message by id
        r = self.service.messages().get(USER_EMAIL, message_id, '?$select=DateTimeReceived')
        logger.debug(r)
        self.assertIn('Id', r)
        self.assertTrue(r['DateTimeReceived'])

    def test_fetch_folders(self):
        r = self.service.folders().list(USER_EMAIL)
        logger.debug(r)
        logger.debug("Count of folders {0}".format(len(r)))
        self.assertTrue(len(r) > 0, "Must have folders")

if __name__ == '__main__':
    unittest.main()
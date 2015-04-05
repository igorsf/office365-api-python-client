__author__ = 'igorsf@gmail.com (Igor Fridman)'

import logging
import requests

logger = logging.getLogger(__name__)


class OutlookService():
    OUTLOOK_SERVICE_URL = "https://outlook.office365.com/api/v1.0/users('{0}')"

    def __init__(self, credentials):
        self.credentials = credentials

    def messages(self):
        return self.Messages(self)

    def folders(self):
        return self.Folders(self)

    class Folders():

        def __init__(self, outer):
            self.outer = outer
            self.url = outer.OUTLOOK_SERVICE_URL + "/folders"

        # GET https://outlook.office365.com/api/v1.0/me/folders
        #GET https://outlook.office365.com/api/v1.0/me/folders/{folder_id}/childfolders
        def list(self, user_context, folder_id=None):
            '''
            Fetch list of folders
            :param user_context: user to fetch
            :param folder_id: optional list sub-folders
            :return:
            '''

            url = self.url.format(user_context)
            r = requests.get(url, auth=self.outer.credentials, verify=True)

            logger.debug('Response: {0}'.format(r))
            if r.status_code == requests.codes.ok:
                return r.json()['value']
            return None

    class Messages():

        def __init__(self, outer):
            self.outer = outer
            self.url = outer.OUTLOOK_SERVICE_URL + "/messages"

        # Retrieves a set of messages from the user's Inbox
        # parameters:
        #     user_id: user identifier
        #     parameters: string. An optional string containing query parameters to filter, sort, etc.
        #                 http://msdn.microsoft.com/office/office365/APi/complex-types-for-mail-contacts-calendar#UseODataqueryparameters
        def list(self, user_context, parameters=None):
            logger.debug('Entering list messages.')
            url = self.url.format(user_context)

            if parameters:
                url = url + parameters

            logger.debug('url: {0}'.format(url))

            r = requests.get(url, auth=self.outer.credentials, verify=True)
            logger.debug('Response: {0}'.format(r))
            if r.status_code == requests.codes.ok:
                return r.json()
            return None

        def count(self, user_context, parameters=None):
            """
            Return count of messages
            :param user_context:
            :param parameters:
            :return:
            """
            logger.debug('entering count message')

            url = self.url.format(user_context) + "/$count"
            if parameters:
                url = url + parameters;

            logger.debug('url: {0}'.format(url))

            r = requests.get(url, auth=self.outer.credentials, verify=True)

            logger.debug('Response: {0}'.format(r))
            if r.status_code == requests.codes.ok:
                return r.content
            return None

        def get(self, user_context, message_id, parameters=None):
            """
                Retrieve a single message by id
                :param user_context:
                :param message_id:
                :param parameters:
                :return:
                """
            logger.debug('entering get message.')
            logger.debug('message id {}'.format(message_id))
            url = self.url.format(user_context) + "/{0}".format(message_id)

            if parameters:
                url = url + parameters

            logger.debug('url: {0}'.format(url))

            r = requests.get(url, auth=self.outer.credentials, verify=True)

            if r.status_code == requests.codes.ok:
                return r.json()
            return None
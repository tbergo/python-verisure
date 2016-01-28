""" Represents a MyPages session """

import json

from bs4 import BeautifulSoup

import requests

# this import is depending on python version
try:
    import HTMLParser
    UNESCAPE = HTMLParser.HTMLParser().unescape
except ImportError:
    import html
    UNESCAPE = html.unescape


DOMAIN = 'https://mypages.verisure.com'
URL_LOGIN = DOMAIN + '/j_spring_security_check?locale=en_GB'
URL_START = DOMAIN + '/uk/start.html'
RESPONSE_TIMEOUT = 3


class Error(Exception):
    ''' mypages error '''
    pass


class LoginError(Error):
    ''' login failed '''
    pass


class ResponseError(Error):
    ''' Unexcpected response '''
    pass


class LoggedOutError(ResponseError):
    ''' Unexcpected response '''
    pass


class TemporarilyUnavailableError(ResponseError):
    ''' My Pages is temporarily unavailable '''
    pass


class MaintenanceError(ResponseError):
    ''' My Pages is currently in maintenance '''
    pass


class Session(object):
    """ Verisure session """

    def __init__(self, username, password):
        self._session = None
        self._username = username
        self._password = password
        self.csrf = ''

    def login(self):
        """ Login to mypages

        Login before calling any read or write commands

        """
        self._session = requests.Session()
        auth = {
            'j_username': self._username,
            'j_password': self._password
            }
        req = requests.Request(
            'POST',
            URL_LOGIN,
            cookies=dict(self._session.cookies),
            data=auth
            ).prepare()
        response = self._session.send(req, timeout=RESPONSE_TIMEOUT)
        self.validate_response(response)
        status = self.json_to_dict(response.text)
        if not status['status'] == 'ok':
            raise LoginError(status['message'])
        self.csrf = self._get_csrf()

    def logout(self):
        """ Ends session

        note:
            Ends the session, will not call the logout command on mypages

        """
        self._session.close()
        self._session = None

    def get(self, url):
        """ Read all statuses of a device type """
        self._ensure_session()
        try:
            response = self._session.get(DOMAIN + url)
        except Exception as e:
            raise Error(e)
        self.validate_response(response)
        return self.json_to_dict(UNESCAPE(response.text))

    def post(self, url, data):
        """ send post request """
        self._ensure_session()
        req = requests.Request(
            'POST',
            DOMAIN + url,
            cookies=dict(self._session.cookies),
            headers={'X-CSRF-TOKEN': self.csrf},
            data=data
            ).prepare()
        response = self._session.send(
            req,
            timeout=RESPONSE_TIMEOUT)
        self.validate_response(response)
        return response.text

    def put(self, url, data):
        """ send put request """
        self._ensure_session()
        req = requests.Request(
            'PUT',
            DOMAIN + url,
            cookies=dict(self._session.cookies),
            headers={
                'X-CSRF-TOKEN': self.csrf,
                'content-type': 'application/json'},
            data=json.dumps(data)
            ).prepare()
        response = self._session.send(
            req,
            timeout=RESPONSE_TIMEOUT)
        self.validate_response(response)
        return response.text

    def _get_csrf(self):
        """ Retreive X-CSRF-TOKEN from start.html """
        response = self._session.get(
            URL_START,
            timeout=RESPONSE_TIMEOUT)
        self.validate_response(response)
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.body.find(attrs={'name': '_csrf'})['value']

    def _ensure_session(self):
        ''' ensures that a session is created '''
        if not self._session:
            raise Error('Session not started')

    def json_to_dict(self, doc):
        ''' transform json with unicode characters to dict '''
        if not doc:
            return ''
        try:
            return json.loads(doc)
        except ValueError as e:
            self.raise_response_error(
                doc,
                ResponseError(
                    'Unable to convert to JSON, '
                    'Error: {0} - Data: {1}'.format(e, doc)))

    def validate_response(self, response):
        """ Verify that response is OK """
        if response.status_code == 200:
            return
        self.raise_response_error(
            response.text,
            ResponseError(
                'Unable to validate response form My Pages'
                ', status code: {0} - Data: {1}'.format(
                    response.status_code,
                    response.text.encode('utf-8'))))

    @staticmethod
    def raise_response_error(doc, default_error):
        """ Create correct error type from response """
        soup = BeautifulSoup(doc, 'html.parser')
        if not soup.tile:
            raise default_error
        if soup.title == 'My Pages is temporarily unavailable -  Verisure':
            raise TemporarilyUnavailableError('Temporarily unavailable')
        if soup.title == 'My Pages - Maintenance -  Verisure':
            raise MaintenanceError('Maintenance')
        if soup.title == 'Choose country - My Pages - Verisure':
            raise LoggedOutError('Not logged in')
        if soup.title == 'Log in - My Pages - Verisure':
            raise LoggedOutError('Not logged in')
        raise ResponseError(soup.title)

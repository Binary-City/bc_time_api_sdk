from datetime import datetime, timezone, timedelta
from requests import codes as requests_status_codes
from requests.exceptions import RequestException
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding
from json import dumps as json_dumps
from base64 import b64encode
from bc_time.system.encryption.crypt import Crypt
from bc_time.system.constants.encryption.crypt import Crypt as CryptConstants
from bc_time.requests.base import Base as RequestsBase
from bc_time.oauth2.constants.grant_type import GrantType as OAuth2GrantType
from bc_time.api.constants.api import Api as ApiConstants
from bc_time.api.enumerators.request_status import RequestStatus
from bc_time.system.constants.datetime.format import Format as DateTimeFormat

class Token(RequestsBase):
    # Private
    __crypt = None
    __oauth2_token_url: str = None

    # Public
    client_id = None
    client_secret = None
    crypt_key = None
    grant_type = None
    code = None
    private_key_file_path = None
    username = None
    password = None
    token = None
    token_expire_as_str = None # This will be stored in UTC.
    timeout = ApiConstants.DEFAULT_REQUEST_TIMEOUT

    @property
    def crypt(self) -> Crypt:
        if self.__crypt is None:
            self.__crypt = Crypt(key=self.crypt_key)
        return self.__crypt

    @crypt.setter
    def crypt(self, value: Crypt):
        self.__crypt = value

    def __init__(self, client_id: str=None, client_secret: str=None, crypt_key: str=None, grant_type: str=None, code: str=None, private_key_file_path: str=None, oauth2_token_url: str=None, timeout: float=None) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.crypt_key = crypt_key
        self.grant_type = grant_type
        self.code = code
        self.private_key_file_path = private_key_file_path
        self.__oauth2_token_url = oauth2_token_url
        if timeout is not None:
            self.timeout = float(timeout)

    def request_token(self) -> tuple[bool, dict]:
        try:
            if self.__has_valid_token():
                return True, None
            if not self.__validate_data():
                return False, self._get_error_response_data(
                    request_status=RequestStatus.data_invalid,
                    error_description=f"Credentials are missing or incomplete for grant_type '{self.grant_type}'; also verify that grant_type itself is correct."
                )
            try:
                data = self.__get_data()
            except (OSError, ValueError, TypeError) as exception:
                # Covers a missing, unreadable, malformed or password-protected private key file (JWT grant type).
                return False, self._get_error_response_data(
                    request_status=RequestStatus.data_invalid,
                    error_description=f"Could not prepare the token request: {exception}"
                )
            if data is None:
                return False, self._get_error_response_data(
                    request_status=RequestStatus.data_invalid,
                    error_description=f"Unsupported grant_type '{self.grant_type}'."
                )
            try:
                request_response = self.session.post(
                    url=self.__oauth2_token_url,
                    data=data,
                    timeout=self.timeout
                )
            except RequestException as exception:
                return False, self._get_error_response_data(
                    request_status=RequestStatus.no_response,
                    error_description=f"No response from the token endpoint: {exception}"
                )
            if request_response.status_code != requests_status_codes.ok:
                return False, self._get_error_response_data(
                    request_status=RequestStatus.response_invalid,
                    error_description=f"The token request failed with HTTP status {request_response.status_code}."
                )
            response_data = self._get_response_data(request_response.text)
            if not set(('access_token', 'expires_in')).issubset(response_data.keys()):
                return False, response_data
            try:
                token_expire = datetime.now(timezone.utc) + timedelta(seconds=float(response_data['expires_in']))
            except (TypeError, ValueError):
                return False, self._get_error_response_data(
                    request_status=RequestStatus.response_json_invalid,
                    error_description=f"The token response contained an invalid expires_in value: {response_data['expires_in']!r}"
                )
            self.token = response_data['access_token']
            self.token_expire_as_str = token_expire.strftime(DateTimeFormat.MY_SQL_DATE_TIME)
            return True, response_data
        finally:
            # Clear up sensitive user credentials.
            if self.username is not None:
                self.username = None
            if self.password is not None:
                self.password = None

    def __has_valid_token(self) -> bool:
        if self.token is None or self.token_expire_as_str is None:
            return False
        now = datetime.now(timezone.utc)
        return self.token_expire_as_str > now.strftime(DateTimeFormat.MY_SQL_DATE_TIME)

    def __validate_data(self) -> bool:
        if self.__oauth2_token_url is None:
            return False
        data = ()
        if self.grant_type == OAuth2GrantType.AUTH_CODE:
            data = (self.client_id, self.client_secret, self.code)
        elif self.grant_type == OAuth2GrantType.CLIENT_CREDENTIALS:
            data = (self.client_id, self.client_secret)
        elif self.grant_type == OAuth2GrantType.JWT_BEARER:
            data = (self.client_id, self.private_key_file_path)
        elif self.grant_type == OAuth2GrantType.USER_CREDENTIALS:
            data = (self.client_id, self.client_secret, self.username, self.password)
        # We don't expect this to ever be true, but if it is, let's rather be sceptical.
        if not data:
            return False
        none_values = [value for value in data if value is None] # Grab all values that are None.
        return len(none_values) == 0 # We want no data to be None.

    def __get_data(self) -> dict|None:
        if self.grant_type == OAuth2GrantType.AUTH_CODE:
            return {
                'grant_type': self.grant_type,
                'client_id': self.client_id,
                'client_secret': self.__get_client_secret(),
                'code': self.code,
            }
        elif self.grant_type == OAuth2GrantType.CLIENT_CREDENTIALS:
            return {
                'grant_type': self.grant_type,
                'client_id': self.client_id,
                'client_secret': self.__get_client_secret(),
            }
        elif self.grant_type == OAuth2GrantType.JWT_BEARER:
            return {
                'grant_type': self.grant_type,
                'assertion': self.__get_jwt_assertion(),
            }
        elif self.grant_type == OAuth2GrantType.USER_CREDENTIALS:
            return {
                'grant_type': self.grant_type,
                'client_id': self.client_id,
                'client_secret': self.__get_client_secret(),
                'username': self.username,
                'password': self.__get_password(),
            }

    def __get_client_secret(self) -> str:
        if self.crypt_key is not None:
            self.crypt.data = self.client_secret
            return self.crypt.encrypt()
        return self.client_secret

    def __get_jwt_assertion(self, separator: str='.') -> str:
        assertion_data = self.__get_jwt_assertion_data()
        assertion_data.append(self.__get_jwt_assertion_data_signature(
            assertion_data=assertion_data,
            separator=separator
        ))
        return separator.join(assertion_data)

    def __get_jwt_assertion_data(self, expire_in_seconds: int=60) -> list:
        expire_datetime = datetime.now(timezone.utc) + timedelta(seconds=expire_in_seconds)
        assertion_data = [
            {'algo': CryptConstants.PHP_OPENSSL_ALGO_SHA1},
            {
                'client_id': self.client_id,
                'issued': datetime.now(timezone.utc).strftime(DateTimeFormat.MY_SQL_DATE_TIME),
                'expire': expire_datetime.strftime(DateTimeFormat.MY_SQL_DATE_TIME),
            },
        ]
        return list(map(lambda data_value: str(b64encode(bytes(json_dumps(data_value), 'utf8')), 'utf8'), assertion_data))

    def __get_jwt_assertion_data_signature(self, assertion_data: list, separator: str) -> str:
        with open(self.private_key_file_path, mode='rb') as opened_key_file:
            private_key = serialization.load_pem_private_key(
                opened_key_file.read(),
                password=None
            )
        sign_data = separator.join(assertion_data)
        signature = private_key.sign(
            data=bytes(sign_data, 'utf8'),
            padding=padding.PKCS1v15(),
            algorithm=hashes.SHA1()
        )
        return str(b64encode(signature), 'utf8')

    def __get_password(self) -> str:
        if self.crypt_key is not None:
            self.crypt.data = self.password
            return self.crypt.encrypt()
        return self.password
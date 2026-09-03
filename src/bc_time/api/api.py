from os.path import exists as path_exists
from pathlib import Path
from json import dumps as json_dumps
from logging import getLogger
from requests import codes as requests_status_codes
from requests.exceptions import RequestException
from configparser import ConfigParser, Error as ConfigParserError
from bc_time.system.encryption.crypt import Crypt
from bc_time.system.validate import Validate
from bc_time.requests.base import Base as RequestsBase
from bc_time.oauth2.token import Token
from bc_time.api.constants.api import Api as ApiConstant
from bc_time.api.enumerators.content_type import ContentType
from bc_time.api.enumerators.request_status import RequestStatus

logger = getLogger('bc_time')

class Api(RequestsBase):
    # Private
    __crypt = None
    __token = None

    # Public
    client_id = None
    client_secret = None
    crypt_key = None
    grant_type = None
    code = None
    private_key_file_path = None
    time_domain = None
    timeout = ApiConstant.DEFAULT_REQUEST_TIMEOUT

    @property
    def oauth2_token_url(self) -> str:
        return self.time_domain + ApiConstant.OAUTH2_TOKEN_URL_PATH

    @property
    def oauth2_authorise_url(self) -> str:
        return self.time_domain + ApiConstant.OAUTH2_AUTHORISE_URL_PATH

    @property
    def api_url(self) -> str:
        return self.time_domain + ApiConstant.API_URL_PATH

    @property
    def crypt(self) -> Crypt:
        if self.__crypt is None:
            self.__crypt = Crypt(key=self.crypt_key)
        return self.__crypt

    @property
    def token(self) -> Token:
        if self.__token is None:
            self.__token = Token(
                client_id=self.client_id,
                client_secret=self.client_secret,
                crypt_key=self.crypt_key,
                grant_type=self.grant_type,
                code=self.code,
                private_key_file_path=self.private_key_file_path,
                oauth2_token_url=self.oauth2_token_url,
                timeout=self.timeout
            )
        return self.__token

    def __init__(self, client_id: str=None, client_secret: str=None, crypt_key: str=None, grant_type: str=None, code: str=None, private_key_file_path: str=None, time_domain: str=None, timeout: float=None) -> None:
        self.__init_config_from_file()
        if client_id is not None:
            self.client_id = client_id
        if client_secret is not None:
            self.client_secret = client_secret
        if crypt_key is not None:
            self.crypt_key = crypt_key
        if grant_type is not None:
            self.grant_type = grant_type
        if code is not None:
            self.code = code
        if private_key_file_path is not None:
            self.private_key_file_path = private_key_file_path
        if time_domain is not None:
            self.time_domain = time_domain
        if timeout is not None:
            self.timeout = timeout
        try:
            self.timeout = float(self.timeout) # The config file yields a str; the constructor may yield an int.
        except (TypeError, ValueError):
            logger.warning("Invalid timeout value %r (from the constructor or the config file); falling back to the default of %s seconds.", self.timeout, ApiConstant.DEFAULT_REQUEST_TIMEOUT)
            self.timeout = ApiConstant.DEFAULT_REQUEST_TIMEOUT
        self.__init_time_domain()
        self.token.crypt = self.crypt
        self.token.session = self.session

    def __init_config_from_file(self, file_path: str='.bc_time/config', section: str='default') -> None:
        time_config_file_path = self.__get_time_config_file_path(file_path=file_path)
        if time_config_file_path is None:
            return
        config_parser = ConfigParser(inline_comment_prefixes=';')
        try:
            config_parser.read(time_config_file_path)
        except ConfigParserError as exception:
            logger.warning("Could not parse the config file at '%s'; ignoring it: %s", time_config_file_path, exception)
            return
        if section not in config_parser:
            return
        config_data_keys_and_attributes = ['client_id', 'client_secret', 'crypt_key', 'grant_type', 'private_key_file_path', 'time_domain', 'timeout']
        for config_data_key_or_attribute in config_data_keys_and_attributes:
            if config_data_key_or_attribute in config_parser[section]:
                setattr(
                    self,
                    config_data_key_or_attribute,
                    config_parser[section][config_data_key_or_attribute]
                )

    def __get_time_config_file_path(self, file_path: str) -> str|None:
        time_config_file_path = f"{str(Path.home())}/{file_path}"
        if  path_exists(time_config_file_path):
            return time_config_file_path
        # Legacy code - accommodate previous config filename.
        time_config_file_path = f"{str(Path.home())}/.bc_time/credentials"
        return time_config_file_path if path_exists(time_config_file_path) else None

    def __init_time_domain(self) -> None:
        if self.time_domain is None:
            self.time_domain = ApiConstant.TIME_DOMAIN
        if not self.time_domain.startswith(('https://', 'http://')):
            self.time_domain = f"https://{self.time_domain}"
        self.time_domain = self.time_domain.rstrip('/')

    def create(self, content_type_id: ContentType, payload: dict, content_uid: int|str=None) -> dict:
        request_token_result, request_token_response_data = self.token.request_token()
        if not request_token_result:
            return request_token_response_data
        create_payload = self.__get_create_or_update_data(
            content_type_id=content_type_id,
            payload=payload,
            content_uid=content_uid
        )
        return self.__send_api_request('post', data=create_payload)

    def update(self, content_type_id: ContentType, content_uid: int|str, payload: dict) -> dict:
        request_token_result, request_token_response_data = self.token.request_token()
        if not request_token_result:
            return request_token_response_data
        update_payload = self.__get_create_or_update_data(
            content_type_id,
            content_uid=content_uid,
            payload=payload
        )
        return self.__send_api_request('post', data=update_payload)

    def __send_api_request(self, http_method: str, **request_kwargs) -> dict:
        try:
            request_response = self.session.request(
                method=http_method,
                url=self.api_url,
                timeout=self.timeout,
                **request_kwargs
            )
        except RequestException as exception:
            logger.warning("No response from the API: %s", exception)
            return self._get_error_response_data(
                request_status=RequestStatus.no_response,
                error_description=f"No response from the API: {exception}"
            )
        if request_response.status_code != requests_status_codes.ok:
            return self._get_error_response_data(
                request_status=RequestStatus.response_invalid,
                error_description=f"The API request failed with HTTP status {request_response.status_code}."
            )
        return self._get_response_data(request_response.text)

    def __get_create_or_update_data(self, content_type_id: ContentType, payload: dict, content_uid: int|str=None) -> dict:
        data = {'content_type_id': int(content_type_id)}
        if content_uid: # Will be omitted if performing POST (1 new object).
            data['content_uid'] = content_uid
        if payload:
            if content_uid != ApiConstant.UID_POST_MANY:
                data.update(payload)
            else:
                data['data'] = payload
        create_or_update_payload = {'access_token': self.token.token}
        if self.crypt_key is not None:
            self.crypt.data = json_dumps(data)
            create_or_update_payload['data'] = self.crypt.encrypt()
        else:
            create_or_update_payload.update(data)
        return create_or_update_payload

    def get_all_using_pagination(self, content_type_id: ContentType, content_uid: int=ApiConstant.UID_GET_ALL, filters: dict=None, page: int=1, row_count: int=ApiConstant.DEFAULT_ROW_COUNT) -> dict:
        request_token_result, request_token_response_data = self.token.request_token()
        if not request_token_result:
            return request_token_response_data
        request_params = self.__get_request_params(
            content_type_id=content_type_id,
            content_uids=[content_uid],
            filters=filters,
            page=page,
            row_count=row_count
        )
        return self.__send_api_request('get', params=request_params)

    def get_one(self, content_type_id: ContentType, content_uid: int|str) -> dict:
        request_token_result, request_token_response_data = self.token.request_token()
        if not request_token_result:
            return request_token_response_data
        request_params = self.__get_request_params(content_type_id, content_uids=[content_uid])
        return self.__send_api_request('get', params=request_params)

    def get_many(self, content_type_id: ContentType, content_uids: list) -> dict:
        if not content_uids:
            return self._get_error_response_data(
                request_status=RequestStatus.uid_invalid,
                error_description="content_uids must contain at least one content UID."
            )
        request_token_result, request_token_response_data = self.token.request_token()
        if not request_token_result:
            return request_token_response_data
        request_params = self.__get_request_params(content_type_id, content_uids)
        return self.__send_api_request('get', params=request_params)

    def __get_request_params(self, content_type_id: ContentType, content_uids: list=None, filters: dict=None, page: int=None, row_count: int=None) -> dict:
        data = {
            'content_type_id': int(content_type_id),
            'content_uid': content_uids[0] if len(content_uids) == 1 else ','.join([str(content_uid) for content_uid in content_uids]),
        }
        if self.__can_paginate(page, row_count):
            data['page'] = page
            data['row_count'] = row_count
        if filters is not None:
            data.update(filters)
        request_params = {'access_token': self.token.token}
        if self.crypt_key is not None:
            self.crypt.data = json_dumps(data)
            request_params['data'] = self.crypt.encrypt()
        else:
            request_params.update(data)
        return request_params

    def __can_paginate(self, page: int, row_count: int) -> bool:
        if not Validate.is_numeric(page, min=1):
            return False
        return Validate.is_numeric(row_count, min=1, max=ApiConstant.DEFAULT_ROW_COUNT)
from json import JSONDecodeError, loads as json_loads
from logging import getLogger
from requests import Session
from bc_time.api.enumerators.request_status import RequestStatus

logger = getLogger('bc_time')

class Base:
    # Private
    __session = None

    @property
    def session(self) -> Session:
        if self.__session is None:
            self.__session = Session()
        return self.__session

    @session.setter
    def session(self, value: Session) -> None:
        self.__session = value

    def close(self) -> None:
        if self.__session is not None:
            self.__session.close()
            self.__session = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _get_response_data(self, response_text: str) -> dict:
        response_data = None
        if self.crypt_key is not None:
            self.crypt.data = response_text
            response_data = self.crypt.decrypt()
        if not response_data:
            response_data = response_text
        try:
            response_data = json_loads(response_data)
        except JSONDecodeError as exception:
            logger.warning("Could not parse API response as JSON: %s", exception)
            return self._get_error_response_data(
                request_status=RequestStatus.response_json_invalid,
                error_description="The API response could not be parsed as JSON. If a crypt_key is configured, verify that it is correct."
            )
        if not isinstance(response_data, dict):
            return self._get_error_response_data(
                request_status=RequestStatus.response_json_invalid,
                error_description="The API response was valid JSON, but not a JSON object."
            )
        return response_data

    @staticmethod
    def _get_error_response_data(request_status: RequestStatus, error_description: str) -> dict:
        return {
            'status': request_status,
            'error_description': error_description,
        }
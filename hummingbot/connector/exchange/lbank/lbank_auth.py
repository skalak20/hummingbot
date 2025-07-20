from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTRequest, WSRequest


class LbankAuth(AuthBase):
    def __init__(self, api_key: str, secret_key: str):
        self.api_key = api_key
        self.secret_key = secret_key

    def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        raise NotImplementedError

    def ws_authenticate(self, request: WSRequest) -> WSRequest:
        raise NotImplementedError

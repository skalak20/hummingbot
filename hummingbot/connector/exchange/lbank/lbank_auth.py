import hashlib
import hmac
from base64 import b64encode

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5

from hummingbot.connector.exchange.lbank.error import CommonError
from hummingbot.connector.exchange.lbank.lbank_constants import ALLOW_METHOD, API_HMACSHA, HMACSHA256_STR, RSA_STR
from hummingbot.connector.exchange.lbank.lbank_utils import build_md5, random_str
from hummingbot.connector.time_synchronizer import TimeSynchronizer
from hummingbot.core.web_assistant.auth import AuthBase
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSRequest


class LbankAuth(AuthBase):

    def __init__(
        self,
        sign_method: str = RSA_STR,
        api_key: str = None,
        api_secret: str = None,
        time_provider: TimeSynchronizer = None,
    ):
        self.sign_method = sign_method.upper()
        if self.sign_method not in ALLOW_METHOD:
            raise CommonError(f"{sign_method} sign method is not supported!")
        if self.sign_method == HMACSHA256_STR:
            self.sign_method = API_HMACSHA
        self.api_key = api_key
        self.api_secret = api_secret
        self.time_provider = time_provider
        self.random_str = None
        self.timestamp = None

    def rest_authenticate(self, request: RESTRequest) -> RESTRequest:
        """
        Adds the server time and the signature to the request, required for authenticated interactions. It also adds
        the required parameter in the request header.

        :param request: the request to be configured for authenticated interaction
        """

        payload = self.build_payload(None)

        if "signature_method" in payload:
            del payload["signature_method"]
        if "echostr" in payload:
            del payload["echostr"]
        if "timestamp" in payload:
            del payload["timestamp"]

        if request.method == RESTMethod.POST:
            request.data = payload
        else:
            request.params = payload

        request.headers = self.build_header()

        return request

    def ws_authenticate(self, request: WSRequest) -> WSRequest:
        """
        This method is intended to configure a websocket request to be authenticated. Mexc does not use this
        functionality
        """
        return request  # pass-through

    def build_header(self) -> dict:
        """
        build request header

        @return:dict:
        """
        self.random_str = random_str()
        self.timestamp = int(self.time_provider.time() * 1e3)  # get_timestamp()
        return {
            "Content-Type": 'application/x-www-form-urlencoded',
            "signature_method": self.sign_method,
            "timestamp": self.timestamp,
            "echostr": self.random_str,
        }

    def build_rsasignv2(self, payload: dict) -> str:
        """
        build the sign
        """
        if self.api_secret is None:
            raise CommonError("private key is empty!")

        msg = build_md5(payload)
        private_key = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            + self.api_secret
            + "\n-----END RSA PRIVATE KEY-----"
        )
        pri_key = PKCS1_v1_5.new(RSA.importKey(private_key))
        digest = SHA256.new(msg.encode("utf8"))
        sign = b64encode(pri_key.sign(digest))
        return sign.decode("utf8")

    def build_hmacsha256(self, payload: dict) -> str:
        """
        build the signature of the HmacSHA256
        """
        msg = build_md5(payload)
        api_secret = bytes(self.api_secret, encoding="utf8")
        payload = bytes(msg, encoding="utf8")
        signature = (
            hmac.new(
                api_secret,
                payload, digestmod=hashlib.sha256).hexdigest().lower()
        )
        return signature

    def build_payload(self, payload: dict) -> dict:
        """
        @param payload: request form
        @return:
        """

        payload["api_key"] = self.api_key
        payload["timestamp"] = self.timestamp
        payload["signature_method"] = self.sign_method
        payload["echostr"] = self.random_str

        if self.sign_method == RSA_STR:
            payload["sign"] = self.build_rsasignv2(payload)
        elif self.sign_method == API_HMACSHA:
            payload["sign"] = self.build_hmacsha256(payload)
        else:
            raise CommonError(f"{self.sign_method} sign method is not supported!")
        return payload

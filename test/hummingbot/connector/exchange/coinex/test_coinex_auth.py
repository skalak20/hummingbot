import asyncio
import hashlib
import hmac
import json
from typing import Awaitable
from unittest import TestCase
from unittest.mock import MagicMock
from urllib.parse import urlencode

from hummingbot.connector.exchange.coinex import coinex_constants as CONSTANTS, coinex_web_utils as web_utils
from hummingbot.connector.exchange.coinex.coinex_auth import CoinexAuth
from hummingbot.core.web_assistant.connections.data_types import RESTMethod, RESTRequest, WSJSONRequest

TEST_TS_SEC = 1700490703.564
TEST_KEY = "560CE33AA5E845929981B163ABD2B25F"
TEST_SECRET = "CB83A671B4F31671138589A7C8805D0C79FEEA9B298A14C7"


class CoinexAuthTests(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self._api_key = TEST_KEY
        self._secret_key = TEST_SECRET

        self._mock_time_provider = MagicMock()
        self._mock_time_provider.time.return_value = TEST_TS_SEC

        self._auth = CoinexAuth(
            api_key=self._api_key,
            api_secret=self._secret_key,
            time_provider=self._mock_time_provider)

    def _async_run_with_timeout(self, coroutine: Awaitable, timeout: int = 1):
        ret = asyncio.get_event_loop().run_until_complete(asyncio.wait_for(coroutine, timeout))
        return ret

    def _sign(self, message: str, key: str) -> str:
        signed_message = hmac.new(
            bytes(key, "latin-1"),
            bytes(message, "latin-1"),
            hashlib.sha256
        ).hexdigest().lower()
        return signed_message

    def test_add_auth_headers_to_get_request_without_params(self):
        url = web_utils.private_rest_url(path_url=CONSTANTS.SERVER_TIME_EP)

        request = RESTRequest(
            method=RESTMethod.GET,
            url=url,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.SERVER_TIME_EP
        )

        self._async_run_with_timeout(self._auth.rest_authenticate(request))

        test_timestamp = f"{TEST_TS_SEC * 1e3:.0f}"
        full_endpoint = f"GET{request.throttler_limit_id}{test_timestamp}"
        expected_signature = self._sign(message=full_endpoint, key=TEST_SECRET)
        self.assertEqual(request.headers[CONSTANTS.H_SIGN], expected_signature)
        self.assertEqual(request.headers[CONSTANTS.H_KEY], TEST_KEY)
        self.assertEqual(request.headers[CONSTANTS.H_TS], test_timestamp)

    def test_add_auth_headers_to_get_request_with_params(self):
        CURRENT_TS = f"{TEST_TS_SEC * 1e3:.0f}"
        url = web_utils.private_rest_url(path_url=CONSTANTS.SERVER_TIME_EP)
        params = {
            "param_a": "value_param_a",
            "param_z": "value_param_z",
        }

        request = RESTRequest(
            method=RESTMethod.GET,
            url=url,
            params=params,
            is_auth_required=True,
            throttler_limit_id=CONSTANTS.SERVER_TIME_EP
        )

        self._async_run_with_timeout(self._auth.rest_authenticate(request))

        full_endpoint = f"GET{request.throttler_limit_id}?{urlencode(params)}{CURRENT_TS}"
        expected_signature = self._sign(message=full_endpoint, key=TEST_SECRET)
        self.assertEqual(request.headers[CONSTANTS.H_SIGN], expected_signature)
        self.assertEqual(request.headers[CONSTANTS.H_KEY], TEST_KEY)
        self.assertEqual(request.headers[CONSTANTS.H_TS], CURRENT_TS)

    def test_add_auth_headers_to_post_request(self):
        CURRENT_TS = f"{TEST_TS_SEC * 1e3:.0f}"
        TEST_EP = "/api/endpoint"
        body = {
            "param_a": "value_param_a",
            "param_z": "value_param_z",
        }

        request = RESTRequest(
            method=RESTMethod.POST,
            url=f"https://test.url{TEST_EP}",
            data=json.dumps(body),
            is_auth_required=True,
            throttler_limit_id=TEST_EP
        )

        self._async_run_with_timeout(self._auth.rest_authenticate(request))

        full_endpoint = f"POST{request.throttler_limit_id}{json.dumps(body)}{CURRENT_TS}"
        expected_signature = self._sign(message=full_endpoint, key=TEST_SECRET)
        self.assertEqual(request.headers[CONSTANTS.H_SIGN], expected_signature)
        self.assertEqual(request.headers[CONSTANTS.H_KEY], TEST_KEY)
        self.assertEqual(request.headers[CONSTANTS.H_TS], CURRENT_TS)

    def test_no_auth_added_to_wsrequest(self):
        payload = {"param1": "value_param_1"}
        request = WSJSONRequest(payload=payload, is_auth_required=True)

        self._async_run_with_timeout(self._auth.ws_authenticate(request))

        self.assertEqual(payload, request.payload)

    def test_ws_auth_prepare(self):
        request = WSJSONRequest(payload={}, is_auth_required=True)
        ws_auth_msg = self._async_run_with_timeout(self._auth.ws_authenticate(request))

        api_key = ws_auth_msg["params"]["access_id"]
        expires = ws_auth_msg["params"]["timestamp"]
        signature = ws_auth_msg["params"]["signed_str"]

        self.assertEqual(ws_auth_msg["method"], f"{CONSTANTS.WS_METHOD_SERVER_SIGN}")
        self.assertEqual(api_key, TEST_KEY)
        self.assertEqual(signature, self._auth.gen_sign(expires))

import time
from typing import Any, Dict

from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap


def get_timestamp() -> str:
    return str(int(time.time() * 1000)).split(".", maxsplit=1)[0]


def combine_to_hb_trading_pair(pair_info) -> str:
    trading_pair = f"{pair_info["trading_name"]}-{pair_info["pricing_name"]}"
    return trading_pair


def is_pair_information_valid(pair_info: Dict[str, Any]) -> bool:
    """
    Verifies if a trading pair is enabled to operate with based on its market information

    :param pair_info: the market information for a trading pair

    :return: True if the trading pair is enabled, False otherwise
    """
    return pair_info["trading_name"] + pair_info["pricing_name"] == pair_info["name"]


class CoinexConfigMap(BaseConnectorConfigMap):
    connector: str = "coinex"
    coinex_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your CoinEx API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    coinex_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your CoinEx API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="coinex")


KEYS = CoinexConfigMap.model_construct()

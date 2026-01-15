from pydantic import ConfigDict, Field, SecretStr

from hummingbot.client.config.config_data_types import BaseConnectorConfigMap


class BacktestConfigMap(BaseConnectorConfigMap):
    connector: str = "backtest"
    backtest_api_key: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your BackTest API key",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    backtest_api_secret: SecretStr = Field(
        default=...,
        json_schema_extra={
            "prompt": "Enter your BackTest API secret",
            "is_secure": True,
            "is_connect_key": True,
            "prompt_on_new": True,
        }
    )
    model_config = ConfigDict(title="backtest")


KEYS = BacktestConfigMap.model_construct()

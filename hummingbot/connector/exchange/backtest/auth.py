from hummingbot.core.web_assistant.auth import AuthBase


class BacktestAuth(AuthBase):
    def __init__(self, api_key, secret_key, time_provider):
        self.api_key = api_key
        self.secret_key = secret_key
        self.time_provider = time_provider

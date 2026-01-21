from hummingbot.exceptions import HummingbotBaseException


class CommonError(HummingbotBaseException):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return '''
        message: %s''' % (
            self.message
        )

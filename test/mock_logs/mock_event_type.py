import re
from enum import Enum

PATTERNS = {}

class MOCK_EVENT_TYPE(Enum):
    UNKNOWN = 0,
    START_BEG = 10
    START_END = 20

    ORDR_NEW_ASK = 30
    ORDR_NEW_RSP = 40
    ORDR_CNL_ASK = 50
    ORDR_CNL_RSP = 60

    STOP_BEG = 70
    STOP_END = 80

    @classmethod
    def parse(cls, msg):
        type = MOCK_EVENT_TYPE.UNKNOWN
        m = None

        match msg:
            case str() if m := re.fullmatch(PATTERNS[MOCK_EVENT_TYPE.START_BEG], msg):
                type = MOCK_EVENT_TYPE.START_BEG
            case str() if m := re.fullmatch(PATTERNS[MOCK_EVENT_TYPE.START_END], msg):
                type = MOCK_EVENT_TYPE.START_END
                
            case str() if m := re.fullmatch(PATTERNS[MOCK_EVENT_TYPE.ORDR_NEW_ASK], msg):
                type = MOCK_EVENT_TYPE.ORDR_NEW_ASK
            case str() if m := re.fullmatch(PATTERNS[MOCK_EVENT_TYPE.ORDR_NEW_RSP], msg):
                type = MOCK_EVENT_TYPE.ORDR_NEW_RSP
            case str() if m := re.fullmatch(PATTERNS[MOCK_EVENT_TYPE.ORDR_CNL_ASK], msg):
                type = MOCK_EVENT_TYPE.ORDR_CNL_ASK
            case str() if m := re.fullmatch(PATTERNS[MOCK_EVENT_TYPE.ORDR_CNL_RSP], msg):
                type = MOCK_EVENT_TYPE.ORDR_CNL_RSP
                
            case str() if m := re.fullmatch(PATTERNS[MOCK_EVENT_TYPE.STOP_BEG], msg):
                type = MOCK_EVENT_TYPE.STOP_BEG
            case str() if m := re.fullmatch(PATTERNS[MOCK_EVENT_TYPE.STOP_END], msg):
                type = MOCK_EVENT_TYPE.STOP_END

        return type, m

PATTERNS = {
    MOCK_EVENT_TYPE.START_BEG:      r"Clock started successfully\n",
    MOCK_EVENT_TYPE.START_END:      r"Successfully connected to user stream\n",
    MOCK_EVENT_TYPE.STOP_BEG:       r"stop command initiated.\n",
    MOCK_EVENT_TYPE.STOP_END:       r"Strategy stopped successfully\n",
    MOCK_EVENT_TYPE.ORDR_NEW_ASK:   r"Created (?P<type>\w+) (?P<side>\w+) order (?P<order_id>.*) for .*\n",
    MOCK_EVENT_TYPE.ORDR_NEW_RSP:   r"{.*\"timestamp\": (?P<timestamp>[^,]*),.* \"type\": \"OrderType.(?P<type>[^\"]*)\".* \"order_id\": \"(?P<order_id>[^\"]*)\".* \"exchange_order_id\": \"(?P<exchange_id>[^\"]*)\".* \"event_name\": \"(?P<side>.*)OrderCreatedEvent\".*}\n",
    MOCK_EVENT_TYPE.ORDR_CNL_ASK:   r".* Canceling the (?P<type>.*) order (?P<order_id>[^.]*).*\n",
    MOCK_EVENT_TYPE.ORDR_CNL_RSP:   r"{.*\"timestamp\": (?P<timestamp>[^,]*),.* \"order_id\": \"(?P<order_id>[^\"]*)\".* \"exchange_order_id\": \"(?P<exchange_id>[^\"]*)\".* \"event_name\": \"OrderCancelledEvent\".*}\n",
}

import re

from datetime import datetime
from test.mock_logs.mock_event_type import MOCK_EVENT_TYPE
from test.mock_logs.mock_log_level import MOCK_LOG_LEVEL
from test.mock_logs.mock_order_side import MOCK_ORDER_SIDE
from test.mock_logs.mock_order_type import MOCK_ORDER_TYPE

class MockRecord:
    def __init__(self, gluphs):
        self.tid = int(gluphs[1])

        date_str = gluphs[0].split(" ")[0]
        time_str = gluphs[0].split(" ")[1]

        self.date = datetime.strptime(date_str, "%Y-%m-%d").date()
        self.time = datetime.strptime(time_str, "%H:%M:%S,%f").time()
        self.namespace = gluphs[2]
        self._log_level = MOCK_LOG_LEVEL[gluphs[3].upper()]
        msg = gluphs[4]
        self.order_id = None
        self.exc_order_id = None
        self._order_side = None

        [self._event_type, m] = MOCK_EVENT_TYPE.parse(msg)
        match self._event_type:
            case MOCK_EVENT_TYPE.ORDR_NEW_ASK:
                self.order_id = m.group("order_id")
                self._order_side = MOCK_ORDER_SIDE[m.group("side").upper()]
                self._order_type = MOCK_ORDER_TYPE[m.group("type").upper()]
            case MOCK_EVENT_TYPE.ORDR_NEW_RSP:
                self.order_id = m.group("order_id")
                self._order_side = MOCK_ORDER_SIDE[m.group("side").upper()]
                self._order_type = MOCK_ORDER_TYPE[m.group("type").upper()]
                self.exc_order_id = m.group("exchange_id")
                self.timestamp = float(m.group("timestamp"))

            case MOCK_EVENT_TYPE.ORDR_CNL_ASK:
                self.order_id = m.group("order_id")
            case MOCK_EVENT_TYPE.ORDR_CNL_RSP:
                self.order_id = m.group("order_id")
        self.message = msg

    def get_date(self):
        return datetime.combine(self.date, self.time)

    @property
    def log_level(self):
        if(self._log_level == None):
            return None
        log_level_str = str(self._log_level)
        point_idx = log_level_str.index('.')
        return log_level_str[point_idx + 1:]

    @property
    def event_type(self):
        if(self._event_type == None):
            return None
        event_type_str = str(self._event_type)
        point_idx = event_type_str.index('.')
        return event_type_str[point_idx + 1:]

    @property
    def order_side(self):
        if(self._order_side == None):
            return None
        order_side_str = str(self._order_side)
        point_idx = order_side_str.index('.')
        return order_side_str[point_idx + 1:]

    @property
    def order_type(self):
        if(self._order_type == None):
            return None
        order_type_str = str(self._order_type)
        point_idx = order_type_str.index('.')
        return order_type_str[point_idx + 1:]

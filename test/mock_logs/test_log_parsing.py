import asyncio
import unittest
from test.mock_logs.model.mock_record import MockRecord
from unittest import IsolatedAsyncioTestCase


class TestLogParsing(IsolatedAsyncioTestCase):
    MOCK_LOG_PATH = "test/mock_logs/logs_conf_v2_with_controllers_tst2.log"
    MOCK_LOG_LEN = 122

    @classmethod
    def setUpClass(cls):
        lines = None
        with open(cls.MOCK_LOG_PATH, "r") as file:
            lines = file.readlines()
        cls._records = [MockRecord(x.split(" - ")) for x in lines]

    @classmethod
    def tearDownClass(cls):
        cls._records = None

    def setUp(self):
        super().setUp()

    def tearDown(self):
        self._records = None

    def test_load(self):
        self.assertIsNotNone(self._records)
        self.assertEqual(self.MOCK_LOG_LEN, len(self._records))

    def test_parsing(self):
        self.assertIsNotNone(self._records)
        self.assertEqual(self.MOCK_LOG_LEN, len(self._records))

    async def test_events_async(self):
        result: bool = False
        duration = 0
        curr_date = None
        for item in self._records:
            item_date = item.get_date()
            if(curr_date != None):
                time_difference = item_date - curr_date
                sleep_duration_seconds = time_difference.total_seconds()
                duration += sleep_duration_seconds
                if(sleep_duration_seconds > 0):
                    await asyncio.sleep(sleep_duration_seconds)

            order_side = "" if item.order_side == None else item.order_side
            order_log = "" if item.order_id == None else f"  id:'{item.order_id}'"
            print(f"{duration:07.3f} - {item.log_level:>10}, {item.event_type:>10}{order_side:>6}{order_log}")
            curr_date = item_date

        result = True
        self.assertTrue(result)


if __name__ == '__main__':
    unittest.main()

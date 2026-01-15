import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from hummingbot.client.hummingbot_application import HummingbotApplication  # noqa: F401


class BacktestCommand:
    def backtest(self,  # type: HummingbotApplication
                 command: Optional[str] = None):
        if threading.current_thread() != threading.main_thread():
            self.ev_loop.call_soon_threadsafe(self.backtest, command)
            return

        self.app.clear_input()

        match command:
            case 'config':
                self.notify(f"\nBacktest config.")
            case 'start':
                self.notify(f"\nBacktest start.")
            case _:
                self.print_help()

    def print_help(self):
        self.notify(f"\nusage: {{ config, start }}")

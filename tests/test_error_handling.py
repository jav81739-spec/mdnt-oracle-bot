import unittest
from unittest.mock import AsyncMock, Mock, patch

from core.error_handling import handle_telegram_error, install_error_handler


class TelegramErrorHandlingTests(unittest.IsolatedAsyncioTestCase):
    async def test_install_error_handler_only_once(self):
        app = Mock()
        app._midnight_error_handler_installed = False
        install_error_handler(app)
        install_error_handler(app)
        self.assertEqual(app.add_error_handler.call_count, 1)

    async def test_handler_logs_without_replying(self):
        update = Mock(update_id=123)
        update.effective_chat.id = -1001
        update.effective_user.id = 42
        context = Mock(error=RuntimeError("boom"))
        with patch("core.error_handling.log.exception") as log_exception:
            await handle_telegram_error(update, context)
        log_exception.assert_called_once()


if __name__ == "__main__":
    unittest.main()

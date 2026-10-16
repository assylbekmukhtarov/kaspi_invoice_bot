from __future__ import annotations
import asyncio
import logging
import time

import aiohttp
from dotenv import load_dotenv

from .config import Settings
from .logging_conf import setup_logging

load_dotenv()
log = logging.getLogger("monitor")

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def check_once(session: aiohttp.ClientSession, url: str) -> tuple[bool, str]:
    try:
        async with session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True) as resp:
            if resp.status < 500:
                return True, f"HTTP {resp.status}"
            return False, f"HTTP {resp.status}"
    except asyncio.TimeoutError:
        return False, "таймаут запроса"
    except aiohttp.ClientError as e:
        return False, f"{type(e).__name__}: {e}"


async def send_telegram(session: aiohttp.ClientSession, bot_token: str, chat_id: str, text: str) -> None:
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        async with session.post(api_url, json={"chat_id": chat_id, "text": text}, timeout=REQUEST_TIMEOUT) as resp:
            if resp.status != 200:
                body = await resp.text()
                log.error("Не удалось отправить сообщение в Telegram: HTTP %s %s", resp.status, body)
    except aiohttp.ClientError as e:
        log.error("Ошибка отправки в Telegram: %s", e)


async def run() -> None:
    setup_logging()
    settings = Settings.from_env()

    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing in .env")
    if not settings.monitor_url:
        raise RuntimeError("MONITOR_URL is missing in .env")
    if not settings.monitor_chat_id:
        raise RuntimeError("MONITOR_CHAT_ID is missing in .env")

    url = settings.monitor_url
    ok_interval = settings.monitor_interval_seconds
    down_interval = settings.monitor_down_interval_seconds
    log.info("Мониторинг %s: каждые %s сек, при падении — каждые %s сек", url, ok_interval, down_interval)

    was_down = False
    down_since: float | None = None

    async with aiohttp.ClientSession() as session:
        while True:
            ok, detail = await check_once(session, url)
            now = time.strftime("%Y-%m-%d %H:%M:%S")

            if not ok:
                if not was_down:
                    down_since = time.time()
                    log.warning("%s недоступен: %s", url, detail)
                    await send_telegram(
                        session,
                        settings.bot_token,
                        settings.monitor_chat_id,
                        f"АгроскопПро упал\n{detail}\nВремя: {now}",
                    )
                else:
                    log.warning("%s всё ещё недоступен: %s", url, detail)
                was_down = True
            else:
                if was_down:
                    downtime_min = round((time.time() - (down_since or time.time())) / 60, 1)
                    log.info("%s снова доступен (%s)", url, detail)
                    await send_telegram(
                        session,
                        settings.bot_token,
                        settings.monitor_chat_id,
                        f"АгроскопПро снова доступен\n{detail}\nПростой: ~{downtime_min} мин\nВремя: {now}",
                    )
                else:
                    log.info("%s доступен: %s", url, detail)
                was_down = False
                down_since = None

            await asyncio.sleep(down_interval if was_down else ok_interval)


if __name__ == "__main__":
    asyncio.run(run())

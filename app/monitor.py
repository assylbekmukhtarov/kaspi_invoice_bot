from __future__ import annotations
import asyncio
import contextlib
import logging
import ssl
import time
from urllib.parse import urlsplit

import aiohttp
from dotenv import load_dotenv

from .config import Settings
from .logging_conf import setup_logging

load_dotenv()
log = logging.getLogger("monitor")

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)
TG_ATTEMPTS = 3
SSL_CHECK_INTERVAL = 24 * 60 * 60


async def check_once(session: aiohttp.ClientSession, url: str) -> tuple[bool, str]:
    try:
        async with session.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True) as resp:
            return resp.status < 500, f"HTTP {resp.status}"
    except asyncio.TimeoutError:
        return False, "таймаут запроса"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def ssl_days_left(host: str, port: int = 443) -> float:
    ctx = ssl.create_default_context()
    _, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port, ssl=ctx, server_hostname=host), timeout=10,
    )
    try:
        cert = writer.get_extra_info("peercert")
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()
    return (ssl.cert_time_to_seconds(cert["notAfter"]) - time.time()) / 86400


async def send_telegram(session: aiohttp.ClientSession, bot_token: str, chat_id: str, text: str) -> bool:
    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    for attempt in range(1, TG_ATTEMPTS + 1):
        try:
            async with session.post(api_url, json={"chat_id": chat_id, "text": text}, timeout=REQUEST_TIMEOUT) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                log.error("Telegram HTTP %s: %s", resp.status, body[:300])
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            log.error("Ошибка отправки в Telegram (попытка %s/%s): %s", attempt, TG_ATTEMPTS, type(e).__name__)
        await asyncio.sleep(5 * attempt)
    return False


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

    parts = urlsplit(url)
    ssl_host = parts.hostname if parts.scheme == "https" else None
    ssl_warn_days = settings.monitor_ssl_warn_days
    next_ssl_check = 0.0

    was_down = False
    down_since: float | None = None

    async with aiohttp.ClientSession() as session:
        while True:
            try:
                ok, detail = await check_once(session, url)
                now = time.strftime("%Y-%m-%d %H:%M:%S")

                if not ok:
                    if not was_down:
                        down_since = time.time()
                        log.warning("%s недоступен: %s", url, detail)
                        await send_telegram(
                            session, settings.bot_token, settings.monitor_chat_id,
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
                            session, settings.bot_token, settings.monitor_chat_id,
                            f"АгроскопПро снова доступен\n{detail}\nПростой: ~{downtime_min} мин\nВремя: {now}",
                        )
                    else:
                        log.info("%s доступен: %s", url, detail)
                    was_down = False
                    down_since = None
            except Exception:
                log.exception("Непредвиденная ошибка в цикле мониторинга")

            if ssl_host and time.time() >= next_ssl_check:
                try:
                    days_left = await ssl_days_left(ssl_host, parts.port or 443)
                    next_ssl_check = time.time() + SSL_CHECK_INTERVAL
                    if days_left < ssl_warn_days:
                        log.warning("SSL %s истекает через %.1f дн.", ssl_host, days_left)
                        await send_telegram(
                            session, settings.bot_token, settings.monitor_chat_id,
                            f"АгроскопПро: SSL-сертификат истекает через {int(days_left)} дн.",
                        )
                    else:
                        log.info("SSL %s: осталось %.1f дн.", ssl_host, days_left)
                except Exception as e:
                    # Не удалось проверить (сайт недоступен и т.п.) — повторим на следующей итерации
                    log.warning("Не удалось проверить SSL %s: %s: %s", ssl_host, type(e).__name__, e)

            await asyncio.sleep(down_interval if was_down else ok_interval)


if __name__ == "__main__":
    asyncio.run(run())
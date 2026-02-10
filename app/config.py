import os, re
from dataclasses import dataclass

A4_WIDTH_PT = 595.275590551  # 210 mm
A4_HEIGHT_PT = 841.88976378  # 297 mm

PT_PER_MM = 72 / 25.4
THERMAL_75x120 = (75 * PT_PER_MM, 120 * PT_PER_MM)
THERMAL_100x150 = (100 * PT_PER_MM, 150 * PT_PER_MM)

ORDER_ID_REGEX = re.compile(r"(\d{8,})")

@dataclass
class Settings:
    bot_token: str
    kaspi_enable: bool = False
    kaspi_login: str | None = None
    kaspi_password: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bot_token=os.getenv("BOT_TOKEN", ""),
            kaspi_enable=os.getenv("KASPI_ENABLE", "no").lower() in ("1","true","yes","y"),
            kaspi_login=os.getenv("KASPI_LOGIN") or None,
            kaspi_password=os.getenv("KASPI_PASSWORD") or None,
        )

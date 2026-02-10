from __future__ import annotations
# Клиент для загрузки накладных из кабинета продавца Kaspi (заготовка).
import json
from pathlib import Path
from typing import Sequence, List

class KaspiClient:
    def __init__(self, workdir: Path):
        self.workdir = workdir

    def download_invoices_by_ids(self, ids: Sequence[str]) -> List[Path]:
        """
        Заглушка: ожидает заранее помещённые <ID>.pdf в папку workdir.
        """
        out: List[Path] = []
        for i in ids:
            p = self.workdir / f"{i}.pdf"
            if p.exists():
                out.append(p)
        return out

    def download_by_date_range(self, date_from: str, date_to: str) -> List[Path]:
        """
        Заглушка: возвращает все *.pdf из workdir.
        """
        return list(self.workdir.glob("*.pdf"))

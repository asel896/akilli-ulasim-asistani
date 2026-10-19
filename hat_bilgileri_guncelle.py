import json
import os
from collections import Counter
from pathlib import Path

import psycopg
from dotenv import load_dotenv

klasor = Path(__file__).resolve().parent
load_dotenv(klasor / ".env")

sayilar = Counter()

try:
    with psycopg.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        client_encoding="UTF8",
        connect_timeout=10
    ) as baglanti:

        with baglanti.cursor() as imlec:
            dosyalar = sorted((klasor / "veriler").glob("*.json"))

            if not dosyalar:
                raise ValueError("JSON dosyası bulunamadı.")

            for dosya in dosyalar:
                with open(dosya, encoding="utf-8") as kaynak:
                    hat = json.load(kaynak)

                turler = set()

                for varyant in hat.get("variants", []):
                    baslik = varyant.get("title", "")
                    baslik = baslik.replace("İ", "I").upper()

                    if "GÖREVLİ" in baslik or "GÖREVLI" in baslik:
                        turler.add("gorevli")
                    elif "RING" in baslik:
                        turler.add("ring")
                    else:
                        turler.add("belirsiz")

                hizmet_turu = "belirsiz"

                if len(turler) == 1:
                    hizmet_turu = next(iter(turler))

                imlec.execute(
                    """
                    UPDATE hatlar
                    SET kaynak_aktif = %s,
                        kaynak_kategori = %s,
                        hizmet_turu = %s
                    WHERE hat_kodu = %s
                    """,
                    (
                        hat.get("isActive"),
                        hat.get("category"),
                        hizmet_turu,
                        hat["code"]
                    )
                )

                if imlec.rowcount != 1:
                    raise ValueError(
                        f"Hat veritabanında bulunamadı: {hat['code']}"
                    )

                sayilar[hizmet_turu] += 1

    print("Güncelleme kaydedildi.")

    for tur, sayi in sorted(sayilar.items()):
        print(f"{tur}: {sayi}")

except (psycopg.Error, OSError, ValueError, KeyError, TypeError) as hata:
    print("Güncelleme tamamlanamadı; değişiklikler geri alındı.")
    print("Hata:", hata)
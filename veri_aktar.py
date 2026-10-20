from db import baglanti_ac
import json
import os
import traceback
from pathlib import Path

import psycopg
from dotenv import load_dotenv

load_dotenv()

klasor = Path(__file__).resolve().parent / "veriler"
dosyalar = sorted(klasor.glob("*.json"))

if not dosyalar:
    raise SystemExit("veriler klasöründe JSON dosyası bulunamadı.")

try:
    with baglanti_ac() as baglanti:

        with baglanti.cursor() as imlec:
            for dosya in dosyalar:
                with open(dosya, encoding="utf-8") as kaynak:
                    hat = json.load(kaynak)

                hat_kodu = hat["code"]

                imlec.execute(
                    """
                    INSERT INTO hatlar (hat_kodu, hat_adi, slug)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (hat_kodu) DO NOTHING
                    """,
                    (hat_kodu, hat["name"], hat["slug"])
                )

                # %s değerleri SQL komutuna güvenli biçimde gönderir

                yonler = [
                    ("gidis", "departureStops"),
                    ("donus", "arrivalStops")
                ]

                for yon, alan in yonler:
                    for sira, durak in enumerate(hat[alan], start=1):
                        durak_kodu = str(durak["id"])

                        imlec.execute(
                            """
                            INSERT INTO duraklar
                                (durak_kodu, durak_adi, enlem, boylam)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (durak_kodu) DO NOTHING
                            """,
                            (
                                durak_kodu,
                                durak["name"],
                                durak["latitude"],
                                durak["longitude"]
                            )
                        )

                        imlec.execute(
                            """
                            INSERT INTO hat_duraklar
                                (hat_kodu, yon, sira, durak_kodu)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (hat_kodu, yon, sira)
                            DO NOTHING
                            """,
                            (hat_kodu, yon, sira, durak_kodu)
                        )

                print("İşlendi:", hat_kodu)

            for tablo in ["hatlar", "duraklar", "hat_duraklar"]:
                sorgu = psycopg.sql.SQL(
                    "SELECT COUNT(*) FROM {}"
                ).format(psycopg.sql.Identifier(tablo))

                imlec.execute(sorgu)
                print(f"{tablo}: {imlec.fetchone()[0]}")

    print("Aktarım tamamlandı ve veritabanına kaydedildi.")

except (psycopg.Error, OSError, ValueError, KeyError, TypeError):
    traceback.print_exc()
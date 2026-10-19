import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

klasor = Path(__file__).resolve().parent
load_dotenv(klasor / ".env")

try:
    dosyalar = sorted((klasor / "veriler").glob("*.json"))

    if not dosyalar:
        raise ValueError("JSON dosyası bulunamadı.")

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
            for dosya in dosyalar:
                with open(dosya, encoding="utf-8") as kaynak:
                    hat = json.load(kaynak)

                for varyant in hat.get("variants", []):
                    guzergah_id = varyant["id"]

                    imlec.execute(
                        """
                        INSERT INTO guzergahlar (
                            guzergah_id, hat_kodu, kaynak_kodu,
                            baslik, kaynak_yon, ana_guzergah,
                            sure_dakika, uzunluk_km
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (guzergah_id) DO NOTHING
                        """,
                        (
                            guzergah_id,
                            hat["code"],
                            varyant.get("code"),
                            varyant.get("title"),
                            varyant["direction"],
                            varyant.get("is_primary"),
                            varyant.get("duration_minutes"),
                            varyant.get("length_km")
                        )
                    )

                    # ayni kaynak kimliginin baska hatta ait olmadigini kontrol et
                    imlec.execute(
                        """
                        SELECT hat_kodu
                        FROM guzergahlar
                        WHERE guzergah_id = %s
                        """,
                        (guzergah_id,)
                    )

                    if imlec.fetchone()[0] != hat["code"]:
                        raise ValueError(
                            f"Güzergâh kimliği farklı hatlarda kullanılmış: "
                            f"{guzergah_id}"
                        )

                    kullanilan_siralar = set()

                    for nokta in varyant.get("coordinates", []):
                        sira = nokta["sequence"]

                        if sira in kullanilan_siralar:
                            raise ValueError(
                                f"Tekrarlanan sıra: güzergâh "
                                f"{guzergah_id}, sıra {sira}"
                            )

                        kullanilan_siralar.add(sira)

                        imlec.execute(
                            """
                            INSERT INTO guzergah_noktalari (
                                guzergah_id, sira, enlem, boylam
                            )
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (guzergah_id, sira) DO NOTHING
                            """,
                            (
                                guzergah_id,
                                sira,
                                nokta["latitude"],
                                nokta["longitude"]
                            )
                        )

                print("İşlendi:", hat["code"])

            imlec.execute("SELECT COUNT(*) FROM guzergahlar")
            print("Güzergâh sayısı:", imlec.fetchone()[0])

            imlec.execute("SELECT COUNT(*) FROM guzergah_noktalari")
            print("Güzergâh noktası sayısı:", imlec.fetchone()[0])

    print("Güzergâh aktarımı kaydedildi.")

except (psycopg.Error, OSError, ValueError, KeyError, TypeError) as hata:
    print("Aktarım tamamlanamadı; değişiklikler geri alındı.")
    print("Hata:", hata)
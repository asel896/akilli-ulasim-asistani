# kaynak dosyalarla vt arasindaki farklari kontrol et
from db import baglanti_ac
import json
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv

klasor = Path(__file__).resolve().parent
load_dotenv(klasor / ".env")

beklenen_guzergahlar = set()
beklenen_noktalar = {}

for dosya in sorted((klasor / "veriler").glob("*.json")):
    with open(dosya, encoding="utf-8") as kaynak:
        hat = json.load(kaynak)

    for varyant in hat.get("variants", []):
        guzergah_id = varyant["id"]
        beklenen_guzergahlar.add(guzergah_id)

        for nokta in varyant.get("coordinates", []):
            anahtar = (guzergah_id, nokta["sequence"])
            beklenen_noktalar[anahtar] = (
                nokta["latitude"],
                nokta["longitude"]
            )

with baglanti_ac() as baglanti:

    with baglanti.cursor() as imlec:
        imlec.execute("SELECT guzergah_id FROM guzergahlar")
        mevcut_guzergahlar = {satir[0] for satir in imlec.fetchall()}

        imlec.execute(
            """
            SELECT guzergah_id, sira, enlem, boylam
            FROM guzergah_noktalari
            """
        )

        mevcut_noktalar = {}

        for guzergah_id, sira, enlem, boylam in imlec.fetchall():
            mevcut_noktalar[(guzergah_id, sira)] = (enlem, boylam)

eksik = beklenen_noktalar.keys() - mevcut_noktalar.keys()
fazla = mevcut_noktalar.keys() - beklenen_noktalar.keys()

farkli_koordinat = 0

for anahtar in beklenen_noktalar.keys() & mevcut_noktalar.keys():
    kaynak = beklenen_noktalar[anahtar]
    mevcut = mevcut_noktalar[anahtar]

    if (
        abs(kaynak[0] - mevcut[0]) > 0.000000001
        or abs(kaynak[1] - mevcut[1]) > 0.000000001
    ):
        farkli_koordinat += 1

print("Kaynak güzergâh sayısı:", len(beklenen_guzergahlar))
print("Veritabanı güzergâh sayısı:", len(mevcut_guzergahlar))
print(
    "Eksik güzergâh:",
    len(beklenen_guzergahlar - mevcut_guzergahlar)
)
print(
    "Fazla güzergâh:",
    len(mevcut_guzergahlar - beklenen_guzergahlar)
)
print("Kaynak nokta sayısı:", len(beklenen_noktalar))
print("Veritabanı nokta sayısı:", len(mevcut_noktalar))
print("Eksik nokta:", len(eksik))
print("Fazla nokta:", len(fazla))
print("Koordinatı farklı nokta:", farkli_koordinat)
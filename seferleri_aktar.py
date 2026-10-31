import json
from pathlib import Path

from db import baglanti_ac


proje_klasoru = Path(__file__).resolve().parent
veri_klasoru = proje_klasoru / "veriler"

yon_eslestirmesi = {
    "departure": "gidis",
    "arrival": "donus",
}

aktarilacak_seferler = []
okunan_dosya_sayisi = 0

for dosya_yolu in sorted(veri_klasoru.glob("*.json")):
    with dosya_yolu.open("r", encoding="utf-8") as dosya:
        hat_verisi = json.load(dosya)

    hat_kodu = str(hat_verisi.get("code", "")).strip()
    if not hat_kodu:
        continue

    okunan_dosya_sayisi += 1

    for cizelge in hat_verisi.get("schedules", []):
        gun = cizelge.get("day")

        if not gun:
            continue

        for json_yon, veritabani_yonu in yon_eslestirmesi.items():
            for sefer in cizelge.get(json_yon, []):
                saat = sefer.get("time")

                if not saat:
                    continue

                aciklama = sefer.get("note") or ""

                aktarilacak_seferler.append(
                    (hat_kodu, gun, veritabani_yonu, saat, aciklama)
                )


if not aktarilacak_seferler:
    print("JSON dosyalarında aktarılacak sefer saati bulunamadı.")
else:
    with baglanti_ac() as baglanti:
        with baglanti.cursor() as imlec:
            imlec.executemany(
                """
                INSERT INTO sefer_saatleri
                    (hat_kodu, gun, yon, saat, aciklama)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (hat_kodu, gun, yon, saat, aciklama)
                DO NOTHING
                """,
                aktarilacak_seferler
            )

        toplam = baglanti.execute(
            "SELECT COUNT(*) FROM sefer_saatleri"
        ).fetchone()[0]

        hat_sayisi = baglanti.execute(
            "SELECT COUNT(DISTINCT hat_kodu) FROM sefer_saatleri"
        ).fetchone()[0]

        yon_dagilimi = baglanti.execute(
            """
            SELECT yon, COUNT(*)
            FROM sefer_saatleri
            GROUP BY yon
            ORDER BY yon
            """
        ).fetchall()

    print(f"Okunan JSON dosyası: {okunan_dosya_sayisi}")
    print(f"JSON'lardan bulunan sefer kaydı: {len(aktarilacak_seferler)}")
    print(f"Veritabanındaki toplam sefer kaydı: {toplam}")
    print(f"Sefer saati bulunan hat sayısı: {hat_sayisi}")
    print("Yön dağılımı:")

    for yon, sayi in yon_dagilimi:
        print(f"- {yon}: {sayi}")
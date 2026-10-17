import json
import math
from pathlib import Path

klasor = Path("veriler")
dosyalar = sorted(klasor.glob("*.json"))

okunan_hat = 0
toplam_durak_kaydi = 0
benzersiz_duraklar = set()
uyarilar = []


def koordinat_gecerli(enlem, boylam):
    if isinstance(enlem, bool) or isinstance(boylam, bool):
        return False

    if not isinstance(enlem, (int, float)):
        return False

    if not isinstance(boylam, (int, float)):
        return False

    return (
        math.isfinite(enlem)
        and math.isfinite(boylam)
        and -90 <= enlem <= 90
        and -180 <= boylam <= 180
        and (enlem, boylam) != (0, 0)
    )


for dosya in dosyalar:
    try:
        with open(dosya, encoding="utf-8") as kaynak:
            hat = json.load(kaynak)

        if not isinstance(hat, dict):
            uyarilar.append(f"{dosya.name}: Hat verisi sözlük değil.")
            continue

        okunan_hat += 1
        hat_kodu = hat.get("code", dosya.stem)

        for alan in ["departureStops", "arrivalStops"]:
            duraklar = hat.get(alan)

            if not isinstance(duraklar, list):
                uyarilar.append(f"{hat_kodu}: {alan} alanı eksik veya hatalı.")
                continue

            if not duraklar:
                uyarilar.append(f"{hat_kodu}: {alan} listesi boş.")

            for sira, durak in enumerate(duraklar, start=1):
                toplam_durak_kaydi += 1

                if not isinstance(durak, dict):
                    uyarilar.append(
                        f"{hat_kodu}: {alan}, sıra {sira}: Hatalı durak."
                    )
                    continue

                kod = durak.get("id")
                ad = durak.get("name")

                if kod is None or not str(kod).strip():
                    uyarilar.append(
                        f"{hat_kodu}: {alan}, sıra {sira}: Durak kodu eksik."
                    )
                else:
                    benzersiz_duraklar.add(str(kod))

                if not isinstance(ad, str) or not ad.strip():
                    uyarilar.append(
                        f"{hat_kodu}: {alan}, sıra {sira}: Durak adı eksik."
                    )

                if not koordinat_gecerli(
                    durak.get("latitude"),
                    durak.get("longitude")
                ):
                    uyarilar.append(
                        f"{hat_kodu}: {alan}, durak {kod}: "
                        "Koordinat eksik veya geçersiz."
                    )

    except (OSError, ValueError) as hata:
        uyarilar.append(f"{dosya.name}: Dosya okunamadı: {hata}")

print("JSON dosyası:", len(dosyalar))
print("Okunan hat:", okunan_hat)
print("Toplam durak kaydı:", toplam_durak_kaydi)
print("Benzersiz durak kodu:", len(benzersiz_duraklar))
print("Uyarı sayısı:", len(uyarilar))

for uyari in uyarilar:
    print("-", uyari)
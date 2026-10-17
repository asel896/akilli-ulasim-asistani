import json
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup


def hat_bul(veri, slug):
    if isinstance(veri, dict):
        if veri.get("slug") == slug and "departureStops" in veri:
            return veri

        for deger in veri.values():
            sonuc = hat_bul(deger, slug)

            if sonuc is not None:
                return sonuc

    elif isinstance(veri, list):
        for eleman in veri:
            sonuc = hat_bul(eleman, slug)

            if sonuc is not None:
                return sonuc

    return None


def sayfadan_hat_oku(html, slug):
    sayfa = BeautifulSoup(html, "html.parser")
    veri_metni = ""

    for script in sayfa.find_all("script"):
        icerik = script.get_text()
        baslangic = "self.__next_f.push("

        if icerik.startswith(baslangic) and icerik.endswith(")"):
            parca = json.loads(icerik[len(baslangic):-1])

            if parca[0] == 1 and isinstance(parca[1], str):
                veri_metni += parca[1]

    for satir in veri_metni.splitlines():
        if ":" not in satir:
            continue

        try:
            veri = json.loads(satir.split(":", 1)[1])
        except json.JSONDecodeError:
            continue

        hat = hat_bul(veri, slug)

        if hat is not None:
            return hat

    return None


with open("hat_adresleri.json", encoding="utf-8") as dosya:
    adresler = json.load(dosya)

Path("veriler").mkdir(exist_ok=True)

# listedeki tum hatlar
for adres in adresler:
    slug = adres.rstrip("/").split("/")[-1]

    print("\nOkunuyor:", slug)

    try:
        cevap = requests.get(adres, timeout=30)
        cevap.raise_for_status()

        hat = sayfadan_hat_oku(cevap.content, slug)

        if hat is None:
            print("HAT VERİSİ BULUNAMADI.")
        else:
            dosya_yolu = Path("veriler") / f"{slug}.json"

            with open(dosya_yolu, "w", encoding="utf-8") as dosya:
                json.dump(hat, dosya, ensure_ascii=False, indent=4)

            print("Hat:", hat["code"])
            print("Gidiş durak sayısı:", len(hat["departureStops"]))
            print("Dönüş durak sayısı:", len(hat["arrivalStops"]))
            print("Dosyaya kaydedildi.")

    except (requests.RequestException, ValueError, KeyError,
            IndexError, TypeError) as hata:
        print("HATA:", hata)

    time.sleep(2)
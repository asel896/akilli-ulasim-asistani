import json
import requests
from bs4 import BeautifulSoup


# İç içe veriler arasında 2A hattını arıyoruz.
def hat_bul(veri):
    if isinstance(veri, dict):
        if veri.get("code") == "2A" and veri.get("departureStops"):
            return veri

        for deger in veri.values():
            sonuc = hat_bul(deger)

            if sonuc is not None:
                return sonuc

    elif isinstance(veri, list):
        for eleman in veri:
            sonuc = hat_bul(eleman)

            if sonuc is not None:
                return sonuc

    return None


url = "https://motas.com.tr/ulasim/hatlar/2a-maliye-mbb-masti-2osb-inonu-myo"

try:
    cevap = requests.get(url, timeout=30)
    cevap.raise_for_status()

    sayfa = BeautifulSoup(cevap.content, "html.parser")

    # Sayfanın veri parçalarını birleştiriyoruz.
    veri_metni = ""

    for script in sayfa.find_all("script"):
        icerik = script.get_text()
        baslangic = "self.__next_f.push("

        if icerik.startswith(baslangic) and icerik.endswith(")"):
            json_metni = icerik[len(baslangic):-1]
            parca = json.loads(json_metni)

            if parca[0] == 1 and isinstance(parca[1], str):
                veri_metni += parca[1]

    hat = None

    for satir in veri_metni.splitlines():
        if ":" not in satir:
            continue

        json_metni = satir.split(":", 1)[1]

        try:
            veri = json.loads(json_metni)
        except json.JSONDecodeError:
            continue

        hat = hat_bul(veri)

        if hat is not None:
            break

    if hat is None:
        print("Hat verisi bulunamadı.")

    else:
        with open("hat_2A.json", "w", encoding="utf-8") as dosya:
            json.dump(hat, dosya, ensure_ascii=False, indent=4)

        print("Hat verileri hat_2A.json dosyasına kaydedildi.")
        print("Hat:", hat["code"])



        yonler = [
            ("GİDİŞ", "departureStops"),
            ("DÖNÜŞ", "arrivalStops")
        ]

        for yon_adi, alan in yonler:
            duraklar = hat[alan]

            print(f"\n{yon_adi}: {len(duraklar)} durak")

            for sira, durak in enumerate(duraklar, start=1):
                print(
                    f"{sira}. {durak['name']} | "
                    f"Enlem: {durak['latitude']} | "
                    f"Boylam: {durak['longitude']}"
                )

except requests.RequestException as hata:
    print("Sayfaya erişilemedi:", hata)

except (json.JSONDecodeError, KeyError, IndexError, TypeError) as hata:
    print("Sayfanın veri yapısı okunamadı:", hata)
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

url = "https://motas.com.tr/ulasim/hatlar"

try:
    cevap = requests.get(url, timeout=30)
    cevap.raise_for_status()

    sayfa = BeautifulSoup(cevap.content, "html.parser")

    baglantilar = sayfa.select('a[href^="/ulasim/hatlar/"]')

    hat_adresleri = []

    for baglanti in baglantilar:
        adres = urljoin(url, baglanti["href"])

        if adres not in hat_adresleri:
            hat_adresleri.append(adres)


        with open("hat_adresleri.json", "w", encoding="utf-8") as dosya:
            import json
            json.dump(hat_adresleri, dosya, ensure_ascii=False, indent=4)

    print("Bulunan farklı hat bağlantısı:", len(hat_adresleri))

    for sira, adres in enumerate(hat_adresleri, start=1):
        print(f"{sira}. {adres}")

except requests.RequestException as hata:
    print("Hat listesi alınamadı:", hata)
import json
from collections import Counter
from pathlib import Path

klasor = Path(__file__).resolve().parent
dosyalar = sorted((klasor / "veriler").glob("*.json"))

# 124 hattin kategori ve aktiflik bilgileri
aktiflik_sayilari = Counter()
kategori_sayilari = Counter()
kaydedilen_adresler = set()

for dosya in dosyalar:
    with open(dosya, encoding="utf-8") as kaynak:
        hat = json.load(kaynak)

    aktiflik = hat.get("isActive")
    kategori = hat.get("category")

    aktiflik_sayilari[str(aktiflik)] += 1

    
    kategori_metni = json.dumps(kategori, ensure_ascii=False)
    kategori_sayilari[kategori_metni] += 1

    slug = hat.get("slug")

    if slug:
        kaydedilen_adresler.add(
            "https://motas.com.tr/ulasim/hatlar/" + slug
        )

    print(
        f"Hat: {hat.get('code')} | "
        f"Aktif: {aktiflik} | "
        f"Kategori: {kategori_metni}"
    )

with open(klasor / "hat_adresleri.json", encoding="utf-8") as kaynak:
    beklenen_adresler = {
        adres.rstrip("/") for adres in json.load(kaynak)
    }

eksikler = beklenen_adresler - kaydedilen_adresler

print("\n--- ÖZET ---")
print("Listedeki farklı bağlantı:", len(beklenen_adresler))
print("JSON dosyası:", len(dosyalar))
print("Dosyası bulunamayan bağlantı:", len(eksikler))

print("\nAktiflik dağılımı:")
for durum, sayi in aktiflik_sayilari.items():
    print(durum, ":", sayi)

print("\nKategori dağılımı:")
for kategori, sayi in kategori_sayilari.items():
    print(kategori, ":", sayi)

for adres in sorted(eksikler):
    print("Eksik:", adres)
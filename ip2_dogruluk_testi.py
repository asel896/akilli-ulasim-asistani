from adres_coz import adresleri_coz, durak_ara


TESTLER = [
    (
        "Maliye'den MAŞTİ'ye nasıl giderim?",
        {"10001", "10362"},
        {"10012", "10158", "12216", "14209"},
    ),
    (
        "Malie den Masti'ye nasıl gidebilirim?",
        {"10001", "10362"},
        {"10012", "10158", "12216", "14209"},
    ),
    (
        "Fethiye'den İnönü Üniversitesi OSB MYO'ya nasıl giderim?",
        {str(kod) for kod in range(10079, 10089)},
        {"12502", "12503"},
    ),
    (
        "Fetiye'den OSB MYO'ya nasıl gidebilirim?",
        {str(kod) for kod in range(10079, 10089)},
        {"12502", "12503"},
    ),
    (
        "MAŞTİ'den Kolejler durağına nasıl giderim?",
        {"10012", "10158", "12216", "14209"},
        {"10016", "10154"},
    ),
    (
        "Kolejler'den Maliye'ye nasıl gidebilirim?",
        {"10016", "10154"},
        {"10001", "10362"},
    ),
    (
        "Malatya Büyükşehir Belediyesi'nden MAŞTİ'ye gitmek istiyorum.",
        {"10004", "10166"},
        {"10012", "10158", "12216", "14209"},
    ),
    (
        "Fahri Kayahan'dan MAŞTİ Otogar'a nasıl ulaşırım?",
        {"10011", "10159"},
        {"10012", "10158", "12216", "14209"},
    ),
    (
        "PTT'den İnönü Üniversitesi OSB MYO'ya nasıl giderim?",
        {"11309"},
        {"12502", "12503"},
    ),
    (
        "İşkur'dan Bostanbaşı Kavşağı'na nasıl gidebilirim?",
        {"10008", "10162"},
        {"10015", "10155"},
    ),
]


dogru_eslesme = 0
toplam_eslesme = len(TESTLER) * 2

for sira, (cumle, beklenen_baslangic, beklenen_hedef) in enumerate(
    TESTLER,
    start=1,
):
    print(f"\nTest {sira}: {cumle}")

    try:
        adresler = adresleri_coz(cumle)

        baslangic_yeri = adresler.get("baslangic")
        hedef_yeri = adresler.get("hedef")

        bulunan_baslangic = {
            str(durak[0])
            for durak in durak_ara(baslangic_yeri)
        } if baslangic_yeri else set()

        bulunan_hedef = {
            str(durak[0])
            for durak in durak_ara(hedef_yeri)
        } if hedef_yeri else set()

        baslangic_dogru = bool(
            bulunan_baslangic & beklenen_baslangic
        )
        hedef_dogru = bool(
            bulunan_hedef & beklenen_hedef
        )

        if baslangic_dogru:
            dogru_eslesme += 1

        if hedef_dogru:
            dogru_eslesme += 1

        print(f"  Anlaşılan başlangıç: {baslangic_yeri}")
        print(
            "  Başlangıç eşleşmesi:",
            "DOĞRU" if baslangic_dogru else "YANLIŞ",
        )
        print(
            "  Bulunan başlangıç durak kodları:",
            sorted(bulunan_baslangic),
        )

        print(f"  Anlaşılan hedef: {hedef_yeri}")
        print(
            "  Hedef eşleşmesi:",
            "DOĞRU" if hedef_dogru else "YANLIŞ",
        )
        print(
            "  Bulunan hedef durak kodları:",
            sorted(bulunan_hedef),
        )

    except Exception as hata:
        print(f"  Bu testte hata oluştu: {type(hata).__name__}: {hata}")
        print("  Başlangıç ve hedef eşleşmesi başarısız sayıldı.")


yuzde = dogru_eslesme / toplam_eslesme * 100

print("\n--- TEST SONUCU ---")
print(f"Doğru eşleşme: {dogru_eslesme}/{toplam_eslesme}")
print(f"Doğruluk oranı: %{yuzde:.1f}")

if yuzde >= 85:
    print("Sonuç: Bu test setinde %85 başarı ölçütü karşılandı.")
else:
    print("Sonuç: Bu test setinde %85 başarı ölçütü karşılanmadı.")
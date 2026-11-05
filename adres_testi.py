import argparse
import hashlib
import json
import re
import time
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path

import requests


KLASOR = Path(__file__).resolve().parent
ALTIN_DOSYA = KLASOR / "adres_testi_beklentiler.json"


# Beklenen yerler, API sonuçları görülmeden tanımlanmıştır.
# Aynı tam ada sahip farklı durak kodlarının tamamı kabul edilir.
DURAK_ADLARI = {
    "stadyum": "STADYUM",
    "villakent": "VİLLAKENT BULGURLU",
    "erkek_yurdu": "BATTALGAZİ ERKEK YURDU",
    "toki": "BAHÇEBAŞI TOKİ",
    "polis_evi": "POLİS EVİ",
    "orduzu": "ORDUZU PINARBAŞI",
    "mismis": "MİŞMİŞ PARK FUAR ALANI",
    "seyrantepe": "SEYRANTEPE",
    "anadolu_lisesi": "MALATYA ANADOLU LİSESİ",
    "yildiztepe": "YILDIZTEPE",
    "yusuf1": "YUSUF ÖZAL CAD. 1",
    "yusuf2": "YUSUF ÖZAL CAD. 2",
    "yusuf3": "YUSUF ÖZAL CAD. 3",
    "yusuf4": "YUSUF ÖZAL CAD. 4",
    "inderesi": "İNDERESİ 1",
    "yusuf5": "YUSUF ÖZAL CAD. 5",
    "yusuf6": "YUSUF ÖZAL CAD. 6",
    "kanal1": "KANALBOYU CAD. 1",
    "kanal2": "KANALBOYU CAD. 2",
    "kanal3": "KANALBOYU CAD. 3",
    "aspuzu1": "ASPUZU CAD. 1",
    "aspuzu2": "ASPUZU CAD. 2",
    "aspuzu3": "ASPUZU CAD. 3",
    "aspuzu4": "ASPUZU CAD. 4",
    "mezarlik": "KUYU ÖNÜ MEZARLIK",
    "itfaiye": "KUYU ÖNÜ İTFAİYE",
    "ibnisina": "İBN-İ SİNA İLKOKULU",
    "saat": "SAAT KULESİ",
    "yazihan1": "YAZIHAN 1",
    "yazihan10": "YAZIHAN 10",
    "yazihan11": "YAZIHAN 11",
    "yazihan2": "YAZIHAN 2",
    "yazihan3": "YAZIHAN 3",
    "yazihan4": "YAZIHAN 4",
    "govuk": "GÖVÜK YOL AYRIMI",
    "tohma1": "TOHMA KÖPRÜSÜ 1",
    "tohma2": "TOHMA KÖPRÜSÜ 2",
    "teias": "TEİAŞ TRAFO",
    "demokrasi": "DEMOKRASİ CAD.",
    "drijan": "DRİJAN BULVARI",
    "jandarma": "YAZIHAN İLÇE JANDARMA",
}


KISALTMALAR = [
    ("yusuf3", "Yusuf Özal Cd. 3", "itfaiye"),
    ("kanal2", "Kanalboyu Cd. 2", "saat"),
    ("aspuzu4", "Aspuzu Cd. 4", "mezarlik"),
    ("ibnisina", "İbn-i Sina İlkok.", "govuk"),
    ("mismis", "Mişmiş Pk. Fuar Alanı", "polis_evi"),
    ("anadolu_lisesi", "Malatya Anadolu Lis.", "yusuf1"),
    ("erkek_yurdu", "Battalgazi Erkek Yrd.", "tohma1"),
    ("orduzu", "Orduzu Pınarb.", "demokrasi"),
    ("jandarma", "Yazıhan İlçe Jand.", "kanal3"),
    ("teias", "TEİAŞ Trafo", "yusuf5"),
]


YAZIM_HATALARI = [
    ("stadyum", "Stadyom", "yildiztepe"),
    ("villakent", "Vılakent Bulgurlu", "polis_evi"),
    ("seyrantepe", "Seyranteppe", "itfaiye"),
    ("mismis", "Mismis Park Fuar Alni", "mezarlik"),
    ("anadolu_lisesi", "Malatya Anadlu Lisesi", "saat"),
    ("demokrasi", "Demokrasi Caddessi", "teias"),
    ("jandarma", "Yazihan Ilce Jandamra", "drijan"),
    ("ibnisina", "Ibni Sina Ilkoklu", "govuk"),
    ("orduzu", "Orduzu Pinarbasi", "tohma1"),
    ("kanal2", "Kanalbyu Caddesi 2", "aspuzu4"),
]


BENZER_ADLAR = [
    ("yusuf1", "yusuf2"),
    ("yusuf2", "yusuf1"),
    ("yusuf3", "yusuf4"),
    ("yusuf4", "yusuf3"),
    ("yusuf5", "yusuf6"),
    ("yusuf6", "yusuf5"),
    ("kanal1", "kanal2"),
    ("kanal2", "kanal3"),
    ("kanal3", "kanal1"),
    ("aspuzu1", "aspuzu2"),
    ("aspuzu2", "aspuzu3"),
    ("aspuzu3", "aspuzu4"),
    ("aspuzu4", "aspuzu1"),
    ("mezarlik", "itfaiye"),
    ("itfaiye", "mezarlik"),
    ("yazihan1", "yazihan10"),
    ("yazihan10", "yazihan11"),
    ("yazihan11", "yazihan1"),
    ("tohma1", "tohma2"),
    ("tohma2", "tohma1"),
]


KALIPLAR = [
    "{a} durağından {b} durağına nasıl giderim?",
    "Başlangıcım {a}, hedefim {b}. Nasıl ulaşırım?",
    "{a} konumundan çıkacağım, {b} konumuna gitmek istiyorum.",
    "Nereden: {a}. Nereye: {b}. Yol tarifi istiyorum.",
    "{b} durağına ulaşmak istiyorum; şu an {a} durağındayım.",
]


def normalize(metin):
    metin = str(metin).casefold().replace("ı", "i")
    metin = unicodedata.normalize("NFKD", metin)
    metin = "".join(
        karakter
        for karakter in metin
        if not unicodedata.combining(karakter)
    )
    return re.sub(r"[^a-z0-9]+", " ", metin).strip()


def durak_adini_temizle(metin):
    metin = re.sub(r"^\s*\d+\s*-\s*", "", metin)
    return normalize(metin)


def ascii_yap(metin):
    metin = metin.replace("ı", "i").replace("İ", "I")
    metin = unicodedata.normalize("NFKD", metin)
    return "".join(
        karakter
        for karakter in metin
        if not unicodedata.combining(karakter)
    ).lower()


def gorunen_ad(anahtar):
    return DURAK_ADLARI[anahtar].replace("CAD.", "CADDESİ")


def dosyaya_yaz(yol, veri):
    yol.write_text(
        json.dumps(veri, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def ozet_degeri(veri):
    metin = json.dumps(
        veri,
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()


def beklenen_durak(anahtar):
    return {"tur": "durak", "yer": anahtar}


def testleri_olustur():
    testler = []
    anahtarlar = list(DURAK_ADLARI)

    def ekle(kategori, soru, baslangic, hedef):
        testler.append(
            {
                "id": f"T{len(testler) + 1:03}",
                "kategori": kategori,
                "soru": soru,
                "baslangic": baslangic,
                "hedef": hedef,
            }
        )

    # 10 normal sorgu.
    for i in range(10):
        a = anahtarlar[i + 10]
        b = anahtarlar[(i + 23) % len(anahtarlar)]
        soru = KALIPLAR[i % len(KALIPLAR)].format(
            a=gorunen_ad(a),
            b=gorunen_ad(b),
        )
        ekle("normal", soru, beklenen_durak(a), beklenen_durak(b))

    # 10 kısaltmalı sorgu.
    for a, kisa_ad, b in KISALTMALAR:
        soru = (
            f"{kisa_ad} durağından "
            f"{gorunen_ad(b)} durağına nasıl gidebilirim?"
        )
        ekle("kisaltma", soru, beklenen_durak(a), beklenen_durak(b))

    # 20 Türkçe karaktersiz sorgu.
    for i in range(20):
        a = anahtarlar[(i + 19) % len(anahtarlar)]
        b = anahtarlar[(i + 7) % len(anahtarlar)]
        soru = KALIPLAR[(i + 2) % len(KALIPLAR)].format(
            a=gorunen_ad(a),
            b=gorunen_ad(b),
        )
        ekle(
            "turkce_karaktersiz",
            ascii_yap(soru),
            beklenen_durak(a),
            beklenen_durak(b),
        )

    # 10 yazım hatalı sorgu.
    for a, hatali_ad, b in YAZIM_HATALARI:
        soru = (
            f"{hatali_ad} duragindan "
            f"{ascii_yap(gorunen_ad(b))} duragina nasil ulasirim?"
        )
        ekle(
            "yazim_hatali",
            soru,
            beklenen_durak(a),
            beklenen_durak(b),
        )

    # 20 benzer adlı veya numaralı durak sorgusu.
    for i, (a, b) in enumerate(BENZER_ADLAR):
        soru = KALIPLAR[(i + 3) % len(KALIPLAR)].format(
            a=gorunen_ad(a),
            b=gorunen_ad(b),
        )
        ekle(
            "benzer_adlari_ayirma",
            soru,
            beklenen_durak(a),
            beklenen_durak(b),
        )

    # 10 eksik bilgi sorgusu: 5 başlangıç, 5 hedef eksik.
    for i in range(5):
        b = anahtarlar[i * 3]
        a = anahtarlar[i * 3 + 1]

        ekle(
            "eksik_bilgi",
            f"{gorunen_ad(b)} durağına gitmek istiyorum.",
            {"tur": "eksik"},
            beklenen_durak(b),
        )

        ekle(
            "eksik_bilgi",
            (
                f"Şu an {gorunen_ad(a)} durağındayım. "
                "Toplu taşımayla gitmek istiyorum."
            ),
            beklenen_durak(a),
            {"tur": "eksik"},
        )

    # 10 bilinçli olarak uydurulmuş yer sorgusu.
    for i in range(5):
        a = anahtarlar[i * 2 + 20]
        b = anahtarlar[i * 2 + 21]
        bilinmeyen1 = f"Zzqv Testkonum {741 + i}"
        bilinmeyen2 = f"Qzxv Hayaliyer {851 + i}"

        ekle(
            "bulunamayan_yer",
            (
                f"Başlangıcım {bilinmeyen1}, "
                f"hedefim {gorunen_ad(b)}. Nasıl giderim?"
            ),
            {"tur": "bilinmeyen", "ad": bilinmeyen1},
            beklenen_durak(b),
        )

        ekle(
            "bulunamayan_yer",
            (
                f"{gorunen_ad(a)} durağından "
                f"{bilinmeyen2} konumuna gitmek istiyorum."
            ),
            beklenen_durak(a),
            {"tur": "bilinmeyen", "ad": bilinmeyen2},
        )

    # 10 fazla genel yer sorgusu.
    genel_yerler = [
        "Malatya",
        "Yeşilyurt",
        "Battalgazi",
        "Merkez",
        "Türkiye",
    ]

    for i, yer in enumerate(genel_yerler):
        a = anahtarlar[i * 2 + 10]
        b = anahtarlar[i * 2 + 11]

        ekle(
            "fazla_genel_yer",
            (
                f"Başlangıcım {yer}, "
                f"varış yerim {gorunen_ad(b)}. Nasıl ulaşırım?"
            ),
            {"tur": "genel", "ad": yer},
            beklenen_durak(b),
        )

        ekle(
            "fazla_genel_yer",
            (
                f"{gorunen_ad(a)} durağından "
                f"{yer} konumuna nasıl giderim?"
            ),
            beklenen_durak(a),
            {"tur": "genel", "ad": yer},
        )

    if len(testler) != 100:
        raise ValueError("Test sayısı 100 olmalı.")

    if len({test["soru"] for test in testler}) != 100:
        raise ValueError("Tekrarlanan sorgu bulundu.")

    return testler


def kabul_edilen_adlar(anahtar):
    resmi_ad = DURAK_ADLARI[anahtar]

    adlar = {
        normalize(resmi_ad),
        normalize(resmi_ad.replace("CAD.", "CADDESİ")),
        normalize(resmi_ad.replace("CAD.", "CADDE")),
    }

    for yer, kisaltma, _ in KISALTMALAR:
        if yer == anahtar:
            adlar.add(normalize(kisaltma))

    return sorted(adlar)


def beklentileri_hazirla(testler):
    if ALTIN_DOSYA.exists():
        raise ValueError(
            "Beklentiler dosyası zaten var. "
            "Test sonucuna bakarak beklentilerin üzerine yazılmıyor."
        )

    # Mevcut projenin veritabanı bağlantısı.
    # Burada uygulamanın durak_ara fonksiyonu kullanılmaz.
    from db import baglanti_ac

    with baglanti_ac() as baglanti:
        satirlar = baglanti.execute(
            """
            SELECT durak_kodu, durak_adi
            FROM duraklar
            ORDER BY durak_kodu
            """
        ).fetchall()

    katalog = {}

    for kod, ad in satirlar:
        temiz_ad = durak_adini_temizle(ad)
        katalog.setdefault(temiz_ad, set()).add(str(kod))

    yerler = {}
    eksikler = []

    for anahtar, resmi_ad in DURAK_ADLARI.items():
        kodlar = katalog.get(normalize(resmi_ad), set())

        if not kodlar:
            eksikler.append(resmi_ad)

        yerler[anahtar] = {
            "resmi_ad": resmi_ad,
            "kodlar": sorted(kodlar),
            "kabul_edilen_adlar": kabul_edilen_adlar(anahtar),
        }

    # Bilinmeyen diye etiketlenen adların katalogda bulunmadığını kontrol et.
    for test in testler:
        for taraf in ("baslangic", "hedef"):
            beklenti = test[taraf]

            if (
                beklenti["tur"] == "bilinmeyen"
                and normalize(beklenti["ad"]) in katalog
            ):
                raise ValueError(
                    "Bilinmeyen yer etiketi veritabanıyla çelişiyor: "
                    + beklenti["ad"]
                )

    if eksikler:
        raise ValueError(
            "Şu etiketlenen durak adları veritabanında doğrulanamadı.\n"
            "Test başlatılmadı; bu listeyi paylaş:\n- "
            + "\n- ".join(eksikler)
        )

    veri = {
        "surum": 1,
        "test_seti_ozeti": ozet_degeri(testler),
        "hazirlanma_zamani": datetime.now().isoformat(),
        "yerler": yerler,
        "testler": testler,
    }

    veri["icerik_ozeti"] = ozet_degeri(veri)
    dosyaya_yaz(ALTIN_DOSYA, veri)

    ozet_satirlari = [
        "TESTTEN ÖNCE KONTROL EDİLECEK BEKLENTİLER",
        "",
    ]

    for yer in yerler.values():
        ozet_satirlari.append(
            f"{yer['resmi_ad']} -> {', '.join(yer['kodlar'])}"
        )

    for test in testler:
        ozet_satirlari.extend(
            [
                "",
                f"{test['id']} [{test['kategori']}]",
                test["soru"],
                "Başlangıç: "
                + json.dumps(test["baslangic"], ensure_ascii=False),
                "Hedef: "
                + json.dumps(test["hedef"], ensure_ascii=False),
            ]
        )

    (KLASOR / "adres_testi_beklenti_ozeti.txt").write_text(
        "\n".join(ozet_satirlari),
        encoding="utf-8",
    )

    print("100 sorgunun beklentileri sabitlendi.")
    print("API'ye henüz istek gönderilmedi.")
    print("Önce adres_testi_beklenti_ozeti.txt dosyasını incele.")
    print()
    print("Kategori dağılımı:")

    for kategori, sayi in Counter(
        test["kategori"] for test in testler
    ).items():
        print(f"- {kategori}: {sayi}")


def tarafi_degerlendir(beklenti, yanit, yerler):
    if not isinstance(yanit, dict):
        raise ValueError("Başlangıç/hedef yanıtı nesne olmalı.")

    eslesmeler = yanit.get("durak_eslesmeleri")

    if not isinstance(eslesmeler, list):
        raise ValueError("durak_eslesmeleri liste olmalı.")

    gelen_kodlar = {
        str(durak["durak_kodu"])
        for durak in eslesmeler
    }

    anlasilan = yanit.get("anlasilan_yer")
    cozum_turu = yanit.get("cozum_turu")
    koordinat = yanit.get("adres_koordinati")
    beklenen_kodlar = set()
    tur = beklenti["tur"]

    if tur == "durak":
        yer = yerler[beklenti["yer"]]
        beklenen_kodlar = set(yer["kodlar"])

        temiz_anlasilan = normalize(anlasilan or "")
        temiz_anlasilan = re.sub(
            r"\s+(?:duragi|durak)$",
            "",
            temiz_anlasilan,
        )

        anlam_dogru = (
            temiz_anlasilan in yer["kabul_edilen_adlar"]
        )

        eslesme_dogru = (
            gelen_kodlar == beklenen_kodlar
            and cozum_turu == "durak_eslesmesi"
        )

    elif tur == "eksik":
        anlam_dogru = anlasilan is None or anlasilan == ""

        eslesme_dogru = (
            not gelen_kodlar
            and koordinat is None
            and cozum_turu == "bulunamadi"
        )

    else:
        anlam_dogru = (
            normalize(anlasilan or "")
            == normalize(beklenti["ad"])
        )

        beklenen_cozum = (
            "yetersiz_bilgi"
            if tur == "genel"
            else "bulunamadi"
        )

        eslesme_dogru = (
            not gelen_kodlar
            and koordinat is None
            and cozum_turu == beklenen_cozum
        )

    return {
        "beklenen": beklenti,
        "anlasilan_yer": anlasilan,
        "cozum_turu": cozum_turu,
        "anlam_dogru": anlam_dogru,
        "eslesme_dogru": eslesme_dogru,
        "beklenen_kodlar": sorted(beklenen_kodlar),
        "gelen_kodlar": sorted(gelen_kodlar),
        "eksik_kodlar": sorted(beklenen_kodlar - gelen_kodlar),
        "fazla_kodlar": sorted(gelen_kodlar - beklenen_kodlar),
        "tp": len(beklenen_kodlar & gelen_kodlar),
        "fp": len(gelen_kodlar - beklenen_kodlar),
        "fn": len(beklenen_kodlar - gelen_kodlar),
    }


def yuzde(dogru, toplam):
    if not toplam:
        return None
    return round(100 * dogru / toplam, 2)


def sonuclari_ozetle(sonuclar):
    toplam = len(sonuclar)

    degerlendirilenler = [
        sonuc
        for sonuc in sonuclar
        if sonuc["degerlendirildi"]
    ]

    n = len(degerlendirilenler)

    ozet = {
        "toplam_sorgu": toplam,
        "degerlendirilen_sorgu": n,
        "teknik_hata": toplam - n,
    }

    for taraf in ("baslangic", "hedef"):
        anlam_dogru = sum(
            sonuc[taraf]["anlam_dogru"]
            for sonuc in degerlendirilenler
        )

        eslesme_dogru = sum(
            sonuc[taraf]["eslesme_dogru"]
            for sonuc in degerlendirilenler
        )

        ozet[taraf] = {
            "anlam_dogru": anlam_dogru,
            "anlam_yuzde": yuzde(anlam_dogru, n),
            "eslesme_dogru": eslesme_dogru,
            "eslesme_yuzde": yuzde(eslesme_dogru, n),
        }

    birlikte_dogru = sum(
        sonuc["baslangic"]["eslesme_dogru"]
        and sonuc["hedef"]["eslesme_dogru"]
        for sonuc in degerlendirilenler
    )

    tam_dogru = sum(
        sonuc["tam_dogru"]
        for sonuc in degerlendirilenler
    )

    bilinen_duraklar = [
        sonuc[taraf]
        for sonuc in degerlendirilenler
        for taraf in ("baslangic", "hedef")
        if sonuc[taraf]["beklenen"]["tur"] == "durak"
    ]

    tp = sum(x["tp"] for x in bilinen_duraklar)
    fp = sum(x["fp"] for x in bilinen_duraklar)
    fn = sum(x["fn"] for x in bilinen_duraklar)

    ozet.update(
        {
            "iki_uc_eslesme_dogru": birlikte_dogru,
            "iki_uc_eslesme_yuzde": yuzde(birlikte_dogru, n),
            "tam_dogru_sorgu": tam_dogru,
            "tam_dogru_yuzde": yuzde(tam_dogru, n),
            "teknik_hatalar_dahil_basari_yuzde": yuzde(
                tam_dogru,
                toplam,
            ),
            "bilinen_durak_kodlari": {
                "kontrol_sayisi": len(bilinen_duraklar),
                "dogru_kod": tp,
                "fazla_kod": fp,
                "eksik_kod": fn,
                "precision_yuzde": yuzde(tp, tp + fp),
                "recall_yuzde": yuzde(tp, tp + fn),
            },
        }
    )

    return ozet


def testleri_calistir(testler):
    if not ALTIN_DOSYA.exists():
        raise ValueError(
            "Önce --hazirla komutunu çalıştırmalısın."
        )

    altin = json.loads(
        ALTIN_DOSYA.read_text(encoding="utf-8")
    )

    kayitli_ozet = altin["icerik_ozeti"]

    ozetsiz_veri = {
        anahtar: deger
        for anahtar, deger in altin.items()
        if anahtar != "icerik_ozeti"
    }

    if (
        ozet_degeri(ozetsiz_veri) != kayitli_ozet
        or altin["test_seti_ozeti"] != ozet_degeri(testler)
    ):
        raise ValueError(
            "Test seti veya beklentiler sonradan değişmiş. "
            "Aynı deney olarak karşılaştırılamaz."
        )

    api_adresi = "http://127.0.0.1:8000"

    try:
        saglik = requests.get(
            api_adresi + "/saglik",
            timeout=10,
        )
        saglik.raise_for_status()
    except requests.RequestException as hata:
        raise ValueError(
            "Yerel API'ye erişilemedi. "
            "Önce FastAPI sunucusunu çalıştır."
        ) from hata

    zaman = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    sonuc_klasoru = KLASOR / f"adres_test_sonuclari_{zaman}"
    sonuc_klasoru.mkdir()

    dosyaya_yaz(
        sonuc_klasoru / "deney_bilgisi.json",
        {
            "zaman": datetime.now().isoformat(),
            "test_seti_ozeti": altin["test_seti_ozeti"],
            "beklenti_ozeti": kayitli_ozet,
            "api": api_adresi + "/adres-coz",
            "yeniden_deneme": 0,
            "istekler_arasi_saniye": 2,
            "aciklama": (
                "Adres çıkarımı ve durak eşleştirme testi. "
                "Rota veya geocoding doğruluğu ölçümü değildir."
            ),
        },
    )

    sonuclar = []

    with requests.Session() as oturum:
        for sira, test in enumerate(altin["testler"], start=1):
            sonuc = {
                "id": test["id"],
                "kategori": test["kategori"],
                "soru": test["soru"],
                "degerlendirildi": False,
                "teknik_hata": None,
                "ham_yanit": None,
            }

            try:
                cevap = oturum.post(
                    api_adresi + "/adres-coz",
                    json={"metin": test["soru"]},
                    timeout=60,
                )

                sonuc["http_durumu"] = cevap.status_code

                if cevap.status_code != 200:
                    sonuc["teknik_hata"] = (
                        f"HTTP {cevap.status_code}"
                    )
                    sonuc["hata_aciklamasi"] = cevap.text[:1000]

                else:
                    veri = cevap.json()
                    sonuc["ham_yanit"] = veri

                    if not isinstance(
                        veri.get("basarili"), bool
                    ):
                        raise ValueError(
                            "Yanıtta basarili alanı yok veya boolean değil."
                        )

                    for taraf in ("baslangic", "hedef"):
                        sonuc[taraf] = tarafi_degerlendir(
                            test[taraf],
                            veri[taraf],
                            altin["yerler"],
                        )

                    beklenen_basarili = all(
                        test[taraf]["tur"] == "durak"
                        for taraf in ("baslangic", "hedef")
                    )

                    sonuc["basarili_alani_dogru"] = (
                        veri["basarili"] == beklenen_basarili
                    )

                    sonuc["tam_dogru"] = (
                        sonuc["basarili_alani_dogru"]
                        and all(
                            sonuc[taraf]["anlam_dogru"]
                            and sonuc[taraf]["eslesme_dogru"]
                            for taraf in ("baslangic", "hedef")
                        )
                    )

                    sonuc["degerlendirildi"] = True

            except requests.RequestException as hata:
                sonuc["teknik_hata"] = type(hata).__name__

            except (ValueError, KeyError, TypeError) as hata:
                sonuc["teknik_hata"] = (
                    "YanitSemasiHatasi: " + str(hata)
                )

            sonuclar.append(sonuc)

            # Her sonuç hemen kaydedilir.
            with (sonuc_klasoru / "detaylar.jsonl").open(
                "a",
                encoding="utf-8",
            ) as dosya:
                dosya.write(
                    json.dumps(sonuc, ensure_ascii=False) + "\n"
                )

            if not sonuc["degerlendirildi"]:
                durum = "TEKNİK HATA"
            elif sonuc["tam_dogru"]:
                durum = "DOĞRU"
            else:
                durum = "YANLIŞ"

            print(
                f"[{sira:03}/100] "
                f"{test['id']} [{test['kategori']}] {durum}",
                flush=True,
            )

            if sira < len(altin["testler"]):
                time.sleep(2)

    kategoriler = sorted(
        {sonuc["kategori"] for sonuc in sonuclar}
    )

    rapor = {
        "genel": sonuclari_ozetle(sonuclar),
        "kategoriler": {
            kategori: sonuclari_ozetle(
                [
                    sonuc
                    for sonuc in sonuclar
                    if sonuc["kategori"] == kategori
                ]
            )
            for kategori in kategoriler
        },
    }

    dosyaya_yaz(
        sonuc_klasoru / "ozet.json",
        rapor,
    )

    print("\n--- TEST SONUCU ---")
    print(
        json.dumps(
            rapor["genel"],
            ensure_ascii=False,
            indent=2,
        )
    )
    print("\nSonuç klasörü:", sonuc_klasoru)
    print(
        "\nBu sonuçlar rota veya geocoding koordinat "
        "doğruluğunu göstermez."
    )


def main():
    parser = argparse.ArgumentParser(
        description="100 sorguluk adres çözümleme testi"
    )

    secim = parser.add_mutually_exclusive_group(required=True)
    secim.add_argument("--hazirla", action="store_true")
    secim.add_argument("--calistir", action="store_true")

    args = parser.parse_args()
    testler = testleri_olustur()

    try:
        if args.hazirla:
            beklentileri_hazirla(testler)
        else:
            testleri_calistir(testler)

    except (ValueError, FileNotFoundError) as hata:
        print("\nİşlem durduruldu:")
        print(hata)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
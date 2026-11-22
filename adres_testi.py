"""100 sorguluk yerel adres testini sabit bir klasörde başlat veya sürdür."""
import argparse
import hashlib
import json
import math
import os
import re
import time
import unicodedata
from collections import Counter
from email.utils import parsedate_to_datetime
from pathlib import Path

from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ALTIN_DOSYA = Path(__file__).resolve().with_name("adres_testi_beklentiler.json")
TARAFLAR = ("baslangic", "hedef")
KOORDINAT_ESIGI = 50
KOORDINAT_HEDEFI = 85
KOORDINAT_URL = "http://127.0.0.1:8000/adres-coz"
KOORDINAT_DURAKLARI = (
    ("10001", "Maliye Durağı", "Maliyee Duragı"),
    ("10002", "Ticaret ve Sanayi Odası", "Ticart ve Sanayi Odası"),
    ("10003", "Sanayi", "Sanyai"),
    ("11309", "Posta İşleme ve Dağıtım Merkezi", "Posta İşlme ve Dagıtım Merkezi"),
    ("10004", "Malatya Büyükşehir Belediyesi", "Malatya Buyuksehir Beledyesi"),
    ("10005", "Dedekorkut", "Dedekorkt"),
    ("10006", "Eğitim ve Araştırma Hastanesi", "Egtim ve Arastrma Hastanesi"),
    ("10007", "SGK Şeker Fabrikası", "SGK Seker Fabrkası"),
    ("10008", "İŞKUR", "İSKURR"),
    ("10010", "Spor ve Yaşam Merkezi", "Spor ve Yasm Merkezi"),
    ("10011", "Fahri Kayahan", "Fahri Kayahn"),
    ("10012", "MAŞTİ Otogar", "Maşti Otogarr"),
    ("10951", "İnönü Üniversitesi", "Inönü Universitsi"),
    ("12502", "İnönü Üniversitesi OSB MYO", "Inönü Universitsi OSB MYO"),
    ("11887", "Tecde Şelale", "Tecdee Selale"),
    ("10105", "Yazıhan 11", "Yazhan 11"),
)
KOORDINAT_ADRESLERI = (
    ("Taşhoron Kilisesi, Malatya", "Taşhoron Kilsei, Malatya", 38.352448, 38.302082,
     "https://www.haritamap.com/lokasyon/tashoron-kilisesi-41"),
    ("Somuncu Baba Türbesi ve Külliyesi, Darende", "Somuncu Baba Türbesi ve Kulliysei, Darende", 38.560963, 37.491241,
     "https://www.haritamap.com/yer/somuncu-baba-turbesi-ve-kulliyesi-darende"),
    ("Arslantepe Höyüğü, Orduzu", "Arslantepe Höygu, Orduzu", 38 + 22/60 + 58/3600, 38 + 21/60 + 47.43/3600,
     "https://kvmgm.ktb.gov.tr/TR-291002/arslantepe-hoyugu-malatya.html"),
    ("Tevfik Temelli Caddesi 21. Sokak, Yeşilyurt", "Tevfk Temelli Caddesi 21. Sokak, Yesilyrt", 38.341824, 38.290207,
     "https://www.haritamap.com/yer/tevfik-temelli-caddesi-21-sokak-yesilyurt"),
)


def ozet_degeri(veri):
    metin = json.dumps(veri, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(metin.encode("utf-8")).hexdigest()


def dosyaya_yaz(yol, veri):
    gecici = yol.with_suffix(yol.suffix + ".tmp")
    gecici.write_text(json.dumps(veri, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    gecici.replace(yol)


def ad_normalize(ad):
    if ad is None:
        return ""
    if not isinstance(ad, str):
        raise ValueError("Anlaşılan yer metin veya null olmalı.")
    ad = unicodedata.normalize("NFKD", ad.casefold().replace("ı", "i"))
    ad = "".join(harf for harf in ad if not unicodedata.combining(harf))
    ad = re.sub(r"[^a-z0-9]+", " ", ad).strip()
    return re.sub(r"\s+(?:duragi|durak)$", "", ad)


def tarafi_degerlendir(beklenti, yanit, yerler):
    if not isinstance(yanit, dict) or not isinstance(yanit.get("durak_eslesmeleri"), list):
        raise ValueError("Yer veya durak eşleşmeleri geçersiz.")
    bulunan = {str(satir["durak_kodu"]) for satir in yanit["durak_eslesmeleri"]}
    anlasilan = yanit["anlasilan_yer"]
    cozum = yanit["cozum_turu"]
    koordinat = yanit["adres_koordinati"]
    tur = beklenti["tur"]
    beklenen = set()
    if tur == "durak":
        yer = yerler[beklenti["yer"]]
        beklenen = set(map(str, yer["kodlar"]))
        kabul = {ad_normalize(ad) for ad in [yer["resmi_ad"], *yer["kabul_edilen_adlar"]]}
        anlam = ad_normalize(anlasilan) in kabul
        eslesme = cozum == "durak_eslesmesi" and bulunan == beklenen
    else:
        anlam = (
            anlasilan in (None, "") if tur == "eksik"
            else ad_normalize(anlasilan) == ad_normalize(beklenti["ad"])
        )
        beklenen_cozum = "yetersiz_bilgi" if tur == "genel" else "bulunamadi"
        eslesme = not bulunan and koordinat is None and cozum == beklenen_cozum

    return {
        "beklenen": beklenti, "anlasilan_yer": anlasilan, "cozum_turu": cozum,
        "anlam_dogru": anlam, "eslesme_dogru": eslesme,
        "beklenen_kodlar": sorted(beklenen), "bulunan_kodlar": sorted(bulunan),
        "eksik_kodlar": sorted(beklenen - bulunan), "fazla_kodlar": sorted(bulunan - beklenen),
    }


def sonuclari_ozetle(sonuclar):
    gecerli = [r for r in sonuclar if r["degerlendirildi"]]
    n = len(gecerli)

    def yuzde(dogru, toplam=n):
        return round(100 * dogru / toplam, 2) if toplam else None

    ozet = {
        "toplam_sorgu": len(sonuclar), "degerlendirilen_sorgu": n,
        "teknik_hata": len(sonuclar) - n,
    }
    for taraf in TARAFLAR:
        anlam = sum(r[taraf]["anlam_dogru"] for r in gecerli)
        eslesme = sum(r[taraf]["eslesme_dogru"] for r in gecerli)
        ozet[taraf] = {
            "anlam_dogru": anlam, "anlam_yuzde": yuzde(anlam),
            "eslesme_dogru": eslesme, "eslesme_yuzde": yuzde(eslesme),
        }

    iki_uc = sum(all(r[t]["eslesme_dogru"] for t in TARAFLAR) for r in gecerli)
    tam = sum(r["tam_dogru"] for r in gecerli)
    kontroller = [r[t] for r in gecerli for t in TARAFLAR if r[t]["beklenen_kodlar"]]
    eksik = sum(len(t["eksik_kodlar"]) for t in kontroller)
    fazla = sum(len(t["fazla_kodlar"]) for t in kontroller)
    dogru = sum(len(t["beklenen_kodlar"]) for t in kontroller) - eksik
    ozet.update(
        iki_uc_eslesme_dogru=iki_uc, iki_uc_eslesme_yuzde=yuzde(iki_uc),
        tam_dogru_sorgu=tam, tam_dogru_yuzde=yuzde(tam),
        teknik_hatalar_dahil_basari_yuzde=yuzde(tam, len(sonuclar)),
        bilinen_durak_kodlari={
            "kontrol_sayisi": len(kontroller), "dogru_kod": dogru,
            "fazla_kod": fazla, "eksik_kod": eksik,
            "precision_yuzde": yuzde(dogru, dogru + fazla),
            "recall_yuzde": yuzde(dogru, dogru + eksik),
        },
    )
    return ozet

def json_oku(yol):
    return json.loads(yol.read_text(encoding="utf-8-sig"))


def satirlari_oku(yol):
    if not yol.exists():
        return []
    return [
        json.loads(satir)
        for satir in yol.read_text(encoding="utf-8-sig").splitlines()
        if satir.strip()
    ]


def kota_hatasi(sonuc):
    return sonuc.get("http_durumu") == 429 or sonuc.get("teknik_hata") == "HTTP 429"


def kota_bekleme(sonuc, tekrar, aralik):
    bekleme = max(aralik, min(1800, 60 * 2 ** min(tekrar - 1, 5)))
    baslik = sonuc.get("retry_after")
    if baslik:
        try:
            saniye = int(baslik) if baslik.isdecimal() else (
                parsedate_to_datetime(baslik).timestamp() - time.time()
            )
            bekleme = max(bekleme, saniye)
        except (ValueError, TypeError, OverflowError, OSError):
            pass
    return bekleme


def sorgula(url, sorgu, yerler):
    sonuc = {k: sorgu[k] for k in ("id", "kategori", "soru")}
    sonuc.update(degerlendirildi=False, teknik_hata=None, ham_yanit=None)
    try:
        istek = Request(
            url, data=json.dumps({"metin": sorgu["soru"]}, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"}, method="POST",
        )
        with urlopen(istek, timeout=60) as cevap:
            sonuc["http_durumu"] = cevap.status
            veri = json.load(cevap)
        sonuc["ham_yanit"] = veri
        if not isinstance(veri, dict) or not isinstance(veri.get("basarili"), bool):
            raise ValueError("basarili alanı geçersiz.")

        taraflar = ("baslangic", "hedef")
        for taraf in taraflar:
            sonuc[taraf] = tarafi_degerlendir(sorgu[taraf], veri[taraf], yerler)

        beklenen_basarili = all(sorgu[t]["tur"] == "durak" for t in taraflar)
        sonuc["basarili_alani_dogru"] = veri["basarili"] == beklenen_basarili
        sonuc["tam_dogru"] = sonuc["basarili_alani_dogru"] and all(
            sonuc[t]["anlam_dogru"] and sonuc[t]["eslesme_dogru"] for t in taraflar
        )
        sonuc["degerlendirildi"] = True

    except HTTPError as hata:
        sonuc["http_durumu"] = hata.code
        sonuc["teknik_hata"] = f"HTTP {hata.code}"
        if hata.headers is not None and hata.headers.get("Retry-After"):
            sonuc["retry_after"] = hata.headers["Retry-After"].strip()
        with hata:
            sonuc["hata_aciklamasi"] = hata.read(1000).decode("utf-8", errors="replace")
    except (URLError, OSError) as hata:
        sonuc["teknik_hata"] = type(hata).__name__
        sonuc["beklemede"] = True
    except (ValueError, TypeError, KeyError) as hata:
        sonuc["teknik_hata"] = "Yanıt şeması hatası: " + str(hata)

    return sonuc

def koordinat_cifti(veri, enlem="enlem", boylam="boylam"):
    try:
        a, b = float(veri[enlem]), float(veri[boylam])
        if -90 <= a <= 90 and -180 <= b <= 180:
            return a, b
    except (KeyError, ValueError, TypeError, OverflowError):
        pass
    return None


def mesafe_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (*a, *b))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def json_nesneleri(veri):
    if isinstance(veri, dict):
        yield veri
        for deger in veri.values():
            yield from json_nesneleri(deger)
    elif isinstance(veri, list):
        for deger in veri:
            yield from json_nesneleri(deger)


def koordinat_hazirla(ham_klasor):
    hedefler = {kod for kod, _, _ in KOORDINAT_DURAKLARI}
    kaynaklar = {}
    for yol in sorted(ham_klasor.rglob("*.json")):
        for kayit in json_nesneleri(json_oku(yol)):
            kod = str(kayit.get("id", ""))
            if kod not in hedefler:
                continue
            nokta = koordinat_cifti(kayit, "latitude", "longitude")
            if nokta is None:
                continue
            if kod in kaynaklar and mesafe_m(kaynaklar[kod][0], nokta) > 10:
                raise ValueError(f"MOTAŞ kaynaklarında {kod} için 10 m üstü fark var; referans doğrulanmalı.")
            kaynaklar.setdefault(kod, (nokta, yol.relative_to(ham_klasor).as_posix()))
    eksik = hedefler - kaynaklar.keys()
    if eksik:
        raise ValueError(f"{ham_klasor} içindeki ham MOTAŞ JSON'larında eksik duraklar: {', '.join(sorted(eksik))}")

    adresler = [
        {"id": kod, "grup": "durak", "dogru_ad": ad, "hatali_ad": yazim,
         "referans": list(kaynaklar[kod][0]), "kaynak": "MOTAŞ: " + kaynaklar[kod][1]}
        for kod, ad, yazim in KOORDINAT_DURAKLARI
    ] + [
        {"id": f"A{i}", "grup": "durak_disi_adres", "dogru_ad": ad, "hatali_ad": yazim,
         "referans": [enlem, boylam], "kaynak": url}
        for i, (ad, yazim, enlem, boylam, url) in enumerate(KOORDINAT_ADRESLERI, 1)
    ]
    sorgular = []
    for i in range(10):
        a, b = adresler[i], adresler[10 + i]
        if i % 2:
            a, b = b, a
        sorgular.append({
            "id": f"K{i + 1:02}", "baslangic": a, "hedef": b,
            "metin": f"{a['hatali_ad']} konumundan {b['hatali_ad']} konumuna gitmek istiyorum.",
        })
    veri = {"surum": 1, "esik_metre": KOORDINAT_ESIGI, "hedef_yuzde": KOORDINAT_HEDEFI,
            "aday_kurali": "Adres koordinatı; yoksa API'nin ilk durak adayı",
            "sorgular": sorgular}
    veri["icerik_ozeti"] = ozet_degeri(veri)
    return veri

def koordinat_olc(yanit, beklenen, esik):
    if beklenen.get("referans_durumu") == "dogrulanamadi":
        return {**beklenen, "durum": "referans_dogrulanamadi"}

    if not isinstance(yanit, dict) or not isinstance(yanit.get("durak_eslesmeleri"), list):
        raise ValueError("Beklenen adres yanıtı alınamadı.")
    adaylar = yanit["durak_eslesmeleri"]
    nokta = koordinat_cifti(yanit.get("adres_koordinati"))
    if nokta is None and adaylar:
        nokta = koordinat_cifti(adaylar[0])
    uzaklik = mesafe_m(beklenen["referans"], nokta) if nokta is not None else None
    durum = ("koordinat_yok" if uzaklik is None else "dogru" if uzaklik <= esik else "yanlis_konum")
    return {**beklenen, "durum": durum, "donen_koordinat": nokta,
            "mesafe_metre": round(uzaklik, 2) if uzaklik is not None else None,
            "anlasilan_yer": yanit.get("anlasilan_yer"), "cozum_turu": yanit.get("cozum_turu")}


def koordinat_ozet(veri, kayitlar):
    def grup_ozeti(grup=None):
        c = Counter()
        for sorgu in veri["sorgular"]:
            kayit = kayitlar.get(sorgu["id"], {})
            for taraf in TARAFLAR:
                if grup is None or sorgu[taraf]["grup"] == grup:
                    if sorgu[taraf].get("referans_durumu") == "dogrulanamadi":
                        c["referans_dogrulanamadi"] += 1
                    else:
                        c[kayit.get(taraf, {}).get("durum", kayit.get("durum", "bekliyor"))] += 1
        toplam = sum(c.values())
        degerlendirilen = c["dogru"] + c["yanlis_konum"] + c["koordinat_yok"]
        oran = 100 * c["dogru"] / degerlendirilen if degerlendirilen else None
        return {"toplam_adres": toplam, "dogru": c["dogru"], "yanlis_konum": c["yanlis_konum"],
                "koordinat_yok": c["koordinat_yok"], "teknik_hata": c["teknik_hata"],
                "kota_bekleyen": c["kota_bekleyen"], "henuz_calismayan": c["bekliyor"],
                "referans_dogrulanamadi": c["referans_dogrulanamadi"],
                "gecerli_referansli_adres": toplam - c["referans_dogrulanamadi"],
                "degerlendirilen": degerlendirilen,
                "degerlendirilenlerde_dogruluk_yuzde": round(oran, 2) if oran is not None else None,
                "gecerli_alt_kumede_hedef_karsilandi": (
                    oran >= veri["hedef_yuzde"]
                    if degerlendirilen and degerlendirilen == toplam - c["referans_dogrulanamadi"] else None
                ),
                "hedef_karsilandi": oran >= veri["hedef_yuzde"] if degerlendirilen == toplam else None}
    return {"esik_metre": veri["esik_metre"], "hedef_yuzde": veri["hedef_yuzde"],
            "genel": grup_ozeti(),
            "gruplar": {g: grup_ozeti(g) for g in ("durak", "durak_disi_adres")},
            "sonuclar": kayitlar}

def koordinat_v2_hazirla(kok):
    eski = kok / "akilli-ulasim-koordinat-testi" / "referanslar.json"
    hedef = kok / "akilli-ulasim-koordinat-testi-v2"
    hedef.mkdir(parents=True, exist_ok=True)
    yol = hedef / "referanslar.json"
    if yol.exists():
        return hedef
    veri = json_oku(eski)
    onceki_imza = veri["icerik_ozeti"]
    if onceki_imza != ozet_degeri({k: v for k, v in veri.items() if k != "icerik_ozeti"}):
        raise ValueError("Eski referansların bütünlüğü doğrulanamadı.")
    veri.pop("icerik_ozeti")
    veri.update(surum=2, onceki_referans_ozeti=onceki_imza,
                degisiklik_notu="A1/A2 bağımsız kaynakla düzeltildi. A3 alan/nokta belirsizliği; A4 konum doğrulanamadı. Eski dosyalar korunur.")
    duzeltmeler = {
        "A1": ([38.3525848, 38.3084068], "https://kulturenvanteri.com/yer/tashoran-kilisesi/"),
        "A2": ([38.5768013, 37.4921989], "https://kulturenvanteri.com/yer/somuncu-baba-turbesi-darende/"),
    }
    for sorgu in veri["sorgular"]:
        for t in TARAFLAR:
            adres = sorgu[t]
            if adres["id"] in duzeltmeler:
                adres["onceki_referans"] = adres["referans"]
                adres["referans"], adres["kaynak"] = duzeltmeler[adres["id"]]
            if adres["id"] in ("A3", "A4"):
                adres["referans_durumu"] = "dogrulanamadi"
                adres["dislama_nedeni"] = (
                    "Geniş alan için 50 m ile karşılaştırılacak hedef nokta kesinleşmedi."
                    if adres["id"] == "A3" else "Sokağın kesin konumu doğrulanamadı."
                )
    veri["icerik_ozeti"] = ozet_degeri(veri)
    dosyaya_yaz(yol, veri)
    return hedef

def koordinat_modu(args, klasor):
    klasor.mkdir(parents=True, exist_ok=True)
    referans_yolu = klasor / "referanslar.json"
    if args.koordinat_hazirla and not referans_yolu.exists():
        dosyaya_yaz(referans_yolu, koordinat_hazirla(args.veri_klasoru))
    if not referans_yolu.exists():
        raise ValueError("Önce --koordinat-hazirla ile referansları sabitle.")
    veri = json_oku(referans_yolu)
    imza = veri["icerik_ozeti"]
    if imza != ozet_degeri({k: v for k, v in veri.items() if k != "icerik_ozeti"}):
        raise ValueError("Sabitlenmiş koordinat referansları değişmiş.")
    print("Referanslar:", referans_yolu, flush=True)
    if args.koordinat_hazirla:
        print("20 adres sabit; 10 sorgu. Eşik: 50 m. Hazırlık API isteği göndermez.")
        return

    kayit_yolu = klasor / "sonuclar.json"
    ozet_yolu = klasor / "ozet.json"
    sonuc = json_oku(kayit_yolu) if kayit_yolu.exists() else {"referans_ozeti": imza, "kayitlar": {}}
    if sonuc["referans_ozeti"] != imza:
        raise ValueError("Koordinat sonuçları başka bir referans setine ait.")
    kayitlar = sonuc["kayitlar"]
    bekleyen = [s for s in veri["sorgular"]
                if kayitlar.get(s["id"], {}).get("durum") != "degerlendirildi"]
    try:
        for i, sorgu in enumerate(bekleyen):
            istek = Request(KOORDINAT_URL,
                            data=json.dumps({
                                "metin": sorgu["metin"],
                                **({f"{t}_turu": "durak" if sorgu[t]["grup"] == "durak" else "adres"
                                    for t in TARAFLAR} if veri.get("surum") == 2 else {}),
                            }, ensure_ascii=False).encode("utf-8"),
                            headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
            try:
                with urlopen(istek, timeout=60) as cevap:
                    yanit = json.load(cevap)
                kayit = {t: koordinat_olc(yanit[t], sorgu[t], veri["esik_metre"]) for t in TARAFLAR}
                kayit["durum"] = "degerlendirildi"
            except HTTPError as hata:
                hata.close()
                kayit = {"durum": "kota_bekleyen" if hata.code == 429 else "teknik_hata",
                         "hata": f"HTTP {hata.code}"}
            except (OSError, ValueError, KeyError, TypeError) as hata:
                kayit = {"durum": "teknik_hata", "hata": type(hata).__name__}
            kayitlar[sorgu["id"]] = kayit
            dosyaya_yaz(kayit_yolu, sonuc)
            if kayit["durum"] != "degerlendirildi":
                print(f"{sorgu['id']}: {kayit['hata']}. Durdu; aynı komutla devam edebilirsin.")
                break
            print(f"{sorgu['id']}: " + ", ".join(f"{t}={kayit[t]['durum']}" for t in TARAFLAR), flush=True)
            if i + 1 < len(bekleyen):
                time.sleep(args.aralik if args.aralik is not None else 15)
    except KeyboardInterrupt:
        print("\nDurduruldu. Ölçülen adresler kaydedildi.")
    finally:
        ozet = koordinat_ozet(veri, kayitlar)
        dosyaya_yaz(ozet_yolu, ozet)
        genel = ozet["genel"]
        print(f"Doğru: {genel['dogru']}/{genel['degerlendirilen']} ölçülen adres "
              f"({genel['toplam_adres']} planlandı). Özet: {ozet_yolu}")
        hedef = genel["hedef_karsilandi"]
        if hedef is None:
            print("Eksik ölçüm veya doğrulanmamış referans var. Tüm set için %85 kararı verilmedi.")
        else:
            print("%85 hedefi karşılandı." if hedef else "%85 hedefi karşılanmadı.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aralik", type=float, help="İstekler arasındaki saniye")
    parser.add_argument("--calistir", action="store_true", help="Testi başlat veya sürdür (varsayılan)")
    mod = parser.add_mutually_exclusive_group()
    mod.add_argument("--koordinat-hazirla", action="store_true", help="Referansları sabitle; API çağırma")
    mod.add_argument("--koordinat", action="store_true", help="Koordinat testini başlat veya sürdür")
    parser.add_argument("--deney", help="Koordinat ölçümü için ayrı kayıt adı")
    parser.add_argument("--koordinat-v2", action="store_true", help="Eski sonuçları koruyarak düzeltilmiş koordinat deneyi")
    parser.add_argument("--veri-klasoru", type=Path, default=Path(__file__).resolve().parent / "veriler",
                        help="Orijinal MOTAŞ JSON klasörü (varsayılan: veriler)")
    args = parser.parse_args()
    if args.aralik is not None and not 1 <= args.aralik <= 3600:
        parser.error("--aralik 1 ile 3600 saniye arasında olmalı.")
    if args.koordinat_v2 and not args.koordinat:
        parser.error("--koordinat-v2 yalnız --koordinat ile kullanılır.")
    if args.koordinat_hazirla or args.koordinat:
        kok = Path(os.environ.get("LOCALAPPDATA") or Path.home())
        klasor = (koordinat_v2_hazirla(kok) if args.koordinat_v2
                  else kok / "akilli-ulasim-koordinat-testi")
        if args.deney:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", args.deney):
                parser.error("--deney yalnız harf, sayı, alt çizgi veya tire içerebilir.")
            yeni = klasor / ("deney-" + args.deney)
            yeni.mkdir(parents=True, exist_ok=True)
            kaynak = klasor / "referanslar.json"
            hedef = yeni / "referanslar.json"
            if not hedef.exists():
                dosyaya_yaz(hedef, json_oku(kaynak))
            elif json_oku(hedef)["icerik_ozeti"] != json_oku(kaynak)["icerik_ozeti"]:
                raise ValueError("Bu deney adı başka referanslara ait; farklı ad kullan.")
            klasor = yeni
        koordinat_modu(args, klasor)
        return
    if not ALTIN_DOSYA.is_file():
        raise FileNotFoundError(f"Mevcut beklenti dosyası bu konumda bulunamadı: {ALTIN_DOSYA}")

    altin = json_oku(ALTIN_DOSYA)
    icerik = {k: v for k, v in altin.items() if k != "icerik_ozeti"}
    if ozet_degeri(icerik) != altin["icerik_ozeti"]:
        raise ValueError("Beklenti dosyası değişmiş.")
    if ozet_degeri(altin["testler"]) != altin["test_seti_ozeti"]:
        raise ValueError("Sorgu seti değişmiş; eski sonuçlarla birleştirilemez.")

    klasor = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "akilli-ulasim-test-100"
    klasor.mkdir(parents=True, exist_ok=True)
    meta_yolu = klasor / "adres_testi_deney.json"
    if not meta_yolu.exists():
        if (klasor / "adres_testi_denemeleri.jsonl").exists():
            raise ValueError("Sonuçlar var, ancak deney bilgisi eksik. Kayıtlar korunuyor.")
        dosyaya_yaz(meta_yolu, {
            "test_seti_ozeti": altin["test_seti_ozeti"],
            "beklenti_ozeti": altin["icerik_ozeti"],
            "api": "http://127.0.0.1:8000/adres-coz",
            "istekler_arasi_saniye": args.aralik if args.aralik is not None else 15.0,
        })

    meta = json_oku(meta_yolu)
    if (meta["test_seti_ozeti"] != altin["test_seti_ozeti"]
            or meta["beklenti_ozeti"] != altin["icerik_ozeti"]):
        raise ValueError("Sabit klasördeki deney mevcut beklentilerle uyuşmuyor.")

    url = "http://127.0.0.1:8000/adres-coz"
    if meta["api"] != url:
        raise ValueError("İlk test farklı bir API adresinde çalıştırılmış.")

    aralik = args.aralik if args.aralik is not None else meta["istekler_arasi_saniye"]
    if not 1 <= aralik <= 3600:
        raise ValueError("--aralik 1 ile 3600 saniye arasında olmalı.")

    tum_sorgular = altin["testler"]
    indeks = {s["id"]: s for s in tum_sorgular}
    if len(tum_sorgular) != 100 or len(indeks) != 100:
        raise ValueError("Beklenen test setinde 100 farklı sorgu olmalı.")

    devam_dosyasi = klasor / "adres_testi_denemeleri.jsonl"
    denemeler = satirlari_oku(devam_dosyasi)
    tamamlanan = {}
    for kayit in denemeler:
        sorgu = indeks.get(kayit["id"])
        if sorgu is None or any(sorgu[k] != kayit[k] for k in ("kategori", "soru")):
            raise ValueError("Bir kayıt sabitlenmiş sorgusuyla uyuşmuyor.")
        if not (kota_hatasi(kayit) or kayit.get("beklemede")):
            tamamlanan.setdefault(kayit["id"], kayit)

    bekleyen = [s for s in tum_sorgular if s["id"] not in tamamlanan]
    print("Sonuç klasörü:", klasor)
    print(f"Korunan sonuç: {len(tamamlanan)}. Kalan: {len(bekleyen)}.", flush=True)

    try:
        if bekleyen:
            try:
                with urlopen("http://127.0.0.1:8000/saglik", timeout=10):
                    pass
            except OSError as hata:
                raise ValueError("FastAPI sağlık kontrolü başarısız. Sunucuyu kontrol et: " + str(hata)) from hata
            sira = 0
            kota_tekrari = 0
            while sira < len(bekleyen):
                sorgu = bekleyen[sira]
                sonuc = sorgula(url, sorgu, altin["yerler"])
                sonuc["istek_araligi_saniye"] = aralik
                with devam_dosyasi.open("a", encoding="utf-8") as dosya:
                    dosya.write(json.dumps(sonuc, ensure_ascii=False) + "\n")
                    dosya.flush()
                    os.fsync(dosya.fileno())
                denemeler.append(sonuc)

                if kota_hatasi(sonuc):
                    kota_tekrari += 1
                    bekleme = kota_bekleme(sonuc, kota_tekrari, aralik)
                    print(
                        f"{sorgu['id']}: 429. {bekleme:.0f} saniye sonra otomatik tekrar denenecek.",
                        flush=True,
                    )
                    time.sleep(bekleme)
                    continue
                if sonuc.get("beklemede"):
                    print(f"{sorgu['id']}: API bağlantısı kesildi. Bu sorgu beklemede kaldı.")
                    break

                tamamlanan[sorgu["id"]] = sonuc
                sira += 1
                kota_tekrari = 0
                durum = ("DOĞRU" if sonuc.get("tam_dogru") else
                         "YANLIŞ" if sonuc["degerlendirildi"] else "TEKNİK HATA")
                print(f"[{len(tamamlanan):03}/100] {sorgu['id']} {durum}", flush=True)
                if sira < len(bekleyen):
                    time.sleep(aralik)

    except KeyboardInterrupt:
        print("\nDurduruldu. Yazılan sonuçlar korundu.")
    finally:
        sonuclar = [tamamlanan[s["id"]] for s in tum_sorgular if s["id"] in tamamlanan]
        ozet = {
            "tam_test": len(sonuclar) == len(tum_sorgular),
            "planlanan_sorgu": len(tum_sorgular),
            "kalan_sorgu": len(tum_sorgular) - len(sonuclar),
            "toplam_test_istegi": len(denemeler),
            "kota_429_denemeleri": sum(kota_hatasi(r) for r in denemeler),
            "deneme_hatalari": dict(Counter(
                r["teknik_hata"] for r in denemeler if r.get("teknik_hata")
            )),
            "genel": sonuclari_ozetle(sonuclar),
            "kategoriler": {
                kategori: sonuclari_ozetle([
                    r for r in sonuclar if r["kategori"] == kategori
                ])
                for kategori in sorted({r["kategori"] for r in sonuclar})
            },
            "not": "Kota duraklarından devam edilen test. Kota denemeleri ayrı sayılır.",
        }
        dosyaya_yaz(klasor / "adres_testi_ozet.json", ozet)
        print(f"Tamamlanan: {len(sonuclar)}/100. Özet: {klasor / 'adres_testi_ozet.json'}")
        if ozet["tam_test"]:
            print("100 sorgu tamamlandı.")
        else:
            print("Bu kısmi sonuçtur. Aynı komutla kaldığın yerden devam edebilirsin.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as hata:
        raise SystemExit(str(hata))

import re
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from db import baglanti_ac
from geocoding import adresi_koordinata_cevir, GeocodingError
from yer_aramasi import yer_ara, yer_getir
from rota_api import router as rota_router, _duraklari_yukle

from adres_coz import (
    adresleri_coz,
    metni_normalize_et,
    durak_ara,
    dogrudan_hatlari_bul,
    tek_aktarmali_hatlari_bul,
    hat_duraklarini_getir,
    sefer_saatlerini_getir,
)


app = FastAPI(
    title="Akıllı Ulaşım Asistanı API",
    description="Malatya toplu taşıma hatları için yönlendirme servisi",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(rota_router)


class GeocodingRequest(BaseModel):
    adres: str


class YolTarifiIstegi(BaseModel):
    soru: str
    gun: str | None = None


class AdresCozIstegi(BaseModel):
    metin: str
    baslangic_turu: Literal["otomatik", "durak", "adres"] = "otomatik"
    hedef_turu: Literal["otomatik", "durak", "adres"] = "otomatik"
    baslangic_yer_id: int | None = None
    hedef_yer_id: int | None = None


class DogalDilRotaIstegi(BaseModel):
    soru: str = Field(min_length=1, max_length=1000)
    baslangic_turu: Literal["otomatik", "durak", "adres"] = "otomatik"
    hedef_turu: Literal["otomatik", "durak", "adres"] = "otomatik"
    baslangic_yer_id: int | None = None
    hedef_yer_id: int | None = None

    yaricap_metre: float = Field(
        default=1000,
        gt=0,
        le=5000,
        allow_inf_nan=False,
    )

    aday_limiti: int = Field(default=10, ge=1, le=50)
    sonuc_limiti: int = Field(default=5, ge=1, le=50)


GUNLER = [
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
]

GENEL_YERLER = {
    "malatya",
    "yesilyurt",
    "battalgazi",
    "merkez",
    "turkiye",
}


def gunu_duzenle(girilen_gun):
    if not girilen_gun:
        return None

    for gun in GUNLER:
        if metni_normalize_et(girilen_gun) == metni_normalize_et(gun):
            return gun

    return None


def duraklari_jsona_cevir(durak_satirlari):
    return [
        {
            "sira": sira,
            "durak_kodu": kod,
            "durak_adi": ad,
        }
        for sira, kod, ad in durak_satirlari
    ]


def eslesme_metin_temizle(metin):
    from durak_eslestirme import eslestirme_metni

    return eslestirme_metni(metin)


def yer_cok_genel_mi(yer):
    if not yer:
        return False

    return metni_normalize_et(yer).strip() in GENEL_YERLER


def durak_eslesmelerini_jsona_cevir(durak_satirlari, aranan_yer):
    temiz_aranan = eslesme_metin_temizle(aranan_yer)
    sonuc = []

    for kod, ad, enlem, boylam in durak_satirlari:
        temiz_ad = eslesme_metin_temizle(ad)

        if temiz_ad == temiz_aranan:
            eslesme_turu = "tam"
        elif temiz_ad.startswith(temiz_aranan):
            eslesme_turu = "baslangictan"
        elif temiz_aranan in temiz_ad:
            eslesme_turu = "iceriyor"
        else:
            eslesme_turu = "diger"

        sonuc.append(
            {
                "durak_kodu": kod,
                "durak_adi": ad,
                "enlem": enlem,
                "boylam": boylam,
                "eslesme_turu": eslesme_turu,
            }
        )

    return sonuc


def adresi_geocode_et(adres):
    if not adres or not adres.strip():
        return None, None

    try:
        return adresi_koordinata_cevir(adres), None
    except GeocodingError as hata:
        return None, str(hata)


def saatleri_jsona_cevir(hat_kodu, yon, gun):
    if not gun:
        return []

    saat_satirlari = sefer_saatlerini_getir(hat_kodu, yon, gun)

    return [
        {
            "saat": (
                saat.strftime("%H:%M")
                if hasattr(saat, "strftime")
                else str(saat)
            ),
            "aciklama": aciklama,
        }
        for saat, aciklama in saat_satirlari
    ]


def sefer_saati_notunu_hazirla(ilk_durak_sirasi):
    if ilk_durak_sirasi != 1:
        return (
            "Sefer saatleri hattın başlangıç durağı içindir; "
            "bu güzergâhtaki biniş veya aktarma durağından "
            "geçiş saatini göstermez."
        )

    return None


def konum_turunu_belirle(yer, tercih="otomatik"):
    if tercih != "otomatik":
        return tercih

    temiz = metni_normalize_et(yer or "")

    if re.search(r"\b(durak\w*|durag\w*)\b", temiz):
        return "durak"

    if re.search(
        r"\b(kilise\w*|muze\w*|turbe\w*|kulliye\w*|hoyuk\w*|"
        r"dershane\w*|otel\w*|hastane\w*|universite\w*|fakulte\w*|"
        r"cadde\w*|sokak\w*|mahallesi|bulvari|"
        r"avm\w*|park\w*|meydan\w*|stadyum\w*)\b",
        temiz,
    ):
        return "adres"

    return "otomatik"


def konumu_coz(yer, tercih="otomatik", yer_id=None):
    tur = konum_turunu_belirle(yer, tercih)

    sonuc = {
        "anlasilan_yer": yer,
        "eslesme_sayisi": 0,
        "birden_fazla_eslesme": False,
        "konum_turu": tur,
        "cozum_turu": "bulunamadi",
        "adres_koordinati": None,
        "durak_eslesmeleri": [],
        "ayni_adli_duraklar": [],
        "geocoding_hatasi": None,
    }

    if not yer:
        return sonuc, "Yer bilgisi anlaşılamadı."

    if yer_cok_genel_mi(yer):
        sonuc["cozum_turu"] = "yetersiz_bilgi"
        return sonuc, "Yer çok genel. Cadde, mahalle veya durak adı belirt."

    kod_eslesmesi = re.search(
        r"(?<!\w)([0-9]{5})\s+kodlu\b",
        str(yer),
        flags=re.IGNORECASE,
    )

    if kod_eslesmesi is None:
        kod_eslesmesi = re.fullmatch(
            r"\s*([0-9]{5})\s*",
            str(yer),
        )

    if tur != "adres" and kod_eslesmesi:
        durak_kodu = kod_eslesmesi.group(1)

        try:
            with baglanti_ac() as baglanti:
                kayit = baglanti.execute(
                    """
                    SELECT durak_kodu, durak_adi, enlem, boylam
                    FROM duraklar
                    WHERE durak_kodu = %s
                    """,
                    (durak_kodu,),
                ).fetchone()
        except Exception as hata:
            raise HTTPException(
                status_code=503,
                detail="Durak kodu sorgulanırken veritabanına ulaşılamadı.",
            ) from hata

        sonuc["konum_turu"] = "durak"

        if kayit is None:
            return sonuc, f"{durak_kodu} kodlu durak bulunamadı."

        kod, ad, enlem, boylam = kayit

        sonuc["durak_eslesmeleri"] = [
            {
                "durak_kodu": str(kod),
                "durak_adi": ad,
                "enlem": float(enlem) if enlem is not None else None,
                "boylam": float(boylam) if boylam is not None else None,
                "eslesme_turu": "kod",
            }
        ]

        sonuc["eslesme_sayisi"] = 1
        sonuc["birden_fazla_eslesme"] = False
        sonuc["cozum_turu"] = "durak_eslesmesi"

        return sonuc, None

    kullanici_durak_istedi = (
        tercih == "durak"
        or bool(
            re.search(
                r"\b(durak\w*|durag\w*)\b",
                metni_normalize_et(yer or ""),
            )
        )
    )

    if yer_id is not None or not kullanici_durak_istedi:
        secilen = None

        if yer_id is not None:
            secilen = yer_getir(yer_id)
            katalog = {
                "durum": "kesin" if secilen else "bulunamadi",
                "yerler": [],
            }
        else:
            katalog = yer_ara(yer)

        if yer_id is not None and secilen is None:
            sonuc["cozum_turu"] = "gecersiz_yer_secimi"
            return sonuc, (
                "Seçilen yer artık bulunamıyor. Yeniden arama yap."
            )

        if katalog["durum"] == "kesin":
            if secilen is None:
                adaylar = katalog.get("yerler") or []

                if adaylar:
                    secilen = yer_getir(adaylar[0]["yer_id"])

            if secilen is None:
                sonuc["cozum_turu"] = "gecersiz_yer_secimi"
                return sonuc, "Yer kaydı değişmiş. Yeniden arama yap."

            koordinat, hata = adresi_geocode_et(secilen["ad"])
            sonuc["geocoding_hatasi"] = hata

            if hata:
                sonuc["cozum_turu"] = "servis_hatasi"
                return sonuc, (
                    "Seçilen yerin konumu doğrulanamadı. "
                    "Daha sonra tekrar dene."
                )

            if koordinat is None:
                sonuc["cozum_turu"] = "konum_dogrulanamadi"

                if tercih == "otomatik" and yer_id is None:
                    duraklar = durak_eslesmelerini_jsona_cevir(
                        durak_ara(yer),
                        yer,
                    )

                    sonuc["ayni_adli_duraklar"] = duraklar

                    if not duraklar:
                        from durak_eslestirme import durak_oner

                        sonuc["durak_onerileri"] = (
                            durak_eslesmelerini_jsona_cevir(
                                durak_oner(yer),
                                yer,
                            )
                        )

                    if duraklar or sonuc.get("durak_onerileri"):
                        return sonuc, (
                            "Adres konumu bulunamadı. "
                            "Bulunan duraklardan uygun olanı seç."
                        )

                return sonuc, (
                    "Bu yerin harita konumu bulunamadı. "
                    "Yakınındaki durak adını yaz."
                )

            sonuc["anlasilan_yer"] = secilen["ad"]
            sonuc["konum_turu"] = "adres"
            sonuc["adres_koordinati"] = koordinat
            sonuc["cozum_turu"] = "geocoding"
            sonuc["eslesme_sayisi"] = 1

            return sonuc, None

        if katalog["durum"] == "secim_gerekli":
            sonuc["konum_turu"] = "adres"
            sonuc["cozum_turu"] = "yer_secimi_gerekli"
            sonuc["yer_adaylari"] = katalog["yerler"]
            sonuc["eslesme_sayisi"] = katalog["toplam_aday"]
            sonuc["birden_fazla_eslesme"] = katalog["toplam_aday"] > 1

            return sonuc, "Birden fazla yer eşleşti; birini seç."

    duraklar = durak_eslesmelerini_jsona_cevir(
        durak_ara(yer),
        yer,
    )

    if tur == "adres":
        sonuc["ayni_adli_duraklar"] = duraklar
    else:
        sonuc["durak_eslesmeleri"] = duraklar
        sonuc["eslesme_sayisi"] = len(duraklar)
        sonuc["birden_fazla_eslesme"] = len(duraklar) > 1

        if duraklar:
            sonuc["konum_turu"] = "durak"
            sonuc["cozum_turu"] = "durak_eslesmesi"
            return sonuc, None

    acikca_durak = (
        tercih == "durak"
        or bool(
            re.search(
                r"\b(durak\w*|durag\w*)\b",
                metni_normalize_et(yer or ""),
            )
        )
    )

    if tur == "durak" and acikca_durak:
        return sonuc, (
            "İstenen durak bulunamadı; "
            "adres koordinatı durak yerine kullanılmadı."
        )

    koordinat, hata = adresi_geocode_et(yer)
    sonuc["geocoding_hatasi"] = hata

    if hata:
        sonuc["cozum_turu"] = "servis_hatasi"
        return sonuc, "Koordinat arama servisine ulaşılamadı."

    if koordinat is not None:
        sonuc["konum_turu"] = "adres"
        sonuc["adres_koordinati"] = koordinat
        sonuc["cozum_turu"] = "geocoding"

        return sonuc, None

    if tercih == "otomatik" and not sonuc["ayni_adli_duraklar"]:
        from durak_eslestirme import durak_oner

        oneriler = durak_oner(yer)

        sonuc["durak_onerileri"] = durak_eslesmelerini_jsona_cevir(
            oneriler,
            yer,
        )

    return sonuc, (
        "Adres koordinatı bulunamadı. "
        "Aynı adlı duraklar adresin konumu değildir."
        if tur == "adres" and duraklar
        else "Durak eşleşmesi veya adres koordinatı bulunamadı."
    )


@app.get("/")
def ana_sayfa():
    return {"mesaj": "Akıllı Ulaşım Asistanı API çalışıyor."}


@app.get("/saglik")
def saglik_kontrolu():
    return {"durum": "çalışıyor"}


@app.post("/geocode")
def geocode_endpoint(girdi: GeocodingRequest):
    try:
        sonuc = adresi_koordinata_cevir(girdi.adres)
    except ValueError as hata:
        raise HTTPException(
            status_code=400,
            detail=str(hata),
        )
    except GeocodingError as hata:
        raise HTTPException(
            status_code=502,
            detail=str(hata),
        )

    if sonuc is None:
        return {
            "basarili": False,
            "mesaj": "Bu adres için koordinat bulunamadı.",
        }

    return {
        "basarili": True,
        "adres": girdi.adres,
        **sonuc,
    }


@app.post("/adres-coz")
def adres_coz_api(istek: AdresCozIstegi):
    metin = istek.metin.strip()

    if not metin:
        raise HTTPException(
            status_code=422,
            detail="Adres metni boş olamaz.",
        )

    try:
        adresler = adresleri_coz(metin)
    except Exception as hata:
        kod = getattr(hata, "code", None)

        if kod is None:
            kod = getattr(hata, "status_code", None)

        if str(kod) == "429":
            raise HTTPException(
                status_code=429,
                detail="Adres çözümleme servisi kullanım sınırına ulaştı.",
            ) from hata

        raise HTTPException(
            status_code=503,
            detail=(
                "Adres çözümleme sırasında hata oluştu: "
                f"{type(hata).__name__}"
            ),
        ) from hata

    baslangic, baslangic_hatasi = konumu_coz(
        adresler.get("baslangic"),
        istek.baslangic_turu,
        istek.baslangic_yer_id,
    )

    hedef, hedef_hatasi = konumu_coz(
        adresler.get("hedef"),
        istek.hedef_turu,
        istek.hedef_yer_id,
    )

    hatalar = []

    if baslangic_hatasi:
        hatalar.append("Başlangıç: " + baslangic_hatasi)

    if hedef_hatasi:
        hatalar.append("Hedef: " + hedef_hatasi)

    return {
        "basarili": not hatalar,
        "baslangic": baslangic,
        "hedef": hedef,
        "hatalar": hatalar,
    }


@app.post("/yol-tarifi")
def yol_tarifi(istek: YolTarifiIstegi):
    soru = istek.soru.strip()

    if not soru:
        raise HTTPException(
            status_code=422,
            detail="Yol tarifi isteği boş olamaz.",
        )

    gun = None

    if istek.gun:
        gun = gunu_duzenle(istek.gun)

        if not gun:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Gün; Pazartesi, Salı, Çarşamba, Perşembe, "
                    "Cuma, Cumartesi veya Pazar olmalı."
                ),
            )

    try:
        adresler = adresleri_coz(soru)
    except Exception as hata:
        kod = getattr(hata, "code", None)

        if kod is None:
            kod = getattr(hata, "status_code", None)

        if str(kod) == "429":
            raise HTTPException(
                status_code=429,
                detail="Adres çözümleme servisi kullanım sınırına ulaştı.",
            ) from hata

        raise HTTPException(
            status_code=503,
            detail=(
                "Adres çözümleme sırasında hata oluştu: "
                f"{type(hata).__name__}"
            ),
        ) from hata

    baslangic_yeri = adresler.get("baslangic")
    hedef_yeri = adresler.get("hedef")

    if not baslangic_yeri or not hedef_yeri:
        raise HTTPException(
            status_code=422,
            detail="İstekten başlangıç ve hedef yeri anlaşılamadı.",
        )

    if yer_cok_genel_mi(baslangic_yeri):
        return {
            "basarili": False,
            "mesaj": (
                "Başlangıç yeri çok genel. "
                "Cadde, mahalle veya durak adı belirt."
            ),
            "anlasilan_baslangic": baslangic_yeri,
            "anlasilan_hedef": hedef_yeri,
        }

    if yer_cok_genel_mi(hedef_yeri):
        return {
            "basarili": False,
            "mesaj": (
                "Hedef yeri çok genel. "
                "Cadde, mahalle veya durak adı belirt."
            ),
            "anlasilan_baslangic": baslangic_yeri,
            "anlasilan_hedef": hedef_yeri,
        }

    baslangic_duraklari = durak_ara(baslangic_yeri)
    hedef_duraklari = durak_ara(hedef_yeri)

    if not baslangic_duraklari:
        return {
            "basarili": False,
            "mesaj": "Başlangıç yeriyle eşleşen durak bulunamadı.",
            "anlasilan_baslangic": baslangic_yeri,
            "anlasilan_hedef": hedef_yeri,
        }

    if not hedef_duraklari:
        return {
            "basarili": False,
            "mesaj": "Hedef yeriyle eşleşen durak bulunamadı.",
            "anlasilan_baslangic": baslangic_yeri,
            "anlasilan_hedef": hedef_yeri,
        }

    ortak_cevap = {
        "basarili": True,
        "anlasilan_baslangic": baslangic_yeri,
        "anlasilan_hedef": hedef_yeri,
        "gun": gun,
    }

    dogrudan_hatlar = dogrudan_hatlari_bul(
        baslangic_duraklari,
        hedef_duraklari,
    )

    if dogrudan_hatlar:
        secenekler = []

        for hat in dogrudan_hatlar:
            (
                hat_kodu,
                hat_adi,
                yon,
                ilk_sira,
                son_sira,
                baslangic_kodu,
                hedef_kodu,
                baslangic_durak_adi,
                hedef_durak_adi,
                durak_araligi,
            ) = hat

            durak_satirlari = hat_duraklarini_getir(
                hat_kodu,
                yon,
                ilk_sira,
                son_sira,
            )

            secenekler.append(
                {
                    "hat_kodu": hat_kodu,
                    "hat_adi": hat_adi,
                    "yon": yon,
                    "binis_duragi": {
                        "durak_kodu": baslangic_kodu,
                        "durak_adi": baslangic_durak_adi,
                    },
                    "inis_duragi": {
                        "durak_kodu": hedef_kodu,
                        "durak_adi": hedef_durak_adi,
                    },
                    "durak_sayisi": len(durak_satirlari),
                    "duraklar": duraklari_jsona_cevir(durak_satirlari),
                    "sefer_saatleri": saatleri_jsona_cevir(
                        hat_kodu,
                        yon,
                        gun,
                    ),
                    "sefer_saati_notu": sefer_saati_notunu_hazirla(
                        ilk_sira
                    ),
                }
            )

        return {
            **ortak_cevap,
            "sonuc_turu": "dogrudan",
            "secenekler": secenekler,
        }

    aktarmali_hatlar = tek_aktarmali_hatlari_bul(
        baslangic_duraklari,
        hedef_duraklari,
    )

    if not aktarmali_hatlar:
        return {
            **ortak_cevap,
            "basarili": False,
            "sonuc_turu": None,
            "mesaj": "Doğrudan veya tek aktarmalı güzergâh bulunamadı.",
            "secenekler": [],
        }

    secenekler = []

    for secenek in aktarmali_hatlar:
        (
            hat1_kodu,
            hat1_adi,
            yon1,
            bas_sira,
            aktarma1_sira,
            bas_kodu,
            aktarma1_kodu,
            bas_adi,
            hat2_kodu,
            hat2_adi,
            yon2,
            aktarma2_sira,
            hedef_sira,
            hedef_kodu,
            aktarma1_adi,
            aktarma2_adi,
            yuru_mesafesi,
            toplam_durak_araligi,
        ) = secenek

        birinci_etap = hat_duraklarini_getir(
            hat1_kodu,
            yon1,
            bas_sira,
            aktarma1_sira,
        )

        ikinci_etap = hat_duraklarini_getir(
            hat2_kodu,
            yon2,
            aktarma2_sira,
            hedef_sira,
        )

        secenekler.append(
            {
                "birinci_hat": {
                    "hat_kodu": hat1_kodu,
                    "hat_adi": hat1_adi,
                    "yon": yon1,
                    "duraklar": duraklari_jsona_cevir(birinci_etap),
                    "sefer_saatleri": saatleri_jsona_cevir(
                        hat1_kodu,
                        yon1,
                        gun,
                    ),
                    "sefer_saati_notu": sefer_saati_notunu_hazirla(
                        bas_sira
                    ),
                },
                "aktarma": {
                    "inilecek_durak": aktarma1_adi,
                    "binilecek_durak": aktarma2_adi,
                    "yurume_mesafesi_metre": round(yuru_mesafesi),
                },
                "ikinci_hat": {
                    "hat_kodu": hat2_kodu,
                    "hat_adi": hat2_adi,
                    "yon": yon2,
                    "duraklar": duraklari_jsona_cevir(ikinci_etap),
                    "sefer_saatleri": saatleri_jsona_cevir(
                        hat2_kodu,
                        yon2,
                        gun,
                    ),
                    "sefer_saati_notu": sefer_saati_notunu_hazirla(
                        aktarma2_sira
                    ),
                },
                "bilgi": (
                    "Aktarmalı sefer saatlerinin birbirine uygunluğu "
                    "hesaplanmıyor."
                ),
            }
        )

    return {
        **ortak_cevap,
        "sonuc_turu": "tek_aktarma",
        "secenekler": secenekler,
    }


@app.post(
    "/rota/dogal-dil",
    tags=["Backend ve Rota"],
    summary="Doğal dildeki yolculuk isteğinden rota bul",
)
def dogal_dilden_rota(istek: DogalDilRotaIstegi):
    from rota_motoru import adaylari_bul, rota_bul

    baslama = perf_counter()

    if not istek.soru.strip():
        raise HTTPException(
            status_code=422,
            detail="Soru boş olamaz.",
        )

    try:
        yerler = adresleri_coz(istek.soru)
    except Exception as hata:
        kod = (
            getattr(hata, "code", None)
            or getattr(hata, "status_code", None)
        )

        raise HTTPException(
            status_code=429 if str(kod) == "429" else 503,
            detail="Adres çözümleme servisi şu an kullanılamıyor.",
        ) from hata

    if not isinstance(yerler, dict):
        yerler = {}

    baslangic, bas_hata = konumu_coz(
        yerler.get("baslangic"),
        istek.baslangic_turu,
        istek.baslangic_yer_id,
    )

    hedef, hedef_hata = konumu_coz(
        yerler.get("hedef"),
        istek.hedef_turu,
        istek.hedef_yer_id,
    )

    ortak = {
        "baslangic": baslangic,
        "hedef": hedef,
    }

    hatalar = [
        f"{etiket}: {hata}"
        for etiket, hata in (
            ("Başlangıç", bas_hata),
            ("Hedef", hedef_hata),
        )
        if hata
    ]

    def bitir(sonuc):
        return {
            **ortak,
            **sonuc,
            "hatalar": hatalar,
            "islem_suresi_ms": round(
                (perf_counter() - baslama) * 1000,
                3,
            ),
        }

    if hatalar:
        return bitir(
            {
                "basarili": False,
                "sonuc_turu": None,
                "secenekler": [],
            }
        )

    bk = {
        str(d["durak_kodu"])
        for d in baslangic["durak_eslesmeleri"]
    }

    hk = {
        str(d["durak_kodu"])
        for d in hedef["durak_eslesmeleri"]
    }

    if bk and bk == hk:
        tek = len(bk) == 1

        return bitir(
            {
                "basarili": tek,
                "sonuc_turu": (
                    "ayni_durak"
                    if tek
                    else "konum_secimi_gerekli"
                ),
                "secenekler": [],
                "mesaj": (
                    "Başlangıç ve hedef aynı durak."
                    if tek
                    else (
                        "Başlangıç ve hedef aynı durak adaylarıyla "
                        "eşleşti. Farklı konum belirt."
                    )
                ),
            }
        )

    satirlar, _ = _duraklari_yukle()

    bas = adaylari_bul(
        baslangic,
        satirlar,
        istek.yaricap_metre,
    )

    son = adaylari_bul(
        hedef,
        satirlar,
        istek.yaricap_metre,
    )

    for konum, adaylar in (
        (baslangic, bas),
        (hedef, son),
    ):
        if konum["cozum_turu"] == "geocoding":
            konum["arama_kapsami"] = (
                "Harita kaydının alan sınırları içindeki duraklar."
                if any(d.get("alan_icinde") for d in adaylar)
                else (
                    "Alan içi durak eşleşmesi yok; harita noktasının "
                    "çevresi aranıyor. Tüm bölgeyi kapsadığı varsayılmaz."
                )
            )

    cevap = rota_bul(
        bas,
        son,
        istek.sonuc_limiti,
    )

    return bitir(
        {
            **cevap,
            "baslangic_aday_sayisi": len(bas),
            "hedef_aday_sayisi": len(son),
            "adaylar_kisitlandi": False,
        }
    )
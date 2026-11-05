import re
from geocoding import adresi_koordinata_cevir, GeocodingError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

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


class GeocodingRequest(BaseModel):
    adres: str


@app.post("/geocode")
def geocode_endpoint(girdi: GeocodingRequest):
    try:
        sonuc = adresi_koordinata_cevir(girdi.adres)
    except ValueError as hata:
        raise HTTPException(status_code=400, detail=str(hata))
    except GeocodingError as hata:
        raise HTTPException(status_code=502, detail=str(hata))

    if sonuc is None:
        return {
            "basarili": False,
            "mesaj": "Bu adres için koordinat bulunamadı."
        }

    return {
        "basarili": True,
        "adres": girdi.adres,
        **sonuc
    }


class YolTarifiIstegi(BaseModel):
    soru: str
    gun: str | None = None


class AdresCozIstegi(BaseModel):
    metin: str


GUNLER = [
    "Pazartesi",
    "Salı",
    "Çarşamba",
    "Perşembe",
    "Cuma",
    "Cumartesi",
    "Pazar",
]


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


GENEL_YERLER = {
    "malatya",
    "yesilyurt",
    "battalgazi",
    "merkez",
    "turkiye",
}


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
            "saat": saat.strftime("%H:%M")
            if hasattr(saat, "strftime")
            else str(saat),
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


@app.get("/")
def ana_sayfa():
    return {"mesaj": "Akıllı Ulaşım Asistanı API çalışıyor."}


@app.get("/saglik")
def saglik_kontrolu():
    return {"durum": "çalışıyor"}


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
        raise HTTPException(
            status_code=503,
            detail=(
                "Adres çözümleme sırasında hata oluştu: "
                f"{type(hata).__name__}"
            ),
        ) from hata

    baslangic_yeri = adresler.get("baslangic")
    hedef_yeri = adresler.get("hedef")

    baslangic_yeri_genel = yer_cok_genel_mi(baslangic_yeri)
    hedef_yeri_genel = yer_cok_genel_mi(hedef_yeri)

    baslangic_duraklari = (
        durak_ara(baslangic_yeri)
        if baslangic_yeri and not baslangic_yeri_genel
        else []
    )
    hedef_duraklari = (
        durak_ara(hedef_yeri)
        if hedef_yeri and not hedef_yeri_genel
        else []
    )

    baslangic_koordinati = None
    if (
        baslangic_yeri
        and not baslangic_yeri_genel
        and not baslangic_duraklari
    ):
        baslangic_koordinati, _ = adresi_geocode_et(baslangic_yeri)

    hedef_koordinati = None
    if hedef_yeri and not hedef_yeri_genel and not hedef_duraklari:
        hedef_koordinati, _ = adresi_geocode_et(hedef_yeri)

    hatalar = []

    if not baslangic_yeri:
        hatalar.append("Başlangıç yeri anlaşılamadı.")
    elif baslangic_yeri_genel:
        hatalar.append(
            "Başlangıç yeri çok genel. Cadde, mahalle veya durak adı belirt."
        )
    elif not baslangic_duraklari and not baslangic_koordinati:
        hatalar.append(
            "Başlangıç yeri için durak eşleşmesi veya koordinat bulunamadı."
        )

    if not hedef_yeri:
        hatalar.append("Hedef yeri anlaşılamadı.")
    elif hedef_yeri_genel:
        hatalar.append(
            "Hedef yeri çok genel. Cadde, mahalle veya durak adı belirt."
        )
    elif not hedef_duraklari and not hedef_koordinati:
        hatalar.append(
            "Hedef yeri için durak eşleşmesi veya koordinat bulunamadı."
        )

    baslangic_cozum_turu = "bulunamadi"
    if baslangic_yeri_genel:
        baslangic_cozum_turu = "yetersiz_bilgi"
    elif baslangic_duraklari:
        baslangic_cozum_turu = "durak_eslesmesi"
    elif baslangic_koordinati:
        baslangic_cozum_turu = "geocoding"

    hedef_cozum_turu = "bulunamadi"
    if hedef_yeri_genel:
        hedef_cozum_turu = "yetersiz_bilgi"
    elif hedef_duraklari:
        hedef_cozum_turu = "durak_eslesmesi"
    elif hedef_koordinati:
        hedef_cozum_turu = "geocoding"

    return {
        "basarili": len(hatalar) == 0,
        "baslangic": {
            "anlasilan_yer": baslangic_yeri,
            "eslesme_sayisi": len(baslangic_duraklari),
            "birden_fazla_eslesme": len(baslangic_duraklari) > 1,
            "cozum_turu": baslangic_cozum_turu,
            "adres_koordinati": baslangic_koordinati,
            "durak_eslesmeleri": durak_eslesmelerini_jsona_cevir(
                baslangic_duraklari,
                baslangic_yeri,
            ),
        },
        "hedef": {
            "anlasilan_yer": hedef_yeri,
            "eslesme_sayisi": len(hedef_duraklari),
            "birden_fazla_eslesme": len(hedef_duraklari) > 1,
            "cozum_turu": hedef_cozum_turu,
            "adres_koordinati": hedef_koordinati,
            "durak_eslesmeleri": durak_eslesmelerini_jsona_cevir(
                hedef_duraklari,
                hedef_yeri,
            ),
        },
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
                "Başlangıç yeri çok genel. Cadde, mahalle veya durak adı belirt."
            ),
            "anlasilan_baslangic": baslangic_yeri,
            "anlasilan_hedef": hedef_yeri,
        }

    if yer_cok_genel_mi(hedef_yeri):
        return {
            "basarili": False,
            "mesaj": "Hedef yeri çok genel. Cadde, mahalle veya durak adı belirt.",
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
                    "binilecek_durak": aktarma1_adi,
                    "inilecek_durak": aktarma2_adi,
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
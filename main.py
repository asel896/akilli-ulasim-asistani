import re
from typing import Literal
from geocoding import adresi_koordinata_cevir, GeocodingError
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rota_api import router as rota_router

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

app.include_router(rota_router)

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
    baslangic_turu: Literal["otomatik", "durak", "adres"] = "otomatik"
    hedef_turu: Literal["otomatik", "durak", "adres"] = "otomatik"


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


def konum_turunu_belirle(yer, tercih="otomatik"):
    if tercih != "otomatik":
        return tercih
    temiz = metni_normalize_et(yer or "")
    if re.search(r"\b(durak\w*|durag\w*)\b", temiz):
        return "durak"

    if re.search(
        r"\b(kilise\w*|muze\w*|turbe\w*|kulliye\w*|hoyuk\w*|"
        r"dershane\w*|otel\w*|hastane\w*|universite\w*|fakulte\w*|"
        r"cadde\w*|sokak\w*|mahallesi|bulvari)\b", temiz
    ):
        return "adres"
    return "durak"


def konumu_coz(yer, tercih="otomatik"):
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

    duraklar = durak_eslesmelerini_jsona_cevir(durak_ara(yer), yer)
    if tur == "adres":
       
        sonuc["ayni_adli_duraklar"] = duraklar
    else:
        sonuc["durak_eslesmeleri"] = duraklar
        sonuc["eslesme_sayisi"] = len(duraklar)
        sonuc["birden_fazla_eslesme"] = len(duraklar) > 1
        if duraklar:
            sonuc["cozum_turu"] = "durak_eslesmesi"
            return sonuc, None

    if tur == "durak":
        return sonuc, "İstenen durak bulunamadı; adres koordinatı durak yerine kullanılmadı."

    koordinat, hata = adresi_geocode_et(yer)
    sonuc["geocoding_hatasi"] = hata
    if hata:
        sonuc["cozum_turu"] = "servis_hatasi"
        return sonuc, "Koordinat arama servisine ulaşılamadı."
    if koordinat is not None:
        sonuc["adres_koordinati"] = koordinat
        sonuc["cozum_turu"] = "geocoding"
        return sonuc, None
    return sonuc, (
        "Adres koordinatı bulunamadı. Aynı adlı duraklar adresin konumu değildir."
        if tur == "adres" and duraklar
        else "Durak eşleşmesi veya adres koordinatı bulunamadı."
    )

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
            print("Gemini 429:", getattr(hata, "response_json", None) or getattr(hata, "details", None) or str(hata), flush=True)
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
        adresler.get("baslangic"), istek.baslangic_turu
    )
    hedef, hedef_hatasi = konumu_coz(
        adresler.get("hedef"), istek.hedef_turu
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


from time import perf_counter
from pydantic import Field
from rota_api import (
    Koordinat,
    _duraklari_yukle,
    _koordinat_adaylari,
)


class DogalDilRotaIstegi(BaseModel):
    soru: str = Field(min_length=1, max_length=1000)

    baslangic_turu: Literal["otomatik", "durak", "adres"] = "otomatik"
    hedef_turu: Literal["otomatik", "durak", "adres"] = "otomatik"

    yaricap_metre: float = Field(
        default=1000,
        gt=0,
        le=5000,
        allow_inf_nan=False,
    )

    aday_limiti: int = Field(default=10, ge=1, le=50)
    sonuc_limiti: int = Field(default=5, ge=1, le=50)


def _rota_adaylarini_hazirla(konum, satirlar, istek):
    if konum["cozum_turu"] == "durak_eslesmesi":
        
        adaylar = [
            {
                **durak,
                "mesafe_metre": None,
            }
            for durak in konum["durak_eslesmeleri"]
        ]

        return adaylar, len(adaylar)

    if konum["cozum_turu"] == "geocoding":
        nokta = Koordinat(
            enlem=konum["adres_koordinati"]["enlem"],
            boylam=konum["adres_koordinati"]["boylam"],
        )

        return _koordinat_adaylari(
            nokta,
            satirlar,
            istek.yaricap_metre,
            istek.aday_limiti,
        )

    return [], 0


@app.post(
    "/rota/dogal-dil",
    tags=["Backend ve Rota"],
    summary="Doğal dildeki yolculuk isteğinden doğrudan rota bul",
)
def dogal_dilden_rota(istek: DogalDilRotaIstegi):
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

        if str(kod) == "429":
            raise HTTPException(
                status_code=429,
                detail="Adres çözümleme servisi kullanım sınırına ulaştı.",
            ) from hata

        raise HTTPException(
            status_code=503,
            detail="Adres çözümleme servisine ulaşılamadı.",
        ) from hata

    baslangic, bas_hata = konumu_coz(
        yerler.get("baslangic"),
        istek.baslangic_turu,
    )

    hedef, hedef_hata = konumu_coz(
        yerler.get("hedef"),
        istek.hedef_turu,
    )

    hatalar = []

    if bas_hata:
        hatalar.append("Başlangıç: " + bas_hata)

    if hedef_hata:
        hatalar.append("Hedef: " + hedef_hata)

    ortak = {
        "baslangic": baslangic,
        "hedef": hedef,
    }

    if hatalar:
        return {
            **ortak,
            "basarili": False,
            "sonuc_turu": None,
            "secenekler": [],
            "hatalar": hatalar,
            "islem_suresi_ms": round(
                (perf_counter() - baslama) * 1000,
                3,
            ),
        }

    satirlar = ()

    if any(
        konum["cozum_turu"] == "geocoding"
        for konum in (baslangic, hedef)
    ):
        satirlar, _ = _duraklari_yukle()

    bas_adaylar, bas_toplam = _rota_adaylarini_hazirla(
        baslangic,
        satirlar,
        istek,
    )

    hedef_adaylar, hedef_toplam = _rota_adaylarini_hazirla(
        hedef,
        satirlar,
        istek,
    )

    bas_sozluk = {
        str(durak["durak_kodu"]): durak
        for durak in bas_adaylar
    }

    hedef_sozluk = {
        str(durak["durak_kodu"]): durak
        for durak in hedef_adaylar
    }

    def satira_cevir(adaylar):
        return [
            (
                str(durak["durak_kodu"]),
                durak["durak_adi"],
                durak["enlem"],
                durak["boylam"],
            )
            for durak in adaylar
        ]

        hatlar = []

    if bas_adaylar and hedef_adaylar:
        hatlar = dogrudan_hatlari_bul(
            satira_cevir(bas_adaylar),
            satira_cevir(hedef_adaylar),
        )

    if not hatlar:
        return _dogal_dil_aktarmali_sonuc(
            ortak,
            bas_adaylar,
            hedef_adaylar,
            bas_toplam,
            hedef_toplam,
            istek,
            baslama,
        )

    secenekler = []

    for kayit in hatlar:
        (
            kod,
            ad,
            yon,
            ilk,
            son,
            binis_kodu,
            inis_kodu,
            _,
            _,
            _,
        ) = kayit

        if str(binis_kodu) == str(inis_kodu):
            continue

        binis = dict(bas_sozluk[str(binis_kodu)])
        inis = dict(hedef_sozluk[str(inis_kodu)])

        toplam = (
            (binis["mesafe_metre"] or 0)
            + (inis["mesafe_metre"] or 0)
        )

        toplam_biliniyor = all(
            durak["mesafe_metre"] is not None
            for durak in (binis, inis)
        )

        for durak in (binis, inis):
            if durak["mesafe_metre"] is not None:
                durak["mesafe_metre"] = round(
                    durak["mesafe_metre"],
                    2,
                )

        secenekler.append(
            {
                "hat_kodu": kod,
                "hat_adi": ad,
                "yon": yon,
                "binis_duragi": binis,
                "inis_duragi": inis,
                "binis_sirasi": ilk,
                "inis_sirasi": son,
                "durak_araligi": son - ilk,
                "toplam_erisim_mesafesi_metre": (
                    round(toplam, 2)
                    if toplam_biliniyor
                    else None
                ),
                "_sira": (
                    toplam,
                    son - ilk,
                    kod,
                    yon,
                    str(binis_kodu),
                    str(inis_kodu),
                    ilk,
                    son,
                ),
            }
        )

    secenekler.sort(key=lambda secenek: secenek["_sira"])

    bulunan = len(secenekler)
    secenekler = secenekler[:istek.sonuc_limiti]

    for secenek in secenekler:
        secenek.pop("_sira")

    return {
        **ortak,
        "basarili": bool(secenekler),
        "sonuc_turu": "dogrudan" if secenekler else None,
        "baslangic_aday_sayisi": len(bas_adaylar),
        "hedef_aday_sayisi": len(hedef_adaylar),
        "adaylar_kisitlandi": (
            bas_toplam > len(bas_adaylar)
            or hedef_toplam > len(hedef_adaylar)
        ),
        "bulunan_secenek_sayisi": bulunan,
        "secenekler": secenekler,
        "hatalar": [],
        "mesaj": (
            "Doğrudan hat bulundu."
            if secenekler
            else (
                "Seçilen durak adayları arasında "
                "doğrudan hat bulunamadı."
            )
        ),
        "bilgi": (
            "Yalnız doğrudan hatlar aranır; "
            "sefer saatleri değerlendirilmez. "
            "Mesafe, adres koordinatı varsa kuş uçuşudur. "
            "Durak belirtilmişse kullanıcının durağa uzaklığı "
            "bilinmediğinden null gösterilir."
        ),
        "islem_suresi_ms": round(
            (perf_counter() - baslama) * 1000,
            3,
        ),
    }

def _dogal_dil_aktarmali_sonuc(
    ortak,
    bas_adaylar,
    hedef_adaylar,
    bas_toplam,
    hedef_toplam,
    istek,
    baslama,
):
    bas_sozluk = {
        str(d["durak_kodu"]): d
        for d in bas_adaylar
    }
    hedef_sozluk = {
        str(d["durak_kodu"]): d
        for d in hedef_adaylar
    }

    def satirlar(adaylar):
        return [
            (
                str(d["durak_kodu"]),
                d["durak_adi"],
                d["enlem"],
                d["boylam"],
            )
            for d in adaylar
        ]

    hatlar = []

    if bas_adaylar and hedef_adaylar:
        hatlar = tek_aktarmali_hatlari_bul(
            satirlar(bas_adaylar),
            satirlar(hedef_adaylar),
        )

    secenekler = []

    for kayit in hatlar:
        (
            hat1,
            ad1,
            yon1,
            bas_sira,
            akt1_sira,
            bas_kod,
            akt1_kod,
            bas_ad,
            hat2,
            ad2,
            yon2,
            akt2_sira,
            hedef_sira,
            hedef_kod,
            akt1_ad,
            akt2_ad,
            aktarma_mesafesi,
            durak_araligi,
        ) = kayit

        binis = dict(bas_sozluk[str(bas_kod)])
        inis = dict(hedef_sozluk[str(hedef_kod)])

        aktarma_mesafesi = float(aktarma_mesafesi)

        bilinen_mesafe = (
            (binis["mesafe_metre"] or 0)
            + (inis["mesafe_metre"] or 0)
            + aktarma_mesafesi
        )

        tumu_biliniyor = all(
            d["mesafe_metre"] is not None
            for d in (binis, inis)
        )

        for durak in (binis, inis):
            if durak["mesafe_metre"] is not None:
                durak["mesafe_metre"] = round(
                    durak["mesafe_metre"], 2
                )

        secenekler.append(
            {
                "binis_duragi": binis,
                "inis_duragi": inis,
                "birinci_hat": {
                    "hat_kodu": hat1,
                    "hat_adi": ad1,
                    "yon": yon1,
                    "binis_sirasi": bas_sira,
                    "inis_sirasi": akt1_sira,
                },
                "aktarma": {
                    "inilecek_durak": {
                        "durak_kodu": str(akt1_kod),
                        "durak_adi": akt1_ad,
                    },
                "binilecek_durak": _aktarma_binis_duragini_getir(
                    hat2, yon2, akt2_sira
                    ),
                    "yaklasik_mesafe_metre": round(
                        aktarma_mesafesi, 2
                    ),
                },
                "ikinci_hat": {
                    "hat_kodu": hat2,
                    "hat_adi": ad2,
                    "yon": yon2,
                    "binis_sirasi": akt2_sira,
                    "inis_sirasi": hedef_sira,
                },
                "toplam_durak_araligi": durak_araligi,
                "toplam_erisim_ve_aktarma_mesafesi_metre": (
                    round(bilinen_mesafe, 2)
                    if tumu_biliniyor
                    else None
                ),
                "_sira": (
                    bilinen_mesafe,
                    durak_araligi,
                    hat1,
                    yon1,
                    hat2,
                    yon2,
                ),
            }
        )

    secenekler.sort(key=lambda s: s["_sira"])

    bulunan = len(secenekler)
    secenekler = secenekler[:istek.sonuc_limiti]

    for secenek in secenekler:
        secenek.pop("_sira")

    return {
        **ortak,
        "basarili": bool(secenekler),
        "sonuc_turu": (
            "tek_aktarma" if secenekler else None
        ),
        "baslangic_aday_sayisi": len(bas_adaylar),
        "hedef_aday_sayisi": len(hedef_adaylar),
        "adaylar_kisitlandi": (
            bas_toplam > len(bas_adaylar)
            or hedef_toplam > len(hedef_adaylar)
        ),
        "bulunan_secenek_sayisi": bulunan,
        "secenekler": secenekler,
        "hatalar": [],
        "mesaj": (
            "Tek aktarmalı seçenek bulundu."
            if secenekler
            else (
                "Arama sınırları içinde doğrudan veya "
                "tek aktarmalı seçenek bulunamadı."
            )
        ),
        "bilgi": (
            "Mevcut aktarma aramasının aday ve sonuç "
            "sınırları geçerlidir. Mesafeler yaklaşık "
            "olup yürünebilir yol garantisi vermez. "
            "Sefer saatlerinin birbirine uygunluğu "
            "hesaplanmaz."
        ),
        "islem_suresi_ms": round(
            (perf_counter() - baslama) * 1000,
            3,
        ),
    }

def _aktarma_binis_duragini_getir(hat_kodu, yon, sira):
    duraklar = hat_duraklarini_getir(
        hat_kodu, yon, sira, sira
    )

    if len(duraklar) != 1:
        raise HTTPException(
            status_code=503,
            detail="Aktarma biniş durağı veritabanından kesin olarak belirlenemedi."
        )

    _, durak_kodu, durak_adi = duraklar[0]

    return {
        "durak_kodu": str(durak_kodu),
        "durak_adi": durak_adi,
    }
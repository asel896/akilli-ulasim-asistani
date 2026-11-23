"""Haversine yakın durak araması ve hat–durak eşleştirme API'si."""

import logging
import math
import time
from threading import Lock
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Response

from db import baglanti_ac


router = APIRouter(tags=["Backend ve Rota"])

_log = logging.getLogger(__name__)
_kilit = Lock()
_onbellek = ()
_yuklenme = 0.0


def haversine_metre(enlem1, boylam1, enlem2, boylam2):
    """İki koordinat arasındaki yaklaşık kuş uçuşu mesafeyi hesaplar."""
    degerler = tuple(
        map(float, (enlem1, boylam1, enlem2, boylam2))
    )

    if not all(math.isfinite(x) for x in degerler):
        raise ValueError("Koordinatlar sonlu sayı olmalı.")

    for i, deger in enumerate(degerler):
        sinir = 90 if i % 2 == 0 else 180
        if abs(deger) > sinir:
            raise ValueError("Koordinatlar geçerli aralıkta olmalı.")

    lat1, lon1, lat2, lon2 = map(math.radians, degerler)

    a = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin((lon2 - lon1) / 2) ** 2
    )

    a = min(1.0, max(0.0, a))

    return 6371008.8 * 2 * math.asin(math.sqrt(a))


def _calistir(baglanti, sql, parametreler=()):
    try:
        return baglanti.execute(sql, parametreler).fetchall()
    except Exception as hata:
        _log.exception("Rota veritabanı sorgusu başarısız.")
        raise HTTPException(
            status_code=503,
            detail="Ulaşım verileri şu an okunamıyor.",
        ) from hata


def _sorgula(sql, parametreler=()):
    try:
        with baglanti_ac() as baglanti:
            return _calistir(baglanti, sql, parametreler)
    except HTTPException:
        raise
    except Exception as hata:
        _log.exception("Rota veritabanı bağlantısı başarısız.")
        raise HTTPException(
            status_code=503,
            detail="Ulaşım veritabanına ulaşılamıyor.",
        ) from hata


def _duraklari_yukle():
    """Geçerli koordinatlı durakları 60 saniye önbellekte tutar."""
    global _onbellek, _yuklenme

    with _kilit:
        if _yuklenme and time.monotonic() - _yuklenme < 60:
            return _onbellek, True

        satirlar = _sorgula(
            """
            SELECT
                d.durak_kodu,
                d.durak_adi,
                d.enlem,
                d.boylam
            FROM duraklar AS d
            WHERE d.enlem IS NOT NULL
              AND d.boylam IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM hat_duraklar AS hd
                  JOIN hatlar AS h
                    ON h.hat_kodu = hd.hat_kodu
                  WHERE hd.durak_kodu = d.durak_kodu
                    AND h.hizmet_turu IS DISTINCT FROM 'gorevli'
              )
            ORDER BY d.durak_kodu
            """
        )

        temiz = []

        for kod, ad, lat, lon in satirlar:
            try:
                lat = float(lat)
                lon = float(lon)

                haversine_metre(lat, lon, lat, lon)
            except (ValueError, TypeError, OverflowError):
                continue

            temiz.append((str(kod), ad, lat, lon))

        _onbellek = tuple(temiz)
        _yuklenme = time.monotonic()

        return _onbellek, False


def _sure(response, baslangic):
    """Endpoint içindeki işlem süresini ölçer; ağ süresini kapsamaz."""
    milisaniye = (time.perf_counter() - baslangic) * 1000

    response.headers["Server-Timing"] = (
        f"backend;dur={milisaniye:.3f}"
    )

    return round(milisaniye, 3)


@router.get(
    "/duraklar/yakin",
    summary="Koordinata yakın durakları mesafeye göre sırala",
)
def yakin_duraklar(
    response: Response,
    enlem: Annotated[
        float,
        Query(ge=-90, le=90, allow_inf_nan=False),
    ],
    boylam: Annotated[
        float,
        Query(ge=-180, le=180, allow_inf_nan=False),
    ],
    yaricap_metre: Annotated[
        float,
        Query(gt=0, le=10000, allow_inf_nan=False),
    ] = 1000,
    limit: Annotated[int, Query(ge=1, le=50)] = 5,
):
    baslangic = time.perf_counter()

    satirlar, onbellekten = _duraklari_yukle()
    adaylar = []

    for kod, ad, lat, lon in satirlar:
        mesafe = haversine_metre(enlem, boylam, lat, lon)

        if mesafe <= yaricap_metre:
            adaylar.append((mesafe, kod, ad, lat, lon))

   
    adaylar.sort(key=lambda satir: (satir[0], satir[1]))

    sonuc = [
        {
            "durak_kodu": kod,
            "durak_adi": ad,
            "enlem": lat,
            "boylam": lon,
            "mesafe_metre": round(mesafe, 2),
        }
        for mesafe, kod, ad, lat, lon in adaylar[:limit]
    ]

    return {
        "basarili": True,
        "duraklar": sonuc,
        "bulunan_durak_sayisi": len(adaylar),
        "gosterilen_durak_sayisi": len(sonuc),
        "yaricap_metre": yaricap_metre,
        "onbellekten": onbellekten,
        "islem_suresi_ms": _sure(response, baslangic),
        "mesafe_notu": (
            "Kuş uçuşu yaklaşık mesafedir; yürünebilir yol "
            "veya canlı sefer garantisi değildir."
        ),
    }


@router.get(
    "/duraklar/{durak_kodu}/hatlar",
    summary="Duraktan geçen hatları yön ve sıra ile getir",
)
def duragin_hatlari(durak_kodu: str, response: Response):
    baslangic = time.perf_counter()

    durak = _sorgula(
        """
        SELECT durak_kodu, durak_adi
        FROM duraklar
        WHERE durak_kodu = %s
        """,
        (durak_kodu,),
    )

    if not durak:
        raise HTTPException(
            status_code=404,
            detail="Durak bulunamadı.",
        )

    satirlar = _sorgula(
        """
        SELECT DISTINCT
            h.hat_kodu,
            h.hat_adi,
            hd.yon,
            hd.sira
        FROM hat_duraklar AS hd
        JOIN hatlar AS h
          ON h.hat_kodu = hd.hat_kodu
        WHERE hd.durak_kodu = %s
          AND h.hizmet_turu IS DISTINCT FROM 'gorevli'
        ORDER BY h.hat_kodu, hd.yon, hd.sira
        """,
        (durak_kodu,),
    )

    return {
        "basarili": True,
        "durak_kodu": str(durak[0][0]),
        "durak_adi": durak[0][1],
        "hatlar": [
            {
                "hat_kodu": kod,
                "hat_adi": ad,
                "yon": yon,
                "sira": sira,
            }
            for kod, ad, yon, sira in satirlar
        ],
        "islem_suresi_ms": _sure(response, baslangic),
    }


@router.get(
    "/hatlar/{hat_kodu}/duraklar",
    summary="Hattın gidiş ve dönüş duraklarını sırasıyla getir",
)
def hattin_duraklari(
    hat_kodu: str,
    response: Response,
    yon: Literal["gidis", "donus"] | None = None,
):
    baslangic = time.perf_counter()
    kod = hat_kodu.strip().upper()

    hat = _sorgula(
        """
        SELECT hat_kodu, hat_adi
        FROM hatlar
        WHERE hat_kodu = %s
        """,
        (kod,),
    )

    if not hat:
        raise HTTPException(
            status_code=404,
            detail="Hat bulunamadı.",
        )

    satirlar = _sorgula(
        """
        SELECT
            hd.yon,
            hd.sira,
            d.durak_kodu,
            d.durak_adi,
            d.enlem,
            d.boylam
        FROM hat_duraklar AS hd
        JOIN duraklar AS d
          ON d.durak_kodu = hd.durak_kodu
        WHERE hd.hat_kodu = %s
          AND (%s::varchar IS NULL OR hd.yon = %s)
        ORDER BY hd.yon, hd.sira, d.durak_kodu
        """,
        (kod, yon, yon),
    )

    yonler = {
        "gidis": [],
        "donus": [],
    }

    for kayit_yonu, sira, durak_kodu, ad, lat, lon in satirlar:
        yonler.setdefault(kayit_yonu, []).append(
            {
                "sira": sira,
                "durak_kodu": str(durak_kodu),
                "durak_adi": ad,
                "enlem": float(lat) if lat is not None else None,
                "boylam": float(lon) if lon is not None else None,
            }
        )

    return {
        "basarili": True,
        "hat_kodu": hat[0][0],
        "hat_adi": hat[0][1],
        "yonler": (
            {yon: yonler.get(yon, [])}
            if yon
            else yonler
        ),
        "islem_suresi_ms": _sure(response, baslangic),
        "bilgi": (
            "Boş yön, veritabanında o yönde durak kaydı "
            "olmadığını gösterir; ters sıra üretilmez."
        ),
    }

from pydantic import BaseModel, Field


class Koordinat(BaseModel):
    enlem: float = Field(
        ge=-90,
        le=90,
        allow_inf_nan=False,
    )
    boylam: float = Field(
        ge=-180,
        le=180,
        allow_inf_nan=False,
    )


class KoordinatRotaIstegi(BaseModel):
    baslangic: Koordinat
    hedef: Koordinat

    yaricap_metre: float = Field(
        default=1000,
        gt=0,
        le=5000,
        allow_inf_nan=False,
    )

    aday_limiti: int = Field(default=10, ge=1, le=50)
    sonuc_limiti: int = Field(default=10, ge=1, le=50)


def _koordinat_adaylari(nokta, satirlar, yaricap, limit):
    bulunan = []

    for kod, ad, lat, lon in satirlar:
        mesafe = haversine_metre(
            nokta.enlem,
            nokta.boylam,
            lat,
            lon,
        )

        if mesafe <= yaricap:
            bulunan.append(
                {
                    "durak_kodu": str(kod),
                    "durak_adi": ad,
                    "enlem": lat,
                    "boylam": lon,
                    "mesafe_metre": mesafe,
                }
            )

    bulunan.sort(
        key=lambda durak: (
            durak["mesafe_metre"],
            durak["durak_kodu"],
        )
    )

    return bulunan[:limit], len(bulunan)


@router.post(
    "/rota/koordinat",
    summary="İki koordinat arasında doğrudan hat bul",
)
def koordinattan_rota(
    istek: KoordinatRotaIstegi,
    response: Response,
):
    baslama = time.perf_counter()

    satirlar, onbellekten = _duraklari_yukle()

    bas_adaylar, bas_sayi = _koordinat_adaylari(
        istek.baslangic,
        satirlar,
        istek.yaricap_metre,
        istek.aday_limiti,
    )

    hedef_adaylar, hedef_sayi = _koordinat_adaylari(
        istek.hedef,
        satirlar,
        istek.yaricap_metre,
        istek.aday_limiti,
    )

    ortak = {
        "baslangic_yaricapindaki_durak": bas_sayi,
        "hedef_yaricapindaki_durak": hedef_sayi,
        "baslangic_aday_sayisi": len(bas_adaylar),
        "hedef_aday_sayisi": len(hedef_adaylar),
        "adaylar_kisitlandi": (
            bas_sayi > len(bas_adaylar)
            or hedef_sayi > len(hedef_adaylar)
        ),
        "onbellekten": onbellekten,
        "mesafe_notu": (
            "Mesafeler kuş uçuşudur; "
            "yürünebilir yol mesafesi değildir."
        ),
        "siralama": (
            "Toplam kuş uçuşu erişim mesafesi, "
            "ardından durak aralığı."
        ),
    }

    secenekler = []

    if bas_adaylar and hedef_adaylar:
        bas_sozluk = {
            durak["durak_kodu"]: durak
            for durak in bas_adaylar
        }

        hedef_sozluk = {
            durak["durak_kodu"]: durak
            for durak in hedef_adaylar
        }

        satirlar = _sorgula(
            """
            SELECT DISTINCT
                h.hat_kodu,
                h.hat_adi,
                b.yon,
                b.durak_kodu,
                i.durak_kodu,
                b.sira,
                i.sira
            FROM hat_duraklar AS b
            JOIN hat_duraklar AS i
              ON i.hat_kodu = b.hat_kodu
             AND i.yon = b.yon
             AND i.sira > b.sira
            JOIN hatlar AS h
              ON h.hat_kodu = b.hat_kodu
            WHERE b.durak_kodu = ANY(%s::varchar[])
              AND i.durak_kodu = ANY(%s::varchar[])
              AND b.durak_kodu <> i.durak_kodu
              AND h.hizmet_turu IS DISTINCT FROM 'gorevli'
            """,
            (
                list(bas_sozluk),
                list(hedef_sozluk),
            ),
        )

        for (
            kod,
            ad,
            yon,
            binis_kodu,
            inis_kodu,
            binis_sirasi,
            inis_sirasi,
        ) in satirlar:
            binis = dict(bas_sozluk[str(binis_kodu)])
            inis = dict(hedef_sozluk[str(inis_kodu)])

            toplam_mesafe = (
                binis["mesafe_metre"]
                + inis["mesafe_metre"]
            )

            binis["mesafe_metre"] = round(
                binis["mesafe_metre"], 2
            )
            inis["mesafe_metre"] = round(
                inis["mesafe_metre"], 2
            )

            durak_araligi = inis_sirasi - binis_sirasi

            secenekler.append(
                {
                    "hat_kodu": kod,
                    "hat_adi": ad,
                    "yon": yon,
                    "binis_duragi": binis,
                    "inis_duragi": inis,
                    "binis_sirasi": binis_sirasi,
                    "inis_sirasi": inis_sirasi,
                    "durak_araligi": durak_araligi,
                    "toplam_erisim_mesafesi_metre": round(
                        toplam_mesafe, 2
                    ),
                    "_siralama": (
                        toplam_mesafe,
                        durak_araligi,
                        kod,
                        yon,
                        str(binis_kodu),
                        str(inis_kodu),
                        binis_sirasi,
                        inis_sirasi,
                    ),
                }
            )

    
    if not secenekler:
        return _koordinattan_aktarmali_rota(
            istek,
            response,
            baslama,
            ortak,
            bas_adaylar,
            hedef_adaylar,
        )

    secenekler.sort(key=lambda secenek: secenek["_siralama"])

    bulunan_secenek_sayisi = len(secenekler)
    secenekler = secenekler[:istek.sonuc_limiti]

    for secenek in secenekler:
        secenek.pop("_siralama")

    return {
        **ortak,
        "basarili": bool(secenekler),
        "sonuc_turu": "dogrudan" if secenekler else None,
        "mesaj": (
            "Doğrudan hat seçenekleri bulundu."
            if secenekler
            else (
                "Seçilen yarıçap ve aday sınırlarında "
                "doğrudan hat bulunamadı."
            )
        ),
        "bulunan_secenek_sayisi": bulunan_secenek_sayisi,
        "secenekler": secenekler,
        "islem_suresi_ms": _sure(response, baslama),
        "bilgi": (
            "Sefer saatleri ve aktarmalar "
            "bu uçta değerlendirilmez."
        ),
    }

def _koordinattan_aktarmali_rota(
    istek, response, baslama, ortak, bas_adaylar, hedef_adaylar
):
    from adres_coz import tek_aktarmali_hatlari_bul

    def satira_cevir(adaylar):
        return [
            (
                d["durak_kodu"],
                d["durak_adi"],
                d["enlem"],
                d["boylam"],
            )
            for d in adaylar
        ]

    kayitlar = []
    if bas_adaylar and hedef_adaylar:
        kayitlar = tek_aktarmali_hatlari_bul(
            satira_cevir(bas_adaylar),
            satira_cevir(hedef_adaylar),
        )

    bas_sozluk = {d["durak_kodu"]: d for d in bas_adaylar}
    hedef_sozluk = {d["durak_kodu"]: d for d in hedef_adaylar}
    secenekler = []

    for kayit in kayitlar:
        (
            hat1, ad1, yon1, bas_sira, akt1_sira,
            bas_kod, akt1_kod, bas_ad,
            hat2, ad2, yon2, akt2_sira, hedef_sira,
            hedef_kod, akt1_ad, akt2_ad,
            aktarma_mesafesi, durak_araligi,
        ) = kayit

        binis = dict(bas_sozluk[str(bas_kod)])
        inis = dict(hedef_sozluk[str(hedef_kod)])
        aktarma_mesafesi = float(aktarma_mesafesi)

        toplam = (
            binis["mesafe_metre"]
            + inis["mesafe_metre"]
            + aktarma_mesafesi
        )

        binis["mesafe_metre"] = round(binis["mesafe_metre"], 2)
        inis["mesafe_metre"] = round(inis["mesafe_metre"], 2)

        secenekler.append({
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
                "binilecek_durak": {
                    "durak_adi": akt2_ad,
                },
                "yaklasik_mesafe_metre": round(aktarma_mesafesi, 2),
            },
            "ikinci_hat": {
                "hat_kodu": hat2,
                "hat_adi": ad2,
                "yon": yon2,
                "binis_sirasi": akt2_sira,
                "inis_sirasi": hedef_sira,
            },
            "toplam_durak_araligi": durak_araligi,
            "toplam_erisim_ve_aktarma_mesafesi_metre": round(toplam, 2),
            "_siralama": (
                toplam, durak_araligi,
                hat1, yon1, hat2, yon2,
                str(bas_kod), str(hedef_kod),
                akt1_sira, akt2_sira,
            ),
        })


    secenekler.sort(key=lambda s: s["_siralama"])
    bulunan = len(secenekler)
    secenekler = secenekler[:istek.sonuc_limiti]

    
    durak_onbellegi = {}

    for secenek in secenekler:
        ikinci = secenek["ikinci_hat"]
        anahtar = (
            ikinci["hat_kodu"],
            ikinci["yon"],
            ikinci["binis_sirasi"],
        )

        if anahtar not in durak_onbellegi:
            satirlar = _sorgula(
                """
                SELECT hd.durak_kodu, d.durak_adi
                FROM hat_duraklar AS hd
                JOIN duraklar AS d
                  ON d.durak_kodu = hd.durak_kodu
                WHERE hd.hat_kodu = %s
                  AND hd.yon = %s
                  AND hd.sira = %s
                """,
                anahtar,
            )

            if len(satirlar) != 1:
                raise HTTPException(
                    status_code=503,
                    detail="Aktarma biniş durağı kesin olarak belirlenemedi.",
                )

            kod, ad = satirlar[0]
            durak_onbellegi[anahtar] = {
                "durak_kodu": str(kod),
                "durak_adi": ad,
            }

        secenek["aktarma"]["binilecek_durak"] = dict(
            durak_onbellegi[anahtar]
        )
        secenek.pop("_siralama")

    return {
        **ortak,
        "siralama": (
            "Önce doğrudan hat aranır. Bulunamazsa aktarmalı seçenekler "
            "toplam kuş uçuşu erişim ve aktarma mesafesine, "
            "ardından durak aralığına göre sıralanır."
        ),
        "basarili": bool(secenekler),
        "sonuc_turu": "tek_aktarma" if secenekler else None,
        "mesaj": (
            "Tek aktarmalı seçenekler bulundu."
            if secenekler else
            "Arama sınırları içinde doğrudan veya tek aktarmalı seçenek bulunamadı."
        ),
        "bulunan_secenek_sayisi": bulunan,
        "secenekler": secenekler,
        "islem_suresi_ms": _sure(response, baslama),
        "bilgi": (
            "Mevcut aktarma aramasının aday ve sonuç sınırları geçerlidir. "
            "Tüm olası rotaların bulunduğu garanti edilmez. "
            "Mesafeler yaklaşık olup yürünebilir yol garantisi vermez. "
            "Sefer saatlerinin birbirine uygunluğu hesaplanmaz."
        ),
    }
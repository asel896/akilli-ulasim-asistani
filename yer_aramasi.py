"""Yer kataloğunda ad araması.

Türkçe karakter, ek/kısaltma ve kontrollü yazım benzerliğiyle eşleştirir.
Emin olmadığında rastgele yer seçmez; adayları döndürüp seçtirir.
"""
import logging
import re
import time
from collections import defaultdict
from threading import Lock

from durak_eslestirme import benzerlik_maliyeti, eslestirme_metni

_log = logging.getLogger(__name__)


YER_ESDEGERLERI = {
    "univ": "universitesi",
    "uni": "universitesi",
    "universite": "universitesi",
    "fak": "fakultesi",
    "fakulte": "fakultesi",
    "hast": "hastanesi",
    "hastane": "hastanesi",
    "yurt": "yurdu",
    "kampus": "kampusu",
    "yuksekokul": "yuksekokulu",
    "myo": "meslek yuksekokulu",
}


GENEL_SOZCUKLER = {
    "universitesi", "fakultesi", "hastanesi", "yurdu", "avm", "kampusu",
    "yuksekokulu", "meslek", "merkez", "merkezi", "arastirma", "egitim",
    "ve", "devlet", "ozel", "tip", "muzesi", "stadyumu", "park",
    "kiz", "erkek", "ogrenci", "belediyesi", "sehir",
}

KESIN_ASAMALAR = ("tam", "bosluksuz")


def yer_metni(metin):
    """Yer adını karşılaştırma biçimine getirir."""
    metin = re.sub(r"['’ʼ`´]\w*", "", str(metin or ""))  # İnönü'ne -> İnönü
    metin = eslestirme_metni(metin).replace("alisveris merkezi", "avm")

    kelimeler = []

    for k in metin.split():
        kelimeler.extend(YER_ESDEGERLERI.get(k, k).split())

    return " ".join(kelimeler)


class YerIndeksi:
    """satirlar: (yer_id, ad, tur, enlem, boylam, eslesen_ad) demetleri."""

    def __init__(self, satirlar):
        self.yerler = {}
        self.adlar = defaultdict(set)

        for yer_id, ad, tur, enlem, boylam, eslesen in satirlar:
            self.yerler[yer_id] = {
                "yer_id": yer_id,
                "ad": ad,
                "tur": tur,
                "enlem": float(enlem),
                "boylam": float(boylam),
            }

            norm = yer_metni(eslesen)

            if norm:
                self.adlar[norm].add(yer_id)

    def _asamalar(self, q):
        kelimeler = set(q.split())
        bosluksuz = q.replace(" ", "")
        sayilar = re.findall(r"\d+", q)

        aday_adlar = [
            ad
            for ad in self.adlar
            if re.findall(r"\d+", ad) == sayilar
        ]

        yield "tam", [
            ad
            for ad in aday_adlar
            if ad == q
        ]

        yield "bosluksuz", [
            ad
            for ad in aday_adlar
            if ad.replace(" ", "") == bosluksuz
        ]

        yield "tum_sozcuk", [
            ad
            for ad in aday_adlar
            if kelimeler <= set(ad.split())
        ]

        maliyetler = []

        for ad in aday_adlar:
            maliyet = benzerlik_maliyeti(q, ad)

            if maliyet is not None:
                maliyetler.append((maliyet, ad))

        if maliyetler:
            en_az = min(
                maliyet
                for maliyet, _ in maliyetler
            )

            yield "benzer", [
                ad
                for maliyet, ad in maliyetler
                if maliyet == en_az
            ]

    def ara(self, sorgu, limit=8):
        q = yer_metni(sorgu)

        if not q:
            return {"durum": "bos", "yerler": []}

        for asama, adlar in self._asamalar(q):
            bulunan = {}

            for ad in adlar:
                for yer_id in self.adlar[ad]:
                    bulunan.setdefault(yer_id, ad)

            if not bulunan:
                continue

            yerler = [
                {
                    **self.yerler[yer_id],
                    "eslesme_turu": asama,
                    "eslesen_ad": ad,
                }
                for yer_id, ad in bulunan.items()
            ]
            yerler.sort(key=lambda d: (len(d["ad"]), d["ad"], d["yer_id"]))

            
            kesin = asama in KESIN_ASAMALAR and len(yerler) == 1

            return {
                "durum": "kesin" if kesin else "secim_gerekli",
                "eslesme_turu": asama,
                "toplam_aday": len(yerler),
                "yerler": yerler[:limit],
            }

        return {"durum": "bulunamadi", "yerler": []}


_YUKLE_SQL = """
    SELECT y.yer_id, y.ad, y.tur, y.enlem, y.boylam, y.ad
    FROM yerler AS y
    UNION
    SELECT y.yer_id, y.ad, y.tur, y.enlem, y.boylam, a.ad
    FROM yer_adlari AS a
    JOIN yerler AS y ON y.yer_id = a.yer_id
"""

_kilit = Lock()
_indeks = None
_yuklenme = 0.0


def indeksi_yukle(sure_saniye=300):
    global _indeks, _yuklenme

    with _kilit:
        if _indeks is not None and time.monotonic() - _yuklenme < sure_saniye:
            return _indeks

        from db import baglanti_ac

        with baglanti_ac() as baglanti:
            satirlar = baglanti.execute(_YUKLE_SQL).fetchall()

        _indeks = YerIndeksi(satirlar)
        _yuklenme = time.monotonic()

        return _indeks


def yer_ara(sorgu, limit=8):
    """Servis hatasında {'durum': 'servis_hatasi'} döner; çağıran geocoding'e düşebilir."""
    try:
        return indeksi_yukle().ara(sorgu, limit)
    except Exception:
        _log.exception("Yer kataloğu okunamadı.")
        return {"durum": "servis_hatasi", "yerler": []}


def yer_getir(yer_id):
    """Seçilen yerin alan sınırıyla birlikte tam kaydı."""
    from db import baglanti_ac

    with baglanti_ac() as baglanti:
        satir = baglanti.execute(
            """
            SELECT yer_id, ad, tur, enlem, boylam, alan_geojson, kaynak
            FROM yerler
            WHERE yer_id = %s
            """,
            (yer_id,),
        ).fetchone()

    if satir is None:
        return None

    yer_id, ad, tur, enlem, boylam, alan, kaynak = satir

    return {
        "yer_id": yer_id,
        "ad": ad,
        "tur": tur,
        "enlem": float(enlem),
        "boylam": float(boylam),
        "alan_geojson": alan,
        "kaynak": kaynak,
    }


def yer_koordinat_kaydi(yer):
    """rota_motoru.adaylari_bul'un beklediği 'adres_koordinati' biçimi."""
    return {
        "enlem": yer["enlem"],
        "boylam": yer["boylam"],
        "bulunan_adres": yer["ad"],
        "kaynak": "yer_katalogu",
        "atif": "© OpenStreetMap contributors",
        "alan_geojson": yer.get("alan_geojson"),
        "yer_id": yer["yer_id"],
        "yer_turu": yer["tur"],
    }
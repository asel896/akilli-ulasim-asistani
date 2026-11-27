"""Malatya adresleri için sınırlı, önbellekli Nominatim araması."""
from __future__ import annotations

import math
import re
import time
import unicodedata
from functools import lru_cache
from threading import Lock
from typing import Any

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AkilliUlasimAsistani/1.1 (student project)"

_request_lock = Lock()
_last_request_at = 0.0


class GeocodingError(Exception):
    """Servis veya yanıt hatası; sonuç bulunmamasından ayrıdır."""


def _temizle(metin):
    metin = unicodedata.normalize("NFKD", metin.casefold().replace("ı", "i"))
    return re.sub(r"[^a-z0-9]+", " ", "".join(
        c for c in metin if not unicodedata.combining(c)
    )).strip()


def adresi_malatya_ile_tamamla(adres: str) -> str:
    adres = " ".join(adres.strip().split())
    if "malatya" not in _temizle(adres).split():
        adres += ", Malatya, Türkiye"
    return adres


def _sorgular(adres):

    ilk = adresi_malatya_ile_tamamla(adres)
    yield {"q": ilk}
    virgulsuz = " ".join(ilk.replace(",", " ").split())
    if virgulsuz != ilk:
        yield {"q": virgulsuz}
    
    bilesenler = ilk.split(",")
    sade = re.sub(
        r"\b(?:Türbesi\s+ve\s+Külliyesi|Turbesi\s+ve\s+Kulliyesi)\b",
        "", bilesenler[0], flags=re.IGNORECASE,
    ).strip()
    if sade != bilesenler[0].strip() and len(_temizle(sade).split()) >= 2:
        yield {"q": ", ".join([sade] + [p.strip() for p in bilesenler[1:]])}
   
    parcalar = [p.strip() for p in adres.split(",") if p.strip()]
    kalan = [p for p in parcalar if _temizle(p) not in ("malatya", "turkiye", "turkey")]
    if len(parcalar) > 1 and kalan:
        alan = "street" if re.search(r"\b(cadde|caddesi|cad|sokak|sokagi|sk)\b",
                                     _temizle(kalan[0])) else "amenity"
        sorgu = {alan: kalan[0], "state": "Malatya", "country": "Türkiye"}
        if len(kalan) > 1:
            sorgu["county"] = kalan[-1]
        yield sorgu


def _http_ara(parametreler):
    global _last_request_at
    with _request_lock:
        bekle = 1.1 - (time.monotonic() - _last_request_at)
        if bekle > 0:
            time.sleep(bekle)
        try:
            cevap = requests.get(
                NOMINATIM_URL,
                params={
                    **parametreler,
                    "format": "jsonv2",
                    "limit": 5,
                    "countrycodes": "tr",
                    "addressdetails": 1,
                    "namedetails": 1,
                    "polygon_geojson": 1,
                    "accept-language": "tr",
                },
                headers={"User-Agent": USER_AGENT}, timeout=15,
            )
            cevap.raise_for_status()
            veri = cevap.json()
            if not isinstance(veri, list):
                raise ValueError("Liste bekleniyordu.")
            return veri
        except (requests.RequestException, ValueError) as hata:
            raise GeocodingError("Adres arama servisine ulaşılamadı veya geçersiz yanıt alındı.") from hata
        finally:
            _last_request_at = time.monotonic()


def _uygun_sonuc(sonuc):
    if not isinstance(sonuc, dict):
        return None

    adres = sonuc.get("address")

    if not isinstance(adres, dict):
        return None

    if str(adres.get("country_code", "")).lower() != "tr":
        return None

    if not any(
        _temizle(str(adres.get(k, "")))
        in ("malatya", "malatya ili")
        for k in ("state", "province")
    ):
        return None

    kategori = (
        sonuc.get("category")
        or sonuc.get("class")
    )

    if (
        kategori == "boundary"
        or sonuc.get("addresstype") in {
            "country",
            "state",
            "region",
            "county",
            "city",
            "town",
            "village",
            "municipality",
            "suburb",
            "quarter",
            "neighbourhood",
        }
    ):
        return None

    try:
        enlem = float(sonuc["lat"])
        boylam = float(sonuc["lon"])
    except (
        KeyError,
        ValueError,
        TypeError,
        OverflowError,
    ):
        return None

    if not (
        math.isfinite(enlem)
        and math.isfinite(boylam)
        and -90 <= enlem <= 90
        and -180 <= boylam <= 180
    ):
        return None

    return {
        "enlem": enlem,
        "boylam": boylam,
        "bulunan_adres": sonuc.get("display_name", ""),
        "kaynak": "OpenStreetMap Nominatim",
        "atif": "© OpenStreetMap contributors",
        "alan_geojson": sonuc.get("geojson"),
        "osm_turu": sonuc.get("osm_type"),
        "osm_kimligi": sonuc.get("osm_id"),
    }


def _ad_eslesiyor(adres, aday):
    aranan = _temizle(adres.split(",")[0])

    if not aranan:
        return False

    adlar = [
        aday.get("name"),
        str(aday.get("display_name", "")).split(",")[0],
    ]

    detay = aday.get("namedetails")

    if isinstance(detay, dict):
        adlar.extend(
            deger
            for anahtar, deger in detay.items()
            if (
                anahtar in {
                    "name",
                    "official_name",
                    "short_name",
                    "alt_name",
                    "loc_name",
                }
                or anahtar.startswith("name:")
            )
        )

    for deger in adlar:
        if not isinstance(deger, str):
            continue

        for ad in deger.split(";"):
            temiz = _temizle(ad)

            if re.findall(r"\d+", aranan) != re.findall(
                r"\d+", temiz
            ):
                continue

            parcalar = temiz.split()

            if any(
                "".join(parcalar[:i])
                == aranan.replace(" ", "")
                for i in range(1, len(parcalar) + 1)
            ):
                return True

            kelimeler = iter(parcalar)

            if all(
                any(x == y for y in kelimeler)
                for x in aranan.split()
            ):
                return True

    return False


@lru_cache(maxsize=256)
def _geocode_cached(adres: str) -> dict[str, Any] | None:
    for sorgu in _sorgular(adres):
        for aday in _http_ara(sorgu):
            uygun = _uygun_sonuc(aday)

            if uygun is None:
                continue

            if not _ad_eslesiyor(adres, aday):
                continue

            return {
                **uygun,
                "arama_sorgusu": dict(sorgu),
            }

    return None


def adresi_koordinata_cevir(adres: str) -> dict[str, Any] | None:
    if not isinstance(adres, str) or not adres.strip():
        raise ValueError("Adres boş olamaz.")
    return _geocode_cached(" ".join(adres.strip().split()))

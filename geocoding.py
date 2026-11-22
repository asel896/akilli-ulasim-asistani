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
                params={**parametreler, "format": "jsonv2", "limit": 5,
                        "countrycodes": "tr", "addressdetails": 1,
                        "namedetails": 1, "accept-language": "tr"},
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
    if not isinstance(adres, dict) or adres.get("country_code") != "tr":
        return None

    
    if not any(_temizle(str(adres.get(k, ""))) in ("malatya", "malatya ili")
               for k in ("state", "province")):
        return None
   
    if sonuc.get("addresstype") in {
        "country", "state", "region", "county", "city", "town",
        "village", "municipality", "suburb", "quarter", "neighbourhood",
    } or sonuc.get("class") == "boundary":
        return None
    try:
        enlem, boylam = float(sonuc["lat"]), float(sonuc["lon"])
        if not (math.isfinite(enlem) and math.isfinite(boylam)
                and -90 <= enlem <= 90 and -180 <= boylam <= 180):
            raise ValueError("Koordinat aralık dışında.")
    except (KeyError, ValueError, TypeError) as hata:
        raise GeocodingError("Adres servisi geçerli koordinat döndürmedi.") from hata
    return {
        "enlem": enlem, "boylam": boylam,
        "bulunan_adres": sonuc.get("display_name", ""),
        "kaynak": "OpenStreetMap Nominatim",
        "atif": "© OpenStreetMap contributors",
    }


@lru_cache(maxsize=256)
def _geocode_cached(adres: str) -> dict[str, Any] | None:
    for sorgu in _sorgular(adres):
        for aday in _http_ara(sorgu):
            uygun = _uygun_sonuc(aday)
            if uygun is not None:
                return {**uygun, "arama_sorgusu": dict(sorgu)}
    return None


def adresi_koordinata_cevir(adres: str) -> dict[str, Any] | None:
    if not isinstance(adres, str) or not adres.strip():
        raise ValueError("Adres boş olamaz.")
    return _geocode_cached(" ".join(adres.strip().split()))

"""Malatya adreslerini OpenStreetMap Nominatim ile koordinata çevirir.

Kullanıcı araması üzerine çağırın. Toplu sorgu yapmayın; sonuçlar bellekte
önbelleğe alınır ve çağrılar arasında en az bir saniye bırakılır.
"""

from __future__ import annotations

import time
from functools import lru_cache
from threading import Lock
from typing import Any

import requests

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "AkilliUlasimAsistani/1.0 (student project)"

_request_lock = Lock()
_last_request_at = 0.0


class GeocodingError(Exception):
    """Geocoding servisine erişilemediğinde veya sonuç alınamadığında oluşur."""


def adresi_malatya_ile_tamamla(adres: str) -> str:
    """Sorguyu Malatya'ya sınırlar; şehir adı zaten varsa tekrar eklemez."""
    adres = " ".join(adres.strip().split())
    if "malatya" not in adres.casefold():
        adres = f"{adres}, Malatya, Türkiye"
    return adres


@lru_cache(maxsize=256)
def _geocode_cached(adres: str) -> dict[str, Any] | None:
    global _last_request_at

    # Kamuya açık sunucunun saniyede bir istek sınırına uy.
    with _request_lock:
        bekle = 1.0 - (time.monotonic() - _last_request_at)
        if bekle > 0:
            time.sleep(bekle)

        try:
            response = requests.get(
                NOMINATIM_URL,
                params={
                    "q": adres,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "tr",
                    "addressdetails": 1,
                },
                headers={"User-Agent": USER_AGENT},
                timeout=15,
            )
            response.raise_for_status()
            data = response.json()
        except (requests.RequestException, ValueError) as exc:
            raise GeocodingError("Adres arama servisine şu an ulaşılamıyor.") from exc
        finally:
            _last_request_at = time.monotonic()

    if not data:
        return None

    result = data[0]
    try:
        latitude = float(result["lat"])
        longitude = float(result["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError("Adres servisi geçerli koordinat döndürmedi.") from exc

    return {
        "enlem": latitude,
        "boylam": longitude,
        "bulunan_adres": result.get("display_name", ""),
        "kaynak": "OpenStreetMap Nominatim",
        "atif": "© OpenStreetMap contributors",
    }


def adresi_koordinata_cevir(adres: str) -> dict[str, Any] | None:
    """Bir Malatya adresini koordinata çevirir; bulunamazsa None döndürür."""
    if not adres or not adres.strip():
        raise ValueError("Adres boş olamaz.")
    sorgu = adresi_malatya_ile_tamamla(adres)
    return _geocode_cached(sorgu)

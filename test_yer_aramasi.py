"""Çalıştırma: python test_yer_aramasi.py  (veritabanı gerekmez)."""
from yer_aramasi import YerIndeksi, yer_metni

# test için uydurma kayitlar
SATIRLAR = [
    (1, "Alfa Üniversitesi", "universite", 38.30, 38.30, "Alfa Üniversitesi"),
    (1, "Alfa Üniversitesi", "universite", 38.30, 38.30, "AÜ"),
    (2, "Alfa Üniversitesi Tıp Fakültesi", "fakulte", 38.31, 38.31,
     "Alfa Üniversitesi Tıp Fakültesi"),
    (3, "Beta Eğitim ve Araştırma Hastanesi", "hastane", 38.32, 38.32,
     "Beta Eğitim ve Araştırma Hastanesi"),
    (4, "Gama Eğitim ve Araştırma Hastanesi", "hastane", 38.33, 38.33,
     "Gama Eğitim ve Araştırma Hastanesi"),
    (5, "Delta AVM", "avm", 38.34, 38.34, "Delta AVM"),
    (6, "Sigma Yurdu", "yurt", 38.35, 38.35, "Sigma Yurdu"),
    (7, "Sigma Yurdu", "yurt", 38.36, 38.36, "Sigma Yurdu"),
]

indeks = YerIndeksi(SATIRLAR)


def kontrol(sorgu, durum, yer_idleri=None, asama=None):
    sonuc = indeks.ara(sorgu)
    idler = {y["yer_id"] for y in sonuc["yerler"]}

    assert sonuc["durum"] == durum, (sorgu, sonuc["durum"], idler)

    if yer_idleri is not None:
        assert idler == set(yer_idleri), (sorgu, idler)

    if asama is not None:
        assert sonuc["eslesme_turu"] == asama, (sorgu, sonuc["eslesme_turu"])


# Türkçe karakter büyük kücük harf
kontrol("ALFA UNIVERSITESI", "kesin", [1])
kontrol("alfa üniversitesi'ne", "kesin", [1])

# kisaltma
kontrol("alfa univ", "kesin", [1])
kontrol("alfa üni tıp fak", "kesin", [2], "tam")

# sözcüklerin bir kismi yazilmis eşleşir ama onay istenir
kontrol("alfa tıp fakültesi", "secim_gerekli", [2], "tum_sozcuk")

# alternatif ad
kontrol("AÜ", "kesin", [1])


kontrol("araştırma hastanesi", "secim_gerekli", [3, 4])

# ayni adli iki yer: otomatik seçilmez
kontrol("sigma yurdu", "secim_gerekli", [6, 7], "tam")

# cümleden gelen uzun metin ozgun ad
kontrol("alfa üniversitesi tıp fakültesi hastanesi", "secim_gerekli", [2], "ad_sorguda")

# yazim hatasi eslesir ama onay istenir
kontrol("alfa universtesi", "secim_gerekli", [1], "benzer")

# bulunamayan
kontrol("olmayan bir yer", "bulunamadi")
kontrol("", "bos")

assert yer_metni("Delta Alışveriş Merkezi") == "delta avm"

print("Tüm testler geçti.")
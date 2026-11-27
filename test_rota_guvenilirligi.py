import sys
import types
import unittest
from unittest.mock import patch

from rota_motoru import adaylari_bul, hesapla, rota_bul


def durak(kod):
    return {
        "durak_kodu": kod,
        "durak_adi": kod,
        "enlem": 38.3,
        "boylam": 38.3,
        "mesafe_metre": None,
    }


def yol(hat, kodlar):
    return [
        (hat, hat, "gidis", sira, kod, 38.3, 38.3)
        for sira, kod in enumerate(kodlar, 1)
    ]


class RotaTestleri(unittest.TestCase):
    def setUp(self):
        self.kayitlar = yol("TEST", ["A", "B", "C", "D", "E"])

    def test_dogrudan_sonuc_sozluk_doner(self):
        cevap = hesapla([durak("A")], [durak("D")], self.kayitlar)
        self.assertIsInstance(cevap, dict)
        self.assertTrue(cevap["basarili"])
        self.assertEqual(cevap["sonuc_turu"], "dogrudan")

    def test_ters_sirada_rota_uretilmez(self):
        cevap = hesapla([durak("E")], [durak("A")], self.kayitlar)
        self.assertFalse(cevap["basarili"])
        self.assertEqual(cevap["secenekler"], [])

    def test_ayni_duraga_yolculuk_uretilmez(self):
        cevap = hesapla([durak("C")], [durak("C")], self.kayitlar)
        self.assertFalse(cevap["basarili"])

    def test_bos_adaylarda_sonuc_sozluktur(self):
        cevap = hesapla([], [], self.kayitlar)
        self.assertIsInstance(cevap, dict)
        self.assertFalse(cevap["basarili"])
        self.assertEqual(cevap["secenekler"], [])

    def test_binisler_inisten_once_olmalidir(self):
        cevap = hesapla(
            [durak("A"), durak("B"), durak("E")],
            [durak("D")],
            self.kayitlar,
        )
        secenek = cevap["secenekler"][0]
        adaylar = secenek["uygun_binis_duraklari"]
        self.assertEqual({d["durak_kodu"] for d in adaylar}, {"A", "B"})
        self.assertTrue(all(d["binis_sirasi"] < secenek["inis_sirasi"] for d in adaylar))

    def test_inisler_binisten_sonra_olmalidir(self):
        cevap = hesapla(
            [durak("B")],
            [durak("A"), durak("C"), durak("D")],
            self.kayitlar,
        )
        secenek = cevap["secenekler"][0]
        adaylar = secenek["uygun_inis_duraklari"]
        self.assertEqual({d["durak_kodu"] for d in adaylar}, {"C", "D"})
        self.assertTrue(all(d["inis_sirasi"] > secenek["binis_sirasi"] for d in adaylar))

    def test_dogrudan_hat_aktarmaya_onceliklidir(self):
        kayitlar = (
            yol("DOGRUDAN", ["A", "D"])
            + yol("ILK", ["A", "T"])
            + yol("IKINCI", ["U", "D"])
        )
        cevap = hesapla([durak("A")], [durak("D")], kayitlar)
        self.assertEqual(cevap["sonuc_turu"], "dogrudan")
        self.assertEqual(cevap["secenekler"][0]["hat_kodu"], "DOGRUDAN")

    def test_aktarmada_iki_etabin_sirasi_gecerlidir(self):
        kayitlar = (
            yol("ILK", ["A", "B", "T"])
            + yol("IKINCI", ["U", "C", "D"])
        )
        cevap = hesapla([durak("A"), durak("B")], [durak("C"), durak("D")], kayitlar)
        self.assertEqual(cevap["sonuc_turu"], "tek_aktarma")
        self.assertTrue(cevap["secenekler"])
        for s in cevap["secenekler"]:
            ilk, ikinci = s["birinci_hat"], s["ikinci_hat"]
            self.assertLess(ilk["binis_sirasi"], ilk["inis_sirasi"])
            self.assertLess(ikinci["binis_sirasi"], ikinci["inis_sirasi"])
            self.assertTrue(all(d["binis_sirasi"] < ilk["inis_sirasi"] for d in s["uygun_binis_duraklari"]))
            self.assertTrue(all(d["inis_sirasi"] > ikinci["binis_sirasi"] for d in s["uygun_inis_duraklari"]))

    def test_uzak_duraklar_arasinda_aktarma_uretilmez(self):
        ilk = yol("ILK", ["A", "T"])
        ikinci = [
            (h, ad, yon, sira, kod, 39.0, 39.0)
            for h, ad, yon, sira, kod, _, _ in yol("IKINCI", ["U", "D"])
        ]
        cevap = hesapla([durak("A")], [durak("D")], ilk + ikinci)
        self.assertFalse(cevap["basarili"])

    def test_rota_bul_tuple_hatasina_dusmez(self):
        sahte_api = types.ModuleType("rota_api")
        sahte_api._sorgula = lambda *args: self.kayitlar
        with patch.dict(sys.modules, {"rota_api": sahte_api}):
            cevap = rota_bul([durak("A")], [durak("D")])
        self.assertIsInstance(cevap, dict)
        self.assertTrue(cevap["basarili"])

    def test_alan_icindeki_uzak_duraklar_kaybolmaz(self):
        konum = {
            "cozum_turu": "geocoding",
            "adres_koordinati": {
                "enlem": 38.32,
                "boylam": 38.32,
                "alan_geojson": {
                    "type": "Polygon",
                    "coordinates": [[
                        [38.30, 38.30],
                        [38.34, 38.30],
                        [38.34, 38.34],
                        [38.30, 38.34],
                        [38.30, 38.30],
                         ]],
                },
            },
        }
        adaylar = adaylari_bul(konum, [
            ("A", "A", 38.31, 38.31),
            ("B", "B", 38.33, 38.33),
            ("X", "X", 39.0, 39.0),
        ], 1)
        self.assertEqual({d["durak_kodu"] for d in adaylar}, {"A", "B"})
        self.assertTrue(all(d["alan_icinde"] for d in adaylar))
        self.assertTrue(all(d["mesafe_metre"] is None for d in adaylar))

    def test_nokta_aramasinda_yaricap_disindaki_durak_elenir(self):
        konum = {
            "cozum_turu": "geocoding",
            "adres_koordinati": {"enlem": 38.3, "boylam": 38.3},
        }
        adaylar = adaylari_bul(konum, [
            ("A", "A", 38.3, 38.3),
            ("X", "X", 39.0, 39.0),
        ], 400)
        self.assertEqual([d["durak_kodu"] for d in adaylar], ["A"])


class YerTestleri(unittest.TestCase):
    def setUp(self):
        from yer_aramasi import YerIndeksi
        self.indeks = YerIndeksi([
            (1, "İnönü Üniversitesi", "universite", 38.3, 38.3, "İnönü Üniversitesi"),
            (2, "Malatya Park AVM", "avm", 38.3, 38.3, "Malatya Park"),
            (2, "Malatya Park AVM", "avm", 38.3, 38.3, "MalatyaPark"),
            (3, "İnönü Üniversitesi Diş Hekimliği Fakültesi", "fakulte", 38.3, 38.3, "Diş Hekimliği Fakültesi"),
            (4, "Hastane A", "hastane", 38.3, 38.3, "Araştırma Hastanesi"),
            (5, "Hastane B", "hastane", 38.3, 38.3, "Araştırma Hastanesi"),
        ])

    def test_olmayan_fakulte_universiteye_indirgenmez(self):
        cevap = self.indeks.ara("İnönü Üniversitesi Olmayan Fakülte")
        self.assertEqual(cevap["yerler"], [])
        self.assertEqual(cevap["durum"], "bulunamadi")

    def test_gecerli_universite_adi_bulunur(self):
        cevap = self.indeks.ara("İnönü Üniversitesi")
        self.assertEqual([y["yer_id"] for y in cevap["yerler"]], [1])

    def test_alternatif_yer_adlari_ayni_kaydi_bulur(self):
        for sorgu in ("Malatya Park", "MalatyaPark"):
            with self.subTest(sorgu=sorgu):
                cevap = self.indeks.ara(sorgu)
                self.assertEqual([y["yer_id"] for y in cevap["yerler"]], [2])

    def test_ayni_adli_farkli_yerler_icin_secim_gerekir(self):
        cevap = self.indeks.ara("Araştırma Hastanesi")
        self.assertEqual(cevap["durum"], "secim_gerekli")
        self.assertEqual({y["yer_id"] for y in cevap["yerler"]}, {4, 5})


if __name__ == "__main__":
    unittest.main(verbosity=2)

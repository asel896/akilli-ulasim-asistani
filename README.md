# Akıllı Ulaşım Asistanı

Malatya için LLM destekli adres çözümleme ve mobil toplu taşıma
yönlendirme asistanı bitirme projesidir.

Projenin amacı, kullanıcının serbest metinle yazdığı hedef adresi
çözümleyerek uygun durak ve toplu taşıma hattını bulmasına yardımcı olmaktır.

Proje geliştirme aşamasındadır. Adres çözümleme, rota önerisi ve mobil
uygulama henüz tamamlanmamıştır.

## Tamamlanan Çalışmalar

- MOTAŞ hat listesinden 124 farklı hat bağlantısı toplandı.
- Hatların mevcut gidiş ve dönüş durak listeleri indirildi.
- Durak kodları, adları, sıraları ve koordinatları okundu.
- Veriler JSON dosyalarına kaydedildi ve PostgreSQL'e aktarıldı.
- Veri yapısı, koordinat aralıkları ve durak tutarlılığı kontrol edildi.

## Veri Kontrol Sonuçları

İlk veri toplama çalışmasında elde edilen sonuçlar:

| Kontrol | Sonuç |
|---|---:|
| Okunan hat dosyası | 124 |
| Benzersiz durak kodu | 3.820 |
| Hat, yön ve sıra bazında durak kaydı | 10.323 |
| Aynı kodda farklı ad veya koordinat bulunan durak | 0 |

37 hattın dönüş durak listesi boştur. Bunların 36'sında kaynak güzergâh
başlığı RİNG, 100 kodlu hatta ise GÖREVLİ olarak tanımlanmıştır.
Boş dönüş listelerinden yapay dönüş güzergâhı üretilmemiştir.

Bu kontroller, verilerin güncelliğini veya sahadaki doğruluğunu garanti etmez.
Koordinatlar için yapılan ilk kontrol, sayısal geçerlilik ve aralık kontrolüdür.

## Kullanılan Teknolojiler

- Python
- Requests
- BeautifulSoup
- PostgreSQL
- Psycopg
- python-dotenv

## Kurulum

Aşağıdaki komutlar Windows PowerShell içindir.

### 1. Sanal ortam oluşturma

```powershell
python -m venv .venv
```

### 2. Kütüphaneleri kurma

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Veritabanını hazırlama

PostgreSQL'de UTF-8 kodlamasına sahip `akilli_ulasim` adlı boş bir
veritabanı oluşturun. Bu veritabanında `schema.sql` dosyasını çalıştırın.

### 4. Bağlantı ayarları

Proje klasöründe `.env` dosyası oluşturup kendi bilgilerinizi girin:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=akilli_ulasim
DB_USER=postgres
DB_PASSWORD="kendi_sifreniz"
```

`.env` dosyası Git tarafından takip edilmez.

### 5. Bağlantıyı test etme

```powershell
.\.venv\Scripts\python.exe -X utf8 db_baglanti.py
```

## Veri Toplama ve Aktarma

Komutları proje klasöründe, aşağıdaki sırayla çalıştırın:

```powershell
.\.venv\Scripts\python.exe -X utf8 hat_listesi.py
.\.venv\Scripts\python.exe -X utf8 hatlari_indir.py
.\.venv\Scripts\python.exe -X utf8 veri_dogrulama.py
.\.venv\Scripts\python.exe -X utf8 yon_kontrol.py
.\.venv\Scripts\python.exe -X utf8 durak_tutarlilik.py
.\.venv\Scripts\python.exe -X utf8 veri_aktar.py
```

İndirilen dosyalar `veriler/` klasöründe tutulur ve GitHub'a yüklenmez.
Veri toplama kodları kaynak sitenin mevcut yapısına bağlıdır.

`veri_aktar.py` ilk aktarım için hazırlanmıştır. Mevcut kayıtlarla
çakışan kayıtları atlar; veri güncelleme veya eski kayıtları silme yapmaz.

## Veritabanı Yapısı

- `hatlar`: Hat kodu, adı ve sayfa kimliği.
- `duraklar`: Durak kodu, adı ve koordinatları.
- `hat_duraklar`: Hatların yönlere göre sıralı durak ilişkileri.

Aynı durak, bir güzergâhta farklı sıralarda tekrar bulunabilir.

## Planlanan Çalışmalar

- LLM ile adres normalizasyonu
- Adresin coğrafi koordinata dönüştürülmesi
- En yakın durak ve uygun hat eşleştirmesi
- FastAPI servisleri
- Flutter mobil uygulaması
- Konum takibi ve durak yaklaşım uyarıları
- Performans ve kaynak tüketimi testleri

## Veri Kaynağı

[MOTAŞ Hatlar](https://motas.com.tr/ulasim/hatlar)

## Geliştiren

Asel Ünlü — İnönü Üniversitesi, Bilgisayar Mühendisliği
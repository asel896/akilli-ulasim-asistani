# Akıllı Ulaşım Asistanı

Malatya için LLM destekli adres çözümleme ve mobil toplu taşıma yönlendirme asistanı bitirme projesidir.

Projenin amacı, kullanıcının doğal dille yazdığı yolculuk isteğinden başlangıç ve hedef bilgilerini çıkararak uygun durak ve toplu taşıma hattını bulmasına yardımcı olmaktır.

Proje geliştirme aşamasındadır. FastAPI tabanlı adres çözümleme, koordinat arama, yakın durak tespiti ve rota sorgulama servisleri geliştirilmiştir. Mobil uygulama, konum takibi ve durak yaklaşım uyarıları henüz tamamlanmamıştır.

## Tamamlanan Çalışmalar

### Veri toplama ve veritabanı

- MOTAŞ hat listesinden 124 farklı hat bağlantısı toplandı.
- Hatların kaynakta mevcut gidiş ve dönüş durak listeleri indirildi.
- Durak kodları, adları, sıraları ve koordinatları okundu.
- Veriler JSON dosyalarına kaydedildi ve PostgreSQL'e aktarıldı.
- Güzergâh varyantları ve sıralı koordinat noktaları aktarıldı.
- Veri yapısı, koordinat aralıkları ve kaynakla tutarlılık kontrol edildi.
- Gün ve yön bazındaki sefer saatleri veritabanına aktarıldı.

### Adres çözümleme ve koordinat arama

- Gemini ile doğal dildeki yolculuk isteklerinden başlangıç ve hedef bilgileri çıkarıldı.
- Sonuçlar yapılandırılmış JSON olarak sunuldu.
- Türkçe karakter, yazım hatası, kısaltma ve birleşik–ayrı yazım farklılıkları için durak eşleştirmesi geliştirildi.
- Birden fazla eşleşmede aday duraklar ve eşleşme türleri gösterildi.
- Eksik veya fazla genel konum bilgilerinde açıklayıcı yanıtlar hazırlandı.
- Durak eşleşmelerinde veritabanındaki koordinatlar kullanıldı.
- Açık adresler için OpenStreetMap Nominatim ile koordinat araması eklendi.
- Yapı ve işletme adresleriyle aynı adlı otobüs durakları ayrı alanlarda gösterildi.
- Açıkça durak istendiğinde, bulunamayan durağın yerine adres koordinatı kullanılmaması sağlandı.
- API kota hataları ele alındı ve test sonuçlarının korunarak devam ettirilmesi sağlandı.

### Backend ve rota algoritması

- Haversine formülüyle koordinata yakın duraklar bulundu.
- Duraklar kuş uçuşu mesafelerine göre sıralandı.
- Duraktan geçen hatlar, yön ve durak sırasıyla sorgulanabilir hâle getirildi.
- Hatların gidiş ve dönüş durakları ayrı listelerle sunuldu.
- Başlangıç ve hedef koordinatlarının çevresindeki aday duraklar arasında doğrudan hat araması eklendi.
- Rota eşleştirmesinde aynı hat, aynı yön ve biniş sırasının inişten önce olması koşulları kullanıldı.
- Doğal dilde adres çözümleme ile yakın durak ve doğrudan rota araması birleştirildi.
- Mevcut `/yol-tarifi` ucunda doğrudan ve tek aktarmalı seçenekler sunuldu.
- Yakın aktarma durakları arasındaki yaklaşık mesafeler ve seçilen güne ait hat kalkış saatleri gösterildi.

## Veri Kontrol Sonuçları

İlk veri toplama ve aktarım çalışmasında elde edilen sonuçlar:

| Kontrol | Sonuç |
|---|---:|
| Okunan hat dosyası | 124 |
| Benzersiz durak kodu | 3.820 |
| Hat, yön ve sıra bazında durak kaydı | 10.323 |
| Aynı kodda farklı ad veya koordinat bulunan durak | 0 |
| Güzergâh varyantı | 211 |
| Güzergâh koordinat noktası | 110.069 |
| Kaynakla karşılaştırmada eksik veya fazla nokta | 0 |
| Kaynakla koordinatı farklı nokta | 0 |
| Aktarılan sefer kaydı | 23.517 |
| Sefer saati bulunan hat sayısı | 122 |

37 hattın dönüş durak listesi boştur. Bunların 36'sında kaynak güzergâh başlığı RİNG, 100 kodlu hatta ise GÖREVLİ olarak tanımlanmıştır. Boş dönüş listelerinden yapay dönüş güzergâhı üretilmemiştir.

100 ve 253 kodlu hatların incelenen kaynak çizelgelerinde sefer saati bulunmamıştır.

Bu kontroller verilerin güncelliğini veya sahadaki doğruluğunu garanti etmez. Koordinatlar için yapılan ilk kontrol sayısal geçerlilik ve aralık kontrolüdür.

## Kullanılan Teknolojiler

- Python
- FastAPI
- Pydantic
- Google Gemini API
- Requests
- BeautifulSoup
- PostgreSQL
- Psycopg
- python-dotenv
- OpenStreetMap Nominatim

## Kurulum

Aşağıdaki komutlar Windows PowerShell içindir. Komutları proje klasöründe çalıştırın.

### 1. Sanal ortam oluşturma

```powershell
python -m venv .venv
```

### 2. Kütüphaneleri kurma

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. Veritabanını hazırlama

PostgreSQL'de UTF-8 kodlamasına sahip `akilli_ulasim` adlı boş bir veritabanı oluşturun.

Bu veritabanında önce `schema.sql`, ardından sefer saatleri tablosunu oluşturan `sefer_saatleri.sql` dosyasını çalıştırın.

### 4. Bağlantı ayarları

Proje klasöründe `.env` dosyası oluşturup kendi bilgilerinizi girin:

```dotenv
DB_HOST=localhost
DB_PORT=5432
DB_NAME=akilli_ulasim
DB_USER=postgres
DB_PASSWORD="kendi_sifreniz"
GEMINI_API_KEY=kendi_gemini_api_anahtariniz
```

`.env` dosyası Git tarafından takip edilmez. Gerçek API anahtarlarını ve veritabanı parolalarını GitHub'a yüklemeyin.

### 5. Bağlantıyı test etme

```powershell
.\.venv\Scripts\python.exe -X utf8 db_baglanti.py
```

### 6. API'yi çalıştırma

Veri aktarımını tamamladıktan sonra:

```powershell
.\.venv\Scripts\python.exe -m fastapi dev main.py
```

- API: http://127.0.0.1:8000
- Swagger: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json

Bu komut geliştirme sunucusunu başlatır.

## Veri Toplama ve Aktarma

Komutları aşağıdaki sırayla çalıştırın:

```powershell
.\.venv\Scripts\python.exe -X utf8 hat_listesi.py
.\.venv\Scripts\python.exe -X utf8 hatlari_indir.py
.\.venv\Scripts\python.exe -X utf8 veri_dogrulama.py
.\.venv\Scripts\python.exe -X utf8 yon_kontrol.py
.\.venv\Scripts\python.exe -X utf8 durak_tutarlilik.py
.\.venv\Scripts\python.exe -X utf8 veri_aktar.py
.\.venv\Scripts\python.exe -X utf8 hat_bilgileri_guncelle.py
.\.venv\Scripts\python.exe -X utf8 guzergah_aktar.py
.\.venv\Scripts\python.exe -X utf8 guzergah_kontrol.py
.\.venv\Scripts\python.exe -X utf8 seferleri_aktar.py
```

İndirilen dosyalar `veriler/` klasöründe tutulur ve GitHub'a yüklenmez. Veri toplama kodları kaynak sitenin mevcut yapısına bağlıdır.

`veri_aktar.py` ilk aktarım için hazırlanmıştır. Mevcut kayıtlarla çakışan kayıtları atlar; veri güncelleme veya eski kayıtları silme yapmaz.

## Veritabanı Yapısı

- `hatlar`: Hat kodu, adı, sayfa kimliği ve diğer hat bilgileri.
- `duraklar`: Durak kodu, adı ve koordinatları.
- `hat_duraklar`: Hatların yönlere göre sıralı durak ilişkileri.
- `guzergahlar`: Hatların güzergâh varyantları, kaynak yönleri ve diğer güzergâh bilgileri.
- `guzergah_noktalari`: Her güzergâhın sıralı koordinat noktaları.
- `sefer_saatleri`: Hat, gün ve yön bazında kalkış saatleri ve açıklamalar.

Hatların kaynak aktiflik ve kategori bilgileri de saklanmaktadır.

Güzergâh başlıklarına göre 36 hat ring, 1 hat görevli olarak sınıflandırılmış; diğer 87 hat belirsiz bırakılmıştır. Bu sınıflandırma, yolcu kullanımına uygunluk doğrulaması değildir.

Aynı durak, bir güzergâhta farklı sıralarda tekrar bulunabilir.

## API Uçları

| Yöntem | Uç | İşlev |
|---|---|---|
| GET | `/` | API ana sayfası |
| GET | `/saglik` | Uygulamanın yanıt verdiğini kontrol eder |
| POST | `/adres-coz` | Başlangıç ve hedefi çözümler; durak veya adres koordinatı döndürür |
| POST | `/geocode` | Verilen adresi Nominatim ile koordinata dönüştürür |
| POST | `/yol-tarifi` | Durak eşleşmelerinden doğrudan veya tek aktarmalı seçenekler arar |
| GET | `/duraklar/yakin` | Koordinat çevresindeki durakları mesafeye göre sıralar |
| GET | `/duraklar/{durak_kodu}/hatlar` | Duraktan geçen hatları yön ve sıra bilgisiyle getirir |
| GET | `/hatlar/{hat_kodu}/duraklar` | Hattın gidiş ve dönüş duraklarını sıralı getirir |
| POST | `/rota/koordinat` | İki koordinatın yakın durak adayları arasında doğrudan hat arar |
| POST | `/rota/dogal-dil` | Doğal dilde adres çözümleme ile doğrudan rota aramasını birleştirir |

`/saglik` ucu Gemini, Nominatim ve veritabanının tamamının erişilebilir olduğunu doğrulamaz.

### Adres çözümleme örneği

`POST /adres-coz`

```json
{
  "metin": "Maliye durağından MAŞTİ Otogar durağına nasıl giderim?",
  "baslangic_turu": "durak",
  "hedef_turu": "durak"
}
```

Konum türleri `otomatik`, `durak` veya `adres` olabilir.

Adres isteklerinde aynı adlı duraklar `ayni_adli_duraklar` alanında ayrıca gösterilebilir. Bu adaylar yapının gerçek koordinatı veya coğrafi olarak en yakın durakları olarak kabul edilmez.

### Yakın durak örneği

`GET /duraklar/yakin`

```text
enlem=38.3523009
boylam=38.315757
yaricap_metre=1000
limit=5
```

Duraklar Haversine mesafesine göre yakından uzağa sıralanır. Mevcut uygulamada yakın durak verileri 60 saniye süreyle bellekte önbelleğe alınır.

### Koordinattan doğrudan rota örneği

`POST /rota/koordinat`

```json
{
  "baslangic": {
    "enlem": 38.3523009,
    "boylam": 38.315757
  },
  "hedef": {
    "enlem": 38.3407705,
    "boylam": 38.256446
  },
  "yaricap_metre": 1000,
  "aday_limiti": 10,
  "sonuc_limiti": 5
}
```

Başlangıç ve hedef çevresindeki aday durak çiftleri aynı hat, aynı yön ve ileri durak sırası koşullarıyla eşleştirilir.

Seçenekler önce toplam kuş uçuşu erişim mesafesine, ardından durak aralığına göre sıralanır. Bu sıralama en kısa yolculuk süresini garanti etmez.

`adaylar_kisitlandi: true`, yarıçap içindeki tüm durakların aday sınırı nedeniyle değerlendirilmediğini gösterir. Sonuç bulunmaması bütün ulaşım ağında rota olmadığı anlamına gelmez.

### Doğal dilden rota örneği

`POST /rota/dogal-dil`

```json
{
  "soru": "Taşhoron Kilisesi, Malatya konumundan MAŞTİ Otogar durağına nasıl giderim?",
  "baslangic_turu": "adres",
  "hedef_turu": "durak",
  "yaricap_metre": 1000,
  "aday_limiti": 10,
  "sonuc_limiti": 5
}
```

Adres çözümlendiğinde koordinat çevresindeki durak adayları değerlendirilir. Açıkça durak belirtildiğinde eşleşen durak adayları korunur.

Kullanıcının gerçek koordinatı verilmediğinde, belirtilen durağa erişim mesafesi bilinmediği için ilgili mesafe alanı `null` döner.

## Test Sonuçları

### Adres çözümleme ve durak eşleştirme

İlk değerlendirmede 10 yolculuk sorgusunun başlangıç ve hedef bilgileri ayrı ayrı kontrol edilmiş, toplam 20 kontrolün tamamı doğru bulunmuştur.

Daha sonra test seti 100 sorguya genişletilmiştir. Set; normal ifadeler, kısaltmalar, Türkçe karaktersiz yazımlar, yazım hataları, benzer adlar, eksik bilgiler, bulunamayan yerler ve fazla genel konumlar içerir.

Kota hatalarından devam edilerek tamamlanan bir çalıştırmada:

| Ölçüm | Sonuç |
|---|---:|
| Toplam sorgu | 100 |
| Değerlendirilen sorgu | 98 |
| HTTP 503 ile sonuçlanan sorgu | 2 |
| Tüm ölçütleri karşılayan sorgu | 89 |
| Teknik hatalar dahil tam doğruluk | %89 |
| Değerlendirilen sorgularda iki ucun durak eşleştirmesi | 98/98 |
| Yeniden denenen HTTP 429 yanıtı | 7 |

Tam doğruluk; başlangıç ve hedef adlarının, durak eşleştirmelerinin ve başarı alanının test beklentilerine uygunluğunu birlikte değerlendirir.

Bu set geliştirme sırasında tekrar kullanılmıştır. Sonuçlar bağımsız ve daha önce görülmemiş sorgulardaki başarıyı göstermez.

### Koordinat doğruluğu

Yazım hatası içeren 20 adreslik bir başlangıç seti hazırlanmıştır. Dönen koordinatın referansa en fazla 50 metre uzaklıkta olması başarı koşulu olarak belirlenmiştir.

Referans incelemesinde Taşhoron Kilisesi ve Somuncu Baba koordinatları bağımsız kaynaklarla düzeltilmiş, önceki sonuçlar korunmuştur.

Arslantepe Höyüğü için karşılaştırılacak kesin noktanın belirsizliği, Tevfik Temelli Caddesi 21. Sokak için ise konumun doğrulanamaması nedeniyle iki örnek değerlendirme dışında raporlanmıştır.

Son düzeltme ölçümünde:

| Grup | Sonuç |
|---|---:|
| Durak örnekleri | 16/16 doğru |
| Referansı geçerli durak dışı adresler | 2/2 doğru |
| Değerlendirilen toplam | 18/18 doğru |
| Referansı belirsiz örnek | 2 |

Bu sonuç, referansı geçerli 18 örnekte %100 başarıdır. İki örneğin değerlendirme dışında olması ve setin geliştirme sırasında kullanılması nedeniyle bütün adresler için %100 doğruluk veya bağımsız bir genel başarı garantisi olarak yorumlanamaz.

### Backend performansı

Üç sorgulama ucunda 20'şer, koordinattan rota ucunda iki yönde 20'şer olmak üzere toplam 100 ardışık yerel HTTP isteği ölçülmüştür.

| Uç / Senaryo | İstek | Ortalama | P95 | En yüksek |
|---|---:|---:|---:|---:|
| Yakın duraklar | 20 | 24,49 ms | 26,64 ms | 193,74 ms |
| Duraktan geçen hatlar | 20 | 89,54 ms | 107,80 ms | 204,53 ms |
| 2A hattının durakları | 20 | 82,98 ms | 104,90 ms | 129,84 ms |
| Koordinattan Maliye → MAŞTİ | 20 | 60,35 ms | 63,32 ms | 218,15 ms |
| Koordinattan MAŞTİ → Maliye | 20 | 50,23 ms | 53,65 ms | 57,83 ms |

Ölçülen 100 isteğin tamamı başarılı ve 500 ms altında sonuçlanmıştır. Koordinattan rota ölçümündeki 40 istekte rota bulunamaması veya hatalı biniş–iniş sırası görülmemiştir.

Bu ölçümler seçilen sorgulara, yerel ortama ve ardışık isteklere aittir. Yakın durak sorgularında önbellek etkisi vardır. Sonuçlar eşzamanlı yükü veya tüm konumları kapsamaz.

Doğal dil rota ucunda iki örneğin toplam süresi yaklaşık 4,18 ve 4,81 saniyedir. Bu süreler Gemini ve gerektiğinde geocoding çağrılarını içerir. Bu uç için 500 ms hedefi karşılanmamıştır.

Yanıtlardaki `islem_suresi_ms` alanı endpoint içindeki işlem süresidir. PowerShell ölçümleri ise yerel HTTP isteğinin tamamını kapsar.

## Testleri Çalıştırma

FastAPI sunucusu açıkken başka bir terminal kullanın.

### Durak eşleştirme testi

Mevcut sabitlenmiş `adres_testi_beklentiler.json` dosyasıyla:

```powershell
.\.venv\Scripts\python.exe .\adres_testi.py --aralik 15
```

Tamamlanan sorgular korunur. Gemini 429 yanıtlarında betik bekleyip yeniden deneyebilir. Süre sınırları günlük kotayı artırmaz.

Beklenti dosyası testten önce hazırlanmış ve kontrol edilmiş olmalıdır. Referansları gerçek API sonuçlarına bakarak başarıyı yükseltmek amacıyla değiştirmeyin.

### Koordinat referanslarını ilk kez hazırlama

Ham MOTAŞ JSON dosyaları `veriler/` klasöründeyken:

```powershell
.\.venv\Scripts\python.exe .\adres_testi.py --koordinat-hazirla
```

Bu adım API'ye istek göndermez.

### Koordinat testi

```powershell
.\.venv\Scripts\python.exe .\adres_testi.py --koordinat --aralik 15
```

### Düzeltilmiş referanslarla ayrı ölçüm

Önceki referans dosyası mevcutken:

```powershell
.\.venv\Scripts\python.exe .\adres_testi.py --koordinat --koordinat-v2 --deney duzeltme-1 --aralik 15
```

Aynı deney adıyla yeniden çalıştırma, kaydedilmiş sonuçlardan devam eder. Kod değişikliğinden sonra yeni bir ölçüm yapmak için farklı bir deney adı kullanın.

Test kayıtları Windows'ta `%LOCALAPPDATA%` altında ilgili `akilli-ulasim-*` klasörlerine yazılır. Bu klasörler otomatik olarak GitHub'a gönderilmez.

## Bilinen Sınırlamalar

- Toplu taşıma verileri kaynak siteden indirilen kayıtları temsil eder; canlı araç veya sefer verisi değildir.
- Haversine mesafesi kuş uçuşudur; yürüyüş yolu, yol geçişi veya erişilebilirlik kontrolü yapılmaz.
- Durak adıyla yapı veya işletme adı aynı olsa bile koordinatları aynı kabul edilmez.
- Otomatik konum türü belirleme kuralları her belirsiz ifadeyi çözemez; gerektiğinde `durak` veya `adres` tercihi verilmelidir.
- Yakın durak adayları yarıçap ve aday sayısıyla sınırlıdır.
- `/rota/koordinat` ve `/rota/dogal-dil` uçları yalnız doğrudan hatları değerlendirir.
- `/yol-tarifi` ucundaki tek aktarmalı arama henüz yeni koordinat ve doğal dil rota akışına bağlanmamıştır.
- Sefer saatleri hattın başlangıç durağındaki kalkış saatleridir; ara duraktan geçiş saati değildir.
- Aktarmalarda araçların saat açısından birbirine yetişmesi hesaplanmaz.
- Dönüş listesi olmayan hatlar için gidiş sırası ters çevrilerek dönüş üretilmez.
- Nominatim her özel işletme, yapı veya yazım biçimi için sonuç döndürmeyebilir.
- Gemini kota veya servis hataları adres çözümleme akışını kesintiye uğratabilir.
- Mevcut test sonuçları tüm adreslerde, hatlarda ve yük koşullarında aynı başarıyı garanti etmez.

## Planlanan Çalışmalar

- Doğal dil ve koordinat rota akışına tek aktarmalı aramanın bağlanması
- Geliştirmede kullanılmamış adres ve rota örnekleriyle bağımsız değerlendirme
- Belirsiz adresler ve durak adayları için kullanıcı seçimi
- Doğal dil uçlarının yanıt süresinin iyileştirilmesi
- Eşzamanlı yük ve kaynak tüketimi ölçümleri
- Flutter mobil uygulaması
- Haritada durak ve güzergâh gösterimi
- Konum takibi ve durak yaklaşım uyarıları

## Veri Kaynakları ve Atıf

- [MOTAŞ Hatlar](https://motas.com.tr/ulasim/hatlar)
- Adres araması: OpenStreetMap Nominatim
- Harita verisi: © OpenStreetMap contributors
- [OpenStreetMap telif ve lisans bilgileri](https://www.openstreetmap.org/copyright)

Nominatim kullanımı sırasında istekler sınırlandırılır ve sonuçlar önbelleğe alınır.

## Geliştiren

Asel Ünlü — İnönü Üniversitesi, Bilgisayar Mühendisliği
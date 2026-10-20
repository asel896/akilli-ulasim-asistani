## Veri Toplama ve Veritabanı Tasarımı

### Veri Kaynağı ve Toplama Süreci

Projenin ilk aşamasında, Malatya’daki toplu taşıma hatlarının ve duraklarının uygulamada kullanılabilecek bir veri yapısına dönüştürülmesi amaçlanmıştır. Veri kaynağı olarak MOTAŞ’ın resmî internet sitesindeki hat listesi ve hat detay sayfaları kullanılmıştır.

Veri toplama işlemleri Python ile gerçekleştirilmiştir. Web sayfalarına erişmek için Requests, HTML içeriğini incelemek için BeautifulSoup kütüphanesinden yararlanılmıştır. İlk olarak hat listesi sayfasından 124 farklı hat detay bağlantısı elde edilmiştir. Ardından örnek olarak seçilen 2A hattı üzerinde veri yapısı incelenmiştir.

İnceleme sırasında, ilk HTML çıktısında durak listesinin yalnızca ilk 10 kaydının görüntülendiği belirlenmiştir. Sayfanın kaynak kodunda bulunan yapılandırılmış veri alanları incelendiğinde ise gidiş ve dönüş durak listelerinin tamamına erişilmiştir. Böylece tarayıcı üzerindeki “Tüm Durakları Göster” düğmesini otomatik olarak kullanmadan verilerin alınması sağlanmıştır.

Geliştirilen veri toplama kodu önce üç hat üzerinde denenmiş, ardından elde edilen 124 bağlantıya uygulanmıştır. İstekler arasında iki saniyelik bekleme süresi bırakılmıştır. Her hattın verisi ayrı bir JSON dosyasına kaydedilmiştir. Bu dosyalarda hat bilgileri, mevcut gidiş ve dönüş durak listeleri, durak koordinatları ve güzergâh verileri korunmuştur.

### Veri Doğrulama

Toplanan veriler veritabanına aktarılmadan önce kontrol edilmiştir. Kontrollerde JSON dosyalarının okunabilirliği, yön listelerinin varlığı, durak kodları, durak adları ve koordinatların sayısal geçerliliği incelenmiştir. Enlem ve boylam değerlerinin geçerli aralıklarda bulunması kontrol edilmiş; iki değerin birlikte sıfır olması geçersiz kabul edilmiştir.

| Kontrol | Sonuç |
|---|---:|
| Okunan hat dosyası | 124 |
| Benzersiz durak kodu | 3.820 |
| Hat, yön ve sıra bazında durak kaydı | 10.323 |
| Dönüş durak listesi boş olan hat | 37 |
| Aynı durak kodunda ad veya koordinat farklılığı | 0 |
| Güzergâh varyantı | 211 |
| Güzergâh koordinat noktası | 110.069 |


Dönüş listesi boş olan 37 hattın güzergâh bilgileri ayrıca incelenmiştir. Bu hatların 36’sında güzergâh başlığının “RİNG”, 100 kodlu hatta ise “GÖREVLİ” olarak tanımlandığı görülmüştür. Bu nedenle boş dönüş listeleri doğrudan veri toplama hatası olarak değerlendirilmemiştir. Kaynakta bulunmayan dönüş listeleri, gidiş listesi ters çevrilerek üretilmemiştir.

Aynı durak kodunun farklı hatlarda farklı bilgilerle bulunup bulunmadığı da kontrol edilmiştir. İncelenen 3.820 benzersiz durak kodunda ad veya koordinat çelişkisine rastlanmamıştır. Bu sonuç, toplanan dosyalar arasındaki tutarlılığı göstermektedir; koordinatların sahadaki doğruluğunu veya verilerin güncelliğini tek başına kanıtlamamaktadır.

### Veritabanı Tasarımı

Toplanan verilerin saklanması için PostgreSQL kullanılmış ve `akilli_ulasim` adlı veritabanı oluşturulmuştur. İlk veritabanı yapısı üç ilişkili tablodan meydana gelmektedir.

Güzergâh verilerinin saklanması için veritabanına iki tablo daha
eklenmiştir. guzergahlar tablosunda hatların güzergâh varyantları,
kaynak yönleri, başlıkları ve diğer güzergâh bilgileri tutulmaktadır.
guzergah_noktalari tablosunda ise her güzergâhın koordinatları
kaynaktaki sıra bilgisiyle saklanmaktadır.

| Tablo | Saklanan bilgiler |
|---|---|
| `hatlar` | Hat kodu, hat adı ve kaynak sayfanın slug değeri |
| `duraklar` | Durak kodu, durak adı, enlem ve boylam |
| `hat_duraklar` | Hat kodu, yön, durak sırası ve durak kodu |

Bir durağın birden fazla hatta bulunabilmesi nedeniyle durak bilgileri ayrı bir tabloda tutulmuştur. Hatlarla duraklar arasındaki ilişki, `hat_duraklar` tablosu üzerinden kurulmuştur. Bu tabloda birincil anahtar, hat kodu, yön ve sıra alanlarının birleşiminden oluşturulmuştur. Böylece aynı durağın bir güzergâhta farklı sıralarda tekrar bulunabilmesi korunmuştur.

Tablolar arasındaki bağlantılar yabancı anahtarlarla tanımlanmıştır. Ayrıca yön, sıra ve koordinat alanlarına geçerlilik kısıtları eklenmiştir. Bir duraktan geçen hatların sorgulanmasını desteklemek amacıyla bağlantı tablosundaki durak kodu alanı üzerinde indeks oluşturulmuştur.

### Verilerin Aktarılması ve Kontrolü

JSON dosyalarındaki veriler, Psycopg kütüphanesi kullanılarak PostgreSQL’e aktarılmıştır. Bağlantı bilgileri `.env` dosyasında tutulmuş ve bu dosya Git takibi dışında bırakılmıştır. Türkçe karakterlerin aktarımında karşılaşılan kodlama sorunu, Python bağlantısında istemci kodlamasının UTF-8 olarak ayarlanmasıyla giderilmiştir.

Aktarım tek bir işlem kapsamında yürütülmüş ve hata durumunda o çalıştırmadaki değişikliklerin geri alınması sağlanmıştır. Mevcut birincil anahtarlarla çakışan kayıtlar tekrar eklenmemiştir. Hazırlanan aktarım kodu ilk veri yüklemesine yöneliktir; mevcut kayıtları güncelleme veya kaynakta kaldırılan kayıtları silme işlemlerini kapsamamaktadır.

Aktarım sonunda veritabanında 124 hat, 3.820 durak ve 10.323 hat-durak ilişkisi bulunduğu doğrulanmıştır. Ek olarak, 2A hattının gidiş yönü sorgulanmış ve beklenen 24 durak sıralı biçimde elde edilmiştir.

### İlk Aşamanın Kapsamı ve Sınırlılıkları

Bu aşamada, kaynak siteden elde edilen 124 hat bağlantısının verileri toplanmış, temel kontrolleri yapılmış ve hat-durak ilişkileri veritabanına aktarılmıştır. Güzergâh verileri de PostgreSQL’e aktarılmış; 211 güzergâh varyantı ve 110.069 koordinat noktası kaydedilmiştir. Kaynak JSON dosyalarıyla yapılan karşılaştırmada eksik veya fazla nokta bulunmamış, eşleşen noktalarda koordinat farklılığına rastlanmamıştır. Bu kontrol aktarım tutarlılığını göstermekte olup güzergâhların sahadaki doğruluğunu kanıtlamamaktadır.

Elde edilen bağlantı sayısı, kaynak sistemdeki tüm aktif yolcu hatlarının kapsandığını tek başına göstermemektedir. Bu nedenle proje önerisindeki en az yüzde 90 veri kapsamı hedefinin doğrulanması için kapsamın ayrıca değerlendirilmesi gerekmektedir. “GÖREVLİ” olarak tanımlanan hattın yolcu yönlendirmesinde kullanılıp kullanılmayacağı da hizmet türü doğrulandıktan sonra belirlenecektir.
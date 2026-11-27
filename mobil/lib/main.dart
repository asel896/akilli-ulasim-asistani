import 'dart:async';
import 'dart:convert';

import 'package:material_ui/material_ui.dart';
import 'package:http/http.dart' as http;

void main() => runApp(const UlasimApp());

class UlasimApp extends StatelessWidget {
  const UlasimApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Akıllı Ulaşım',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: Colors.teal,
        ),
        useMaterial3: true,
      ),
      home: const RotaEkrani(),
    );
  }
}

class RotaEkrani extends StatefulWidget {
  const RotaEkrani({super.key});

  @override
  State<RotaEkrani> createState() => _RotaEkraniState();
}

class _RotaEkraniState extends State<RotaEkrani> {
  final _form = GlobalKey<FormState>();
  final _baslangic = TextEditingController();
  final _hedef = TextEditingController();

  bool _yukleniyor = false;
  String? _mesaj;
  Map<String, dynamic>? _sonuc;
  http.Client? _istemci;

  Map<String, dynamic> _nesne(dynamic deger) {
    return deger is Map
        ? Map<String, dynamic>.from(deger)
        : <String, dynamic>{};
  }

  List<dynamic> _liste(dynamic deger) {
    return deger is List ? deger : <dynamic>[];
  }

  String _durakAdi(dynamic deger) {
    final ad = _nesne(deger)['durak_adi']?.toString();

    if (ad == null || ad.trim().isEmpty) {
      return 'Durak bilgisi yok';
    }

    return ad
        .replaceFirst(
          RegExp(r'^\s*\d+\s*[-–]\s*'),
          '',
        )
        .trim();
  }

  String _yon(dynamic deger) {
    return switch (deger) {
      'gidis' => 'Gidiş',
      'donus' => 'Dönüş',
      _ => deger?.toString() ?? '',
    };
  }

  List<Map<String, dynamic>> _secimDuraklari(
    Map<String, dynamic> konum,
  ) {
    final oneriler = _liste(konum['durak_onerileri']);

    final kaynak = oneriler.isNotEmpty
        ? oneriler
        : _liste(konum['ayni_adli_duraklar']);

    return kaynak
        .whereType()
        .map((d) => _nesne(d))
        .where(
          (d) =>
              d['durak_kodu'] != null &&
              d['durak_adi'] != null &&
              d['durak_adi'].toString().trim().isNotEmpty,
        )
        .toList();
  }

  List<Map<String, dynamic>> _yerAdaylari(
    Map<String, dynamic> konum,
  ) {
    return _liste(konum['yer_adaylari'])
        .whereType()
        .map((y) => _nesne(y))
        .where(
          (y) =>
              y['yer_id'] != null &&
              y['ad'] != null &&
              y['ad'].toString().trim().isNotEmpty,
        )
        .toList();
  }

  bool _secimGerekiyor(
    Map<String, dynamic> konum,
    String tercih,
    int? yerId,
  ) {
    if (yerId == null &&
        konum['cozum_turu'] == 'yer_secimi_gerekli' &&
        _yerAdaylari(konum).isNotEmpty) {
      return true;
    }

    if (tercih != 'otomatik' ||
        konum['cozum_turu'] == 'geocoding' ||
        konum['cozum_turu'] == 'durak_eslesmesi') {
      return false;
    }

    return _secimDuraklari(konum).isNotEmpty;
  }

  Future<String?> _konumSec(
    String baslik,
    Map<String, dynamic> konum,
  ) {
    final ad =
        konum['anlasilan_yer']?.toString() ?? 'Bu yer';

    final koordinat = _nesne(
      konum['adres_koordinati'],
    );

    final lat = koordinat['enlem'];
    final lon = koordinat['boylam'];

    final adresVar =
        lat is num &&
        lon is num &&
        lat.isFinite &&
        lon.isFinite &&
        lat >= -90 &&
        lat <= 90 &&
        lon >= -180 &&
        lon <= 180;

    final bulunanAdres =
        koordinat['bulunan_adres']?.toString();

    final durakAdlari = _secimDuraklari(konum)
        .map((d) => _durakAdi(d))
        .toSet()
        .toList();

    final yerAdaylari = _yerAdaylari(konum);

    return showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (dialogContext) => AlertDialog(
        title: Text('$baslik için konum seç'),
        content: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Aranan yer: $ad'),
              const SizedBox(height: 12),
              Text(
                yerAdaylari.isNotEmpty
                    ? 'Birden fazla yer eşleşti. Gitmek istediğin yeri seç.'
                    : adresVar
                        ? 'Bulunan duraklardan birini veya '
                            'yerin adresini seçebilirsin.'
                        : 'Bu ad için adres konumu bulunamadı. '
                            'Aşağıdaki duraklardan biri gitmek '
                            'istediğin yerse onu seçebilirsin.',
              ),
              if (yerAdaylari.isNotEmpty) ...[
                const SizedBox(height: 16),
                const Text('Eşleşen yerler:'),
                const SizedBox(height: 8),
                for (final yer in yerAdaylari)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: FilledButton(
                      onPressed: () {
                        Navigator.pop(
                          dialogContext,
                          'yer|${yer['yer_id']}',
                        );
                      },
                      child: Text(yer['ad'].toString()),
                    ),
                  ),
              ],
              if (durakAdlari.isNotEmpty) ...[
                const SizedBox(height: 16),
                const Text('Bulunan otobüs durakları:'),
                const SizedBox(height: 8),
                for (final durakAdi in durakAdlari)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: FilledButton(
                      onPressed: () {
                        Navigator.pop(
                          dialogContext,
                          'durak|$durakAdi',
                        );
                      },
                      child: Text(durakAdi),
                    ),
                  ),
              ],
              if (yerAdaylari.isEmpty) ...[
                const SizedBox(height: 8),
                OutlinedButton(
                  onPressed: adresVar
                      ? () {
                          Navigator.pop(
                            dialogContext,
                            'adres',
                          );
                        }
                      : null,
                  child: Text(
                    adresVar
                        ? 'Yerin kendisi / adresi'
                        : 'Adres konumu bulunamadı',
                  ),
                ),
                if (adresVar &&
                    bulunanAdres != null &&
                    bulunanAdres.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  Text(
                    'Haritada bulunan yer:\n$bulunanAdres',
                  ),
                ],
                if (!adresVar) ...[
                  const SizedBox(height: 12),
                  const Text(
                    'Hiçbiri doğru değilse vazgeçip '
                    'yer adını daha ayrıntılı yaz.',
                  ),
                ],
              ],
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.pop(dialogContext);
            },
            child: const Text('Vazgeç'),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _istemci?.close();
    _baslangic.dispose();
    _hedef.dispose();
    super.dispose();
  }

  Future<void> _rotaAra() async {
    if (_yukleniyor ||
        !(_form.currentState?.validate() ?? false)) {
      return;
    }

    FocusScope.of(context).unfocus();

    setState(() {
      _yukleniyor = true;
      _mesaj = null;
      _sonuc = null;
    });

    var basAd = _baslangic.text.trim();
    var hedefAd = _hedef.text.trim();
    var basTercih = 'otomatik';
    var hedefTercih = 'otomatik';
    int? basYerId;
    int? hedefYerId;

    final istemci = http.Client();
    _istemci = istemci;

    try {
      while (true) {
        final cevap = await istemci
            .post(
              Uri.parse(
                'http://127.0.0.1:8000/rota/dogal-dil',
              ),
              headers: {
                'Content-Type':
                    'application/json; charset=utf-8',
              },
              body: jsonEncode({
                'soru':
                    '$basAd konumundan '
                    '$hedefAd konumuna nasıl giderim?',
                'baslangic_turu': basTercih,
                'hedef_turu': hedefTercih,
                'baslangic_yer_id': basYerId,
                'hedef_yer_id': hedefYerId,
                'yaricap_metre': 400,
                'aday_limiti': 10,
                'sonuc_limiti': 15,
              }),
            )
            .timeout(const Duration(seconds: 45));

        if (cevap.statusCode == 429) {
          throw Exception(
            'Adres çözümleme servisinin kullanım sınırına '
            'ulaşıldı. Daha sonra tekrar dene.',
          );
        }

        if (cevap.statusCode == 503) {
          throw Exception(
            'Servis şu an kullanılamıyor. Tekrar dene.',
          );
        }

        if (cevap.statusCode != 200) {
          throw Exception(
            'İstek tamamlanamadı '
            '(HTTP ${cevap.statusCode}).',
          );
        }

        final veri = jsonDecode(
          utf8.decode(cevap.bodyBytes),
        );

        if (veri is! Map<String, dynamic>) {
          throw const FormatException();
        }

        if (!mounted) return;

        final basKonum = _nesne(veri['baslangic']);
        final hedefKonum = _nesne(veri['hedef']);
        var yenidenAra = false;

        if (_secimGerekiyor(basKonum, basTercih, basYerId)) {
          final secim = await _konumSec(
            'Başlangıç',
            basKonum,
          );

          if (!mounted) return;

          if (secim == null) {
            setState(() {
              _mesaj = 'Arama iptal edildi.';
            });
            return;
          }

          if (secim.startsWith('yer|')) {
            basYerId = int.tryParse(secim.substring(4));
            basTercih = 'adres';
          } else if (secim.startsWith('durak|')) {
            basTercih = 'durak';
            basAd = secim.substring(6);
          } else {
            basTercih = 'adres';
            basAd =
                basKonum['anlasilan_yer']?.toString() ??
                basAd;
          }

          yenidenAra = true;
        }

        if (_secimGerekiyor(hedefKonum, hedefTercih, hedefYerId)) {
          final secim = await _konumSec(
            'Hedef',
            hedefKonum,
          );

          if (!mounted) return;

          if (secim == null) {
            setState(() {
              _mesaj = 'Arama iptal edildi.';
            });
            return;
          }

          if (secim.startsWith('yer|')) {
            hedefYerId = int.tryParse(secim.substring(4));
            hedefTercih = 'adres';
          } else if (secim.startsWith('durak|')) {
            hedefTercih = 'durak';
            hedefAd = secim.substring(6);
          } else {
            hedefTercih = 'adres';
            hedefAd =
                hedefKonum['anlasilan_yer']?.toString() ??
                hedefAd;
          }

          yenidenAra = true;
        }

        if (yenidenAra) {
          continue;
        }

        final hatalar = _liste(veri['hatalar']).join('\n');

        setState(() {
          _sonuc = veri;
          _mesaj = hatalar.isNotEmpty
              ? hatalar
              : veri['mesaj']?.toString() ??
                    'Arama tamamlandı.';
        });

        break;
      }
    } on TimeoutException {
      _hataGoster(
        'Yanıt zaman aşımına uğradı. Tekrar dene.',
      );
    } on http.ClientException {
      _hataGoster(
        'Sunucuya bağlanılamadı. '
        'FastAPI’nin açık olduğunu kontrol et.',
      );
    } on FormatException {
      _hataGoster(
        'Sunucudan beklenen biçimde yanıt alınamadı.',
      );
    } catch (hata) {
      _hataGoster(
        hata.toString().replaceFirst('Exception: ', ''),
      );
    } finally {
      istemci.close();

      if (identical(_istemci, istemci)) {
        _istemci = null;
      }

      if (mounted) {
        setState(() {
          _yukleniyor = false;
        });
      }
    }
  }

  void _hataGoster(String mesaj) {
    if (!mounted) return;

    setState(() {
      _mesaj = mesaj;
    });
  }

  Widget _anlasilanKonum(
    String alan,
    String baslik,
  ) {
    final konum = _nesne(_sonuc?[alan]);
    final adres = _nesne(konum['adres_koordinati']);
    final cozum = konum['cozum_turu'];

    final satirlar = <String>[
      '$baslik: '
          '${konum['anlasilan_yer'] ?? 'Belirlenemedi'}',
    ];

    if (cozum == 'geocoding') {
      satirlar.add('Yer/adres konumu kullanılıyor.');

      final bulunan =
          adres['bulunan_adres']?.toString();

      if (bulunan != null && bulunan.isNotEmpty) {
        satirlar.add(bulunan);
      }

      final kapsam =
          konum['arama_kapsami']?.toString();

      if (kapsam != null && kapsam.isNotEmpty) {
        satirlar.add(kapsam);
      }
    } else if (cozum == 'durak_eslesmesi') {
      satirlar.add('Durak eşleşmesi kullanılıyor.');
    } else {
      satirlar.add('Konum çözümlenemedi.');
    }

    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: Text(satirlar.join('\n')),
    );
  }

  Widget _erisimMesafesi(
    Map<String, dynamic> durak,
    String aciklama,
  ) {
    if (durak['alan_icinde'] == true) {
      return const Padding(
        padding: EdgeInsets.only(top: 6),
        child: Text(
          'Durak, seçilen yerin harita alanı içinde. '
          'Belirli binaya yürüyüş mesafesi hesaplanmadı.',
        ),
      );
    }

    final mesafe = durak['mesafe_metre'];

    if (mesafe is! num ||
        !mesafe.isFinite ||
        mesafe < 0) {
      return const SizedBox.shrink();
    }

    return Padding(
      padding: const EdgeInsets.only(top: 6),
      child: Text(
        '$aciklama yaklaşık ${mesafe.round()} m '
        '(kuş uçuşu; yürüyüş mesafesi değildir).',
      ),
    );
  }

    Widget _binisSecenekleri(Map<String, dynamic> secenek) {
    final adaylar = _liste(secenek['uygun_binis_duraklari'])
        .whereType<Map>()
        .map((d) => _nesne(d))
        .where(
          (d) => (d['durak_kodu']?.toString() ?? '').isNotEmpty,
        )
        .toList();

    if (adaylar.length < 2) {
      return const SizedBox.shrink();
    }

    final secili = _nesne(secenek['binis_duragi']);
    final aktarmali = secenek['birinci_hat'] is Map;

    final seciliSira = aktarmali
        ? _nesne(secenek['birinci_hat'])['binis_sirasi']
        : secenek['binis_sirasi'];

    return ExpansionTile(
      tilePadding: EdgeInsets.zero,
      title: const Text('Binebileceğin diğer duraklar'),
      subtitle: Text(
        aktarmali
            ? 'Karttaki aktarma noktasına ulaşabilen duraklar.'
            : 'Karttaki iniş durağına ulaşabilen duraklar.',
      ),
      children: [
        const Padding(
          padding: EdgeInsets.only(bottom: 8),
          child: Text(
            'Başlangıç alanına uyan duraklar listelenir. '
            'Bir durak seçersen rota yeniden hesaplanır.',
          ),
        ),
        for (final d in adaylar)
          ListTile(
            leading: const Icon(Icons.location_on_outlined),
            title: Text(_durakAdi(d)),
            subtitle:
                d['durak_kodu'].toString() ==
                        secili['durak_kodu']?.toString() &&
                    d['binis_sirasi'] == seciliSira
                ? const Text('Kartta gösterilen biniş durağı')
                : null,
            trailing: const Icon(Icons.chevron_right),
            onTap: _yukleniyor
                ? null
                : () {
                    final kod = d['durak_kodu'].toString();
                    _baslangic.text = '$kod kodlu durak';
                    _rotaAra();
                  },
          ),
      ],
    );
  }

  Widget _rotaKarti(Map<String, dynamic> secenek) {
    final aktarmali =
        _sonuc?['sonuc_turu'] == 'tek_aktarma';

    final birinci = _nesne(secenek['birinci_hat']);
    final ikinci = _nesne(secenek['ikinci_hat']);
    final aktarma = _nesne(secenek['aktarma']);
    final binis = _nesne(secenek['binis_duragi']);
    final inis = _nesne(secenek['inis_duragi']);
    final mesafe = aktarma['yaklasik_mesafe_metre'];

    final uygunInisler =
        _liste(secenek['uygun_inis_duraklari'])
            .whereType()
            .map((d) => _nesne(d))
            .toList();

    final baslik = aktarmali
        ? '${birinci['hat_kodu']} → ${ikinci['hat_kodu']}'
        : secenek['hat_kodu']?.toString() ?? 'Hat';

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              baslik,
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 8),
            Text(
              aktarmali ? 'Tek aktarma' : 'Doğrudan',
            ),
            if (!aktarmali)
              Text(_yon(secenek['yon'])),
            const SizedBox(height: 12),
            Text(
              'Biniş: ${_durakAdi(binis)}',
            ),
            _erisimMesafesi(
              binis,
              'Başlangıç konumundan biniş durağına',
            ),
            _binisSecenekleri(secenek),
            if (aktarmali) ...[
              const SizedBox(height: 12),
              Text(
                '${birinci['hat_kodu']} — '
                '${_yon(birinci['yon'])}',
              ),
              Text(
                'Aktarma için iniş: '
                '${_durakAdi(aktarma['inilecek_durak'])}',
              ),
              Text(
                'İkinci araca biniş: '
                '${_durakAdi(aktarma['binilecek_durak'])}',
              ),
              Text(
                '${ikinci['hat_kodu']} — '
                '${_yon(ikinci['yon'])}',
              ),
              if (mesafe is num &&
                  mesafe.isFinite &&
                  mesafe >= 0)
                Text(
                  'Aktarma arası yaklaşık '
                  '${mesafe.round()} m (kuş uçuşu).',
                ),
            ],
            const SizedBox(height: 12),
            Text(
              'İniş: ${_durakAdi(inis)}',
            ),
            _erisimMesafesi(
              inis,
              'İniş durağından hedefin haritada '
              'bulunan konumuna',
            ),
            if (!aktarmali && uygunInisler.length > 1)
              ExpansionTile(
                tilePadding: EdgeInsets.zero,
                title: const Text(
                  'Bu hatla ulaşılabilen hedef durakları',
                ),
                children: [
                  for (final d in uygunInisler)
                    ListTile(
                      leading: const Icon(
                        Icons.location_on_outlined,
                      ),
                      title: Text(_durakAdi(d)),
                      subtitle:
                          d['durak_kodu'] == inis['durak_kodu']
                          ? const Text(
                              'Kartta gösterilen iniş durağı',
                            )
                          : null,
                    ),
                ],
              ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final liste = _liste(_sonuc?['secenekler']);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Akıllı Ulaşım Asistanı'),
      ),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(
              maxWidth: 760,
            ),
            child: ListView(
              padding: const EdgeInsets.all(20),
              children: [
                Text(
                  'Nereye gitmek istiyorsun?',
                  style:
                      Theme.of(context).textTheme.headlineSmall,
                ),
                const SizedBox(height: 8),
                const Text(
                  'Yer veya durak adını yaz. '
                  'Tam adres bilmen gerekmiyor.',
                ),
                const SizedBox(height: 20),
                Form(
                  key: _form,
                  child: Column(
                    children: [
                      TextFormField(
                        controller: _baslangic,
                        enabled: !_yukleniyor,
                        decoration: const InputDecoration(
                          labelText: 'Başlangıç',
                          hintText: 'Örnek: Nikah Sarayı',
                          prefixIcon: Icon(
                            Icons.trip_origin,
                          ),
                          border: OutlineInputBorder(),
                        ),
                        textInputAction: TextInputAction.next,
                        validator: (v) =>
                            v == null || v.trim().isEmpty
                            ? 'Başlangıç yerini yaz.'
                            : null,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        controller: _hedef,
                        enabled: !_yukleniyor,
                        decoration: const InputDecoration(
                          labelText: 'Hedef',
                          hintText:
                              'Örnek: İnönü Üniversitesi',
                          prefixIcon: Icon(
                            Icons.place_outlined,
                          ),
                          border: OutlineInputBorder(),
                        ),
                        textInputAction: TextInputAction.search,
                        onFieldSubmitted: (_) => _rotaAra(),
                        validator: (v) =>
                            v == null || v.trim().isEmpty
                            ? 'Hedef yerini yaz.'
                            : null,
                      ),
                      const SizedBox(height: 20),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton.icon(
                          onPressed:
                              _yukleniyor ? null : _rotaAra,
                          icon: const Icon(Icons.route),
                          label: Text(
                            _yukleniyor
                                ? 'Aranıyor…'
                                : 'Rota bul',
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                if (_yukleniyor) ...[
                  const SizedBox(height: 16),
                  const LinearProgressIndicator(),
                ],
                if (_mesaj != null) ...[
                  const SizedBox(height: 20),
                  Text(_mesaj!),
                ],
                if (_sonuc != null) ...[
                  _anlasilanKonum(
                    'baslangic',
                    'Anlaşılan başlangıç',
                  ),
                  _anlasilanKonum(
                    'hedef',
                    'Anlaşılan hedef',
                  ),
                ],
                const SizedBox(height: 12),
                ...liste.map(
                  (s) => _rotaKarti(_nesne(s)),
                ),
                if (liste.isNotEmpty)
                  const Padding(
                    padding: EdgeInsets.only(top: 12),
                    child: Text(
                      'Harita alanı veya noktası, özellikle '
                      'geniş yerlerde gitmek istediğin binayı '
                      'kesin olarak belirtmez. Belirli bir bina '
                      'veya fakülte için adını açıkça yaz.\n\n'
                      'Sefer saatlerinin aktarmaya uygunluğu '
                      'hesaplanmaz. Listelenen seçenekler '
                      'en hızlı rota garantisi vermez.',
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}


# vt tablolarini olusturan sql. baska bilgisayarda ayni vt olusturmak icin

CREATE TABLE hatlar (
    hat_kodu VARCHAR(30) PRIMARY KEY,
    hat_adi TEXT NOT NULL,
    slug TEXT NOT NULL UNIQUE,
    kaynak_aktif BOOLEAN,
    kaynak_kategori TEXT,
    hizmet_turu TEXT NOT NULL DEFAULT 'belirsiz',


    CONSTRAINT hatlar_hizmet_turu_kontrol
        CHECK (
            hizmet_turu IN ('ring', 'gorevli', 'belirsiz')
        )
);

CREATE TABLE duraklar (
    durak_kodu VARCHAR(30) PRIMARY KEY,
    durak_adi TEXT NOT NULL,
    enlem DOUBLE PRECISION NOT NULL,
    boylam DOUBLE PRECISION NOT NULL,

    CHECK (enlem BETWEEN -90 AND 90),
    CHECK (boylam BETWEEN -180 AND 180),
    CHECK (enlem <> 0 OR boylam <> 0)
);

CREATE TABLE hat_duraklar (
    hat_kodu VARCHAR(30) NOT NULL,
    yon VARCHAR(10) NOT NULL,
    sira INTEGER NOT NULL,
    durak_kodu VARCHAR(30) NOT NULL,

    PRIMARY KEY (hat_kodu, yon, sira),

    FOREIGN KEY (hat_kodu)
        REFERENCES hatlar(hat_kodu),

    FOREIGN KEY (durak_kodu)
        REFERENCES duraklar(durak_kodu),

    CHECK (yon IN ('gidis', 'donus')),
    CHECK (sira > 0)
);

CREATE INDEX idx_hat_duraklar_durak_kodu
ON hat_duraklar(durak_kodu);



CREATE TABLE guzergahlar (
    guzergah_id BIGINT PRIMARY KEY,
    hat_kodu VARCHAR(30) NOT NULL,
    kaynak_kodu TEXT,
    baslik TEXT,
    kaynak_yon TEXT NOT NULL,
    ana_guzergah BOOLEAN,
    sure_dakika DOUBLE PRECISION,
    uzunluk_km DOUBLE PRECISION,

    FOREIGN KEY (hat_kodu)
        REFERENCES hatlar(hat_kodu)
);

CREATE TABLE guzergah_noktalari (
    guzergah_id BIGINT NOT NULL,
    sira INTEGER NOT NULL,
    enlem DOUBLE PRECISION NOT NULL,
    boylam DOUBLE PRECISION NOT NULL,

    PRIMARY KEY (guzergah_id, sira),

    FOREIGN KEY (guzergah_id)
        REFERENCES guzergahlar(guzergah_id),

    CHECK (sira > 0),
    CHECK (enlem BETWEEN -90 AND 90),
    CHECK (boylam BETWEEN -180 AND 180),
    CHECK (enlem <> 0 OR boylam <> 0)
);

CREATE INDEX idx_guzergahlar_hat_kodu
ON guzergahlar(hat_kodu);

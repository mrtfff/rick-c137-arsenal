# Rick C-137 Gadget Logger & Arsenal

Multiverse üzerindeki tüm C-137 Rick icatlarini, silahlarini ve deneysel teknolojilerini anlik ekran yakalama ile arsivleyen sistem.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue?style=for-the-badge&logo=python)
![GUI](https://img.shields.io/badge/GUI-Tkinter-green?style=for-the-badge)
![Pillow](https://img.shields.io/badge/Image-Pillow-orange?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-purple?style=for-the-badge)

---

## ARSENAL ISTATISTIKLERI (CANLI VERI)

<!-- STATS:START -->
| Metrik | Deger |
| :--- | :--- |
| Toplam Kayitli Icat / Silah | **43** |
| Taranan Sezon Sayisi | **2** (Sezon 01 - 02) |
| Taranan Bölüm Sayisi | **11** |
| C-137 Onayli Icat Orani | **%95** (41/43) |

### Kategori Dagilimi
- **Elde Taşınır Silah / Cihaz:** 18 adet
- **Sibernetik / Vücut İmplantı:** 0 adet
- **Araç / Taşıt / Uyarlama:** 1 adet
- **Garaj / Laboratuvar Ekipmanı:** 4 adet
- **Giyilebilir Ekipman / Zırh / Jetpack:** 8 adet
- **Biyolojik / Genetik / Kimyasal İcat:** 4 adet
- **Diğer / Özel İcat:** 7 adet
- **Emin Değilim / Bilinmiyor:** 0 adet
- **mekiğe takılı cihazlar:** 1 adet

### Tehdit Seviyesi Dagilimi
- **[0] Zararsız / İşlevsel:** 15 adet
- **[1] Dolaylı Tehlike / Taktiksel:** 11 adet
- **[2] Kişisel / Doğrudan Hasar:** 8 adet
- **[3] Kitle / Bölgesel Tahrip:** 4 adet
- **[4] Gezegen / Medeniyet Tehdidi:** 1 adet
- **[5] Evrensel / Gerçeklik Bükücü:** 0 adet
- **[99] Emin Değilim / Bilinmiyor:** 4 adet
<!-- STATS:END -->

---

## MODÜLLER VE KULLANIM

### 1. Ana Uygulama (`main.py`)
Rick and Morty izlerken ekran görüntüsü yakalayip hizlica veritabanina eklemek için kullanilir.

```bash
python main.py
```

| Kontrol | Eylem |
| :--- | :--- |
| **`x` Tusu** | Ekran yakalama akisini baslatir (Input kutularinda yazarken tetiklenmez). |
| **1/2 Seçim** | Tam sahne alanini çiz (Iptal için `ESC` veya `Sag Tik`). |
| **2/2 Seçim** | Sadece aletin/silahin odak alanini çiz. |
| **Form Kayit** | Sezon, bölüm, zaman kodu (`MM:SS`) ve kategoriyi seçip `KAYDET` butonuna bas. |

---

### 2. Görüntüleyici ve Düzenleyici (`viewer.py`)
Kayitli icatlari incelemek, filtrelemek ve verileri güncellemek için kullanilir.

```bash
python viewer.py
```

* **Canli Arama:** Isim, Tag ID, sezon/bölüm veya açiklamaya göre anlik filtreleme.
* **Çift Önizleme:** Tam sahne ve odak resimlerini yan yana görme, üzerine tiklayarak tam ekran inceleme.
* **Düzenleme & Silme:** Kayitli verileri güncelleme veya veritabanindan/diskten kaldirma.
* **Git Push:** Degisiklikleri tek tikla GitHub'a gönderme.

---

### 3. Istatistik Güncelleyici (`update_readme.py`)
`README.md` dosyasindaki veri istatistiklerini `data/gadgets.json` verilerine göre dinamik olarak günceller.

```bash
python update_readme.py
```

---

## VERI ARSIV YAPISI (`data/gadgets.json`)

Ekran görüntüleri `assets/season_XX/episode_YY/` klasör yapisinda otomatik depolanir. JSON verisi su formattadir:

```json
{
  "id": "tag#003",
  "name": "portal gun",
  "season": 1,
  "episode": 1,
  "timestamp": "07:36",
  "category_id": 0,
  "c137_confirmed": true,
  "description": "Can travel anywhere and everywhere",
  "images": {
    "full": "assets/season_01/episode_01/tag#003_full.png",
    "focus": "assets/season_01/episode_01/tag#003_focus.png"
  }
}
```

---

## LISANS

Bu proje [MIT Lisansi](LICENSE) altinda lisanslanmistir.

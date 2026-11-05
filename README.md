# İzmir / İstanbul ⇄ Prag kısa gezi uçuş takipçisi

ADB ⇄ PRG, IST ⇄ PRG ve SAW ⇄ PRG **aktarmasız** gidiş-dönüş fiyatlarını günde iki kez (TR saatiyle 10:30 ve 18:30) Google Flights'tan çeker.

- Ocak–Mayıs 2027 arası, gidiş ve dönüş günü dahil 3–5 günlük geziler
- Sadece en fazla **2 gün izin** gerektiren kombinasyonlar (2027 için kalkış noktası başına 184, toplam 552)
- İzin sayımı: gidiş ve dönüş günü dahil her hafta içi günü 1 izin (akşam uçuşu da olsa). Resmi tatiller izin yemez, bayram arifesi 0,5 sayılır
- Google boş sonuç döndürürse son bilinen fiyat soluk gösterilir
- Fiyatlar tek yetişkin, ekonomi, bagaj hariç, gidiş-dönüş toplam, TL
- Alarm yok; fiyatlar sadece panelde

## Dosyalar

| Dosya | Ne işe yarar |
|---|---|
| `config.json` | Kalkış noktaları, tarih aralığı, gün sayısı, izin sınırı, resmi tatiller |
| `tracker.py` | Taramayı yapar, sonuçları `docs/data.json`'a ekler |
| `docs/index.html` | Panel (GitHub Pages) |
| `.github/workflows/track.yml` | Günde 2 kez otomatik çalıştırır |

## Ayar değiştirmek

`config.json` dosyasını GitHub üzerinde düzenleyip kaydetmen yeterli; bir sonraki taramada geçerli olur.
Tarih aralığını uzatırsan `public_holidays` listesine o dönemin resmi tatillerini de ekle.

## Elle tarama başlatmak

GitHub'da **Actions → Fiyat taraması → Run workflow**.

## Yerelde çalıştırmak

```bash
pip install -r requirements.txt
python tracker.py
```

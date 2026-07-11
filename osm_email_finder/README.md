# NY Firma Email Bulucu (OpenStreetMap tabanlı)

## Bu araç ne yapar?
1. Girdiğin anahtar kelimeye göre (örn. "auto", "restaurant", "dentist") **New York eyaleti** sınırları içinde OpenStreetMap (Overpass API) üzerinden firma arar.
2. Her firma için önce OSM verisindeki isim/adres/telefon/email bilgisini alır.
3. Email yoksa ama web sitesi varsa, o web sitesinin ana sayfası + contact/about gibi sayfalarını tarayıp email adresi arar.
4. Email hâlâ bulunamazsa o firma **listeye eklenmez** (senin isteğine göre).
5. Sonuçları ekranda gösterir (ilerleme yüzdesi + bulunan email sayısı ile) ve Excel (.xlsx) olarak indirmeni sağlar.

## ÖNEMLİ — dürüst sınırlamalar
- **Google Haritalar kullanılmadı.** Google Haritalar'ı ücretsiz ve kurallara uygun şekilde toplu taramak mümkün değil (ücretli API veya ToS ihlali gerekir). Bunun yerine tamamen ücretsiz ve açık olan OpenStreetMap kullanıldı.
- **"En az 100 email" garantisi yok.** Bu, seçtiğin anahtar kelimeye ve OSM'in o bölgedeki veri yoğunluğuna bağlı. ABD'de küçük işletmelerin bir kısmı OSM'de hiç kayıtlı değildir veya telefon/website bilgisi eksiktir. Sonuç azsa, `app.py` içindeki `KEYWORD_TAG_MAP` sözlüğüne ilgili OSM etiketlerini ekleyerek kapsamı genişletebiliriz.
- **Sahte email üretilmez.** Şirket adından veya telefon numarasından "tahmini" bir email uydurmadım — bu, hatalı/yanıltıcı veri üretir. Sadece gerçekten web sitesinde bulunan adresler listeleniyor.
- Bu kod **benim ortamımda internete çıkışım kısıtlı olduğu için canlı test edilemedi** (Overpass API'ye veya gerçek firma sitelerine buradan bağlanamıyorum). Söz dizimi kontrolü yaptım ve mantığı standart, kararlı kütüphanelerle (requests, pandas, Flask) kurdum, ama sende ilk çalıştırmada beklenmedik bir hata çıkarsa hatayı bana yapıştır, hemen düzeltirim.

## Kurulum (kendi bilgisayarında, internetle)
```bash
cd osm_email_finder
pip install -r requirements.txt
python app.py
```
Sonra tarayıcıda: **http://localhost:5000**

## Kullanım
1. Arama kutusuna anahtar kelimeyi yaz (örn. `auto`).
2. "Ara" butonuna bas.
3. İlerleme çubuğunu ve bulunan email sayısını izle.
4. Bitince "Excel İndir" butonuna bas.

## Aramayı genişletmek istersen
`app.py` içindeki `KEYWORD_TAG_MAP` sözlüğüne yeni satırlar ekleyebilirsin, örnek:
```python
"plumber": ["craft=plumber"],
```
Sol taraf senin arama kutusuna yazacağın kelime (küçük harf), sağ taraf OSM etiketi.
Hangi etiketin hangi iş koluna karşılık geldiğini https://wiki.openstreetmap.org/wiki/Map_features adresinden bulabilirsin.

## Overpass API kullanım kuralları (önemli)
Overpass ücretsizdir ama aşırı yüklenmeyi önlemek için kaba kullanım kısıtlaması vardır. Kod zaten `User-Agent` gönderiyor ve istekler arasında küçük bekleme (`time.sleep`) uyguluyor. Çok sık/art arda arama yaparsan geçici olarak engellenebilirsin — bu durumda birkaç dakika bekleyip tekrar dene.

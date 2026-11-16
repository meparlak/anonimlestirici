# Kurulum rehberi

Bu rehber, bilgisayar konusunda teknik bilgisi olmayanlar için yazıldı. Kurulum yaklaşık 5 dakika sürer. Terminal ya da kod gerekmez.

Bilgisayarınıza göre ilgili bölüme geçin: [Mac'e kurulum](#mace-kurulum) · [Windows'a kurulum](#windowsa-kurulum)

> **Bilmeniz gereken:** Anonimleştirici henüz Apple'ın ve Microsoft'un ücretli geliştirici sertifikalarıyla **imzalanmamış** bir uygulama. Bu yüzden ilk açılışta macOS "Apple bu uygulamayı denetleyemiyor", Windows ise "Windows bilgisayarınızı korudu" diye bir uyarı verir ve sizden bir kez ek izin ister. Bu uyarı uygulamada bir sorun bulunduğu anlamına gelmez; Apple'ın uygulamayı incelemediğini söyler. Uygulama internete bağlanmaz, dosyalarınızı hiçbir yere göndermez ve kaynak kodunun tamamı herkesin inceleyebileceği şekilde açıktır. İleride uygulama imzalandığında bu adıma gerek kalmayacak.

# Mac'e kurulum

## Başlamadan önce: Mac'iniz uygun mu?

Anonimleştirici, Apple'ın kendi işlemcisini (M1, M2, M3, M4…) kullanan Mac'lerde çalışır. Kontrol etmek için:

1. Ekranın sol üst köşesindeki elma simgesine () tıklayın.
2. **Bu Mac Hakkında**'yı seçin.
3. Açılan pencerede **Çip** satırında "Apple M1", "Apple M2" gibi bir şey yazıyorsa Mac'iniz uygundur.

"İşlemci: Intel" yazıyorsa bu sürüm sizin Mac'inizde çalışmaz.

Ayrıca macOS 13 (Ventura) ya da daha yeni bir sürüm gerekir. Aynı pencerede **macOS** satırında sürümü görebilirsiniz.

Uygulama yaklaşık 700 MB yer kaplar. İndirme dosyası 580 MB civarındadır; internet hızınıza göre birkaç dakika sürebilir.

## 1. İndirin

[**Anonimleştirici'yi indirmek için buraya tıklayın**](https://github.com/meparlak/anonimlestirici/releases/latest/download/Anonimlestirici.dmg)

`Anonimlestirici.dmg` adlı dosya, İndirilenler (Downloads) klasörünüze kaydedilir.

Eski sürümler ve yeniliklerin listesi için [Sürümler sayfasına](https://github.com/meparlak/anonimlestirici/releases) bakabilirsiniz.

## 2. Uygulamalar klasörüne taşıyın

1. İndirilenler klasöründeki `Anonimlestirici.dmg` dosyasına çift tıklayın. Küçük bir pencere açılır.
2. Pencerede solda Anonimleştirici simgesi, sağda **Applications (Uygulamalar)** klasörü görünür.
3. Anonimleştirici simgesini fareyle tutup Applications klasörünün üzerine sürükleyip bırakın. Kopyalama birkaç saniye sürer.
4. Pencereyi kapatın. Finder'ın sol kenarında "Anonimleştirici" diye görünen diskin yanındaki çıkarma simgesine (⏏) basın.

İsterseniz artık `Anonimlestirici.dmg` dosyasını çöpe atabilirsiniz.

## 3. İlk açılış: güvenlik izni

Uygulama henüz Apple'ın ücretli geliştirici programıyla imzalanmadığı için macOS ilk açılışta uyarı verir. Bu bir defalık bir işlemdir.

1. Finder'da **Uygulamalar** klasörünü açın ve **Anonimleştirici**'ye çift tıklayın.
2. "Anonimleştirici açılamadı" ya da "Apple, … kötü amaçlı yazılım içermediğini doğrulayamıyor" diye bir uyarı çıkar. **Bitti**'ye basın. Kesinlikle "Çöp Sepetine Taşı"yı seçmeyin.
3. Elma menüsünden () **Sistem Ayarları**'nı açın.
4. Sol taraftaki listeden **Gizlilik ve Güvenlik**'e tıklayın.
5. Sağ tarafta aşağı doğru, **Güvenlik** başlığına kadar kaydırın. "Anonimleştirici, Mac'inizi korumak için engellendi" yazısını ve yanında **Yine de Aç** düğmesini göreceksiniz. Bu düğmeye basın.
6. Mac'inizin açılış parolasını girin.
7. Son bir uyarı daha çıkar; **Yine de Aç**'a basın.

Uygulama açılır. Bundan sonra her seferinde normal şekilde çift tıklayarak açabilirsiniz.

"Yine de Aç" düğmesi uygulamayı açmayı denedikten sonra yaklaşık bir saat görünür kalır. Göremezseniz 1. adımdan yeniden başlayın.

### Bu uyarı neden çıkıyor?

macOS, internetten indirilen her uygulamanın Apple'ın verdiği bir geliştirici sertifikasıyla imzalanmasını ve Apple'ın taramasından geçmesini bekler. Bunun için yıllık ücretli bir üyelik gerekiyor ve bu proje henüz o aşamada değil. Uyarı, uygulamada bir sorun bulunduğu anlamına gelmez; Apple'ın uygulamayı görmediğini söyler. Uygulamanın kaynak kodunun tamamı bu sayfada herkese açık olarak duruyor. Uygulama internete bağlanmaz ve dosyalarınızı hiçbir yere göndermez; ayrıntılar [README'deki Gizlilik bölümünde](../README.md#gizlilik-verileriniz-bilgisayarınızdan-çıkmaz).

## Güncelleme

Yeni bir sürüm çıktığında 1. ve 2. adımları tekrarlayın. Kopyalarken "Değiştir" deyin. Ayarlarınız ve listeleriniz korunur. Güvenlik izni yeni sürüm için bir kez daha istenebilir.

## Kaldırma

Uygulamalar klasöründeki Anonimleştirici'yi çöpe sürükleyin. Ayarlarınızı da silmek isterseniz Finder'da **Git → Klasöre Git…** menüsünü açın, `~/Library/Containers` yazın ve içindeki `io.github.meparlak.anonimlestirici` klasörünü çöpe atın.

# Windows'a kurulum

## Başlamadan önce: bilgisayarınız uygun mu?

Windows 10 ya da Windows 11 (64 bit) gerekir. Uygulama yaklaşık 700 MB yer kaplar; kurulum dosyası 600 MB civarındadır. Yönetici parolası gerekmez, uygulama yalnızca sizin kullanıcı hesabınıza kurulur.

## 1. İndirin

[**Windows kurulum dosyasını indirmek için buraya tıklayın**](https://github.com/meparlak/anonimlestirici/releases/latest/download/Anonimlestirici-Kurulum.exe)

Tarayıcınız "Bu dosya yaygın olarak indirilmiyor" gibi bir uyarı gösterebilir. Edge'de indirme listesindeki dosyanın yanındaki **⋯** menüsünden **Sakla**'yı, ardından **Yine de sakla**'yı seçin. Chrome'da **Sakla** deyin.

## 2. Kurun

1. İndirilenler klasöründeki `Anonimlestirici-Kurulum.exe` dosyasına çift tıklayın.
2. Mavi bir "Windows bilgisayarınızı korudu" penceresi çıkar. Penceredeki **Ek bilgi** yazısına tıklayın, ardından **Yine de çalıştır** düğmesine basın. Bu uyarı, kurulum dosyası Microsoft'un ücretli sertifikasıyla imzalanmadığı için çıkar; dosyada bir sorun olduğu anlamına gelmez.
3. Kurulum sihirbazı Türkçe açılır. Lisansı kabul edin, isterseniz masaüstü kısayolunu işaretleyin ve **Kur**'a basın.
4. Kurulum bitince **Son**'a basın. Uygulama açılır.

Bundan sonra Başlat menüsünde "Anonimleştirici" yazarak açabilirsiniz.

## Güncelleme

Yeni bir sürüm çıktığında kurulum dosyasını yeniden indirip çalıştırın; eski sürümün üzerine kurulur. Ayarlarınız ve listeleriniz korunur.

## Kaldırma

**Ayarlar → Uygulamalar → Yüklü uygulamalar** bölümünde Anonimleştirici'yi bulun ve **Kaldır**'a basın. Ayarlarınızı da silmek isterseniz Dosya Gezgini'nin adres çubuğuna `%APPDATA%\Anonimlestirici` yazıp bu klasörü silin.

## Windows'ta karşılaşılabilecek sorunlar

- **Uygulama açılıyor ama pencere boş kalıyor:** Arayüz için Microsoft Edge WebView2 gerekir. Windows 11'de ve güncel Windows 10'da hazır gelir. Eksikse kurulum sihirbazı uyarır; Microsoft'un sayfasından "Evergreen Bootstrapper"ı indirip kurmanız yeterli.
- **Kurumsal bilgisayarda kurulum engellendi:** Şirket bilgisayarlarında BT politikaları imzasız uygulamaları engelleyebilir. Bu durumda BT biriminizle görüşün.

## Sorun mu yaşıyorsunuz?

- **"Hasar görmüş, çöpe taşınmalı" uyarısı:** İndirme yarıda kalmış olabilir. Dosyayı silip yeniden indirin.
- **Uygulama açılıyor ama dosya taranmıyor:** Dosyanın Excel ya da Word'de açık olmadığından emin olun. Parola korumalı dosyalar desteklenmiyor.
- **Başka bir sorun:** [Sorun bildirme sayfasından](https://github.com/meparlak/anonimlestirici/issues) yazabilirsiniz. Lütfen gerçek kişisel veri içeren dosya paylaşmayın.

Kurulum bittiyse [kullanım kılavuzuna](KULLANIM.md) geçebilirsiniz.

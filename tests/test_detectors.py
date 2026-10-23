import pytest

from anonimlestirici.core.detectors import build_detectors
from anonimlestirici.core.detectors.patterns import iban_valid, tc_valid
from anonimlestirici.core.engine import resolve_overlaps
from anonimlestirici.core.types import EntityType as T
from anonimlestirici.core.types import Segment


def found(settings, text, hint=None, whole=False):
    out = []
    for d in build_detectors(settings):
        out += d.detect(Segment(text, "test", hint=hint, whole=whole))
    return [(f.etype, f.text) for f in resolve_overlaps(out)]


def test_tc_checksum():
    assert tc_valid("10000000078")
    assert not tc_valid("12345678901")
    assert not tc_valid("01234567890")


def test_iban_checksum():
    assert iban_valid("TR33 0006 1005 1978 6457 8413 26")
    assert not iban_valid("TR34 0006 1005 1978 6457 8413 26")


def test_tc_only_with_valid_checksum_or_context(settings):
    assert (T.TC, "10000000078") in found(settings, "Kimlik: 10000000078")
    assert found(settings, "Sipariş 12345678901") == []
    assert (T.TC, "12345678901") in found(settings, "TC No: 12345678901")


@pytest.mark.parametrize(
    "phone",
    ["0532 123 45 67", "05321234567", "+90 532 123 45 67", "(0264) 295 10 10", "0 532 123 45 67", "532-123-45-67"],
)
def test_phone_formats(settings, phone):
    assert (T.TELEFON, phone) in found(settings, f"Telefon: {phone} arayın")


def test_order_number_is_not_phone(settings):
    assert found(settings, "Sipariş no 2642951010") == []


def test_email_and_iban(settings):
    res = found(settings, "a.yilmaz@ornek.com.tr adresine, IBAN TR33 0006 1005 1978 6457 8413 26")
    assert (T.EPOSTA, "a.yilmaz@ornek.com.tr") in res
    assert (T.IBAN, "TR33 0006 1005 1978 6457 8413 26") in res


def test_names_with_titles_and_suffixes(settings):
    res = found(settings, "Sayın Dr. Elif Demir ile Ayşe Kaya'ya ve AHMET YILMAZ'a yazıldı. Can Bey geldi.")
    assert (T.KISI, "Elif Demir") in res
    assert (T.KISI, "Ayşe Kaya") in res
    assert (T.KISI, "AHMET YILMAZ") in res
    assert (T.KISI, "Can") in res


def test_ambiguous_name_alone_is_low_confidence(settings):
    out = []
    for d in build_detectors(settings):
        out += d.detect(Segment("Umut ediyoruz ki sorun çözülür.", "x"))
    assert all(f.confidence < 0.5 for f in out if f.etype == T.KISI)


def test_unknown_first_name_with_known_surname(settings):
    assert (T.KISI, "Oya Tekin") in found(settings, "Müdürü Oya Tekin katıldı.")


def test_units_and_orgs(settings):
    res = found(settings, "Bugün Satın Alma Birimi ile Bilgi İşlem Daire Başkanlığı, Yılmaz Makine San. ve Tic. A.Ş. ile görüştü.")
    assert (T.BIRIM, "Satın Alma Birimi") in res
    assert (T.BIRIM, "Bilgi İşlem Daire Başkanlığı") in res
    assert (T.KURUM, "Yılmaz Makine San. ve Tic. A.Ş.") in res


def test_person_not_swallowed_by_unit(settings):
    res = found(settings, "Ahmet Yılmaz Kalite Müdürlüğü'ne bağlı.")
    assert (T.BIRIM, "Kalite Müdürlüğü") in res
    assert any(t == T.KISI and "Ahmet" in v for t, v in res)


def test_address(settings):
    res = found(settings, "Adres: Esentepe Mah. Üniversite Cad. No:12 Serdivan/Sakarya. Teşekkürler.")
    assert (T.ADRES, "Esentepe Mah. Üniversite Cad. No:12 Serdivan/Sakarya") in res
    res = found(settings, "Atatürk Bulvarı No: 45/3 Kat: 2 Çankaya Ankara 06420 adresine gönderildi.")
    assert (T.ADRES, "Atatürk Bulvarı No: 45/3 Kat: 2 Çankaya Ankara 06420") in res


def test_column_hint_takes_whole_cell(settings):
    assert found(settings, "Zeki Müren", hint=T.KISI, whole=True) == [(T.KISI, "Zeki Müren")]


def test_disabled_type_is_ignored(settings):
    settings.enabled[T.BIRIM.value] = False
    assert found(settings, "Satın Alma Birimi") == []


def test_custom_list(settings):
    settings.custom_terms = ["Proje Atlas", "Hat-3 | ÖZEL", "Delta Kimya | KURUM"]
    res = found(settings, "Proje Atlas kapsamında Hat-3 ve delta kimya ile")
    assert (T.OZEL, "Proje Atlas") in res
    assert (T.OZEL, "Hat-3") in res
    assert (T.KURUM, "delta kimya") in res


def test_card_and_tax_numbers(settings):
    from anonimlestirici.core.detectors.patterns import luhn_valid

    assert luhn_valid("4111 1111 1111 1111")
    res = found(settings, "Kart 4111 1111 1111 1111 ile ödendi. Vergi no: 1234567890, IP 192.168.1.20")
    assert (T.FINANS, "4111 1111 1111 1111") in res
    assert (T.VERGI, "1234567890") in res
    assert (T.IP, "192.168.1.20") in res
    assert found(settings, "Sipariş 1234567890 kodlu") == []

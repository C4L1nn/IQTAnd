"""Content region helpers for iqtMusic.

This module keeps UI language separate from music/content region.
The app can be Turkish while the homepage uses Germany/US/Brazil charts.
"""
from __future__ import annotations

import json
import locale
import os
import platform
import re
import time
from typing import Any

DEFAULT_CONTENT_REGION = "TR"
_REGION_CACHE_FILE = "content_region_cache.json"
_REGION_CACHE_TTL = 7 * 24 * 60 * 60

COUNTRY_NAMES = {
    "TR": {"tr": "Türkiye", "en": "Turkey"},
    "US": {"tr": "Amerika", "en": "United States"},
    "GB": {"tr": "Birleşik Krallık", "en": "United Kingdom"},
    "DE": {"tr": "Almanya", "en": "Germany"},
    "FR": {"tr": "Fransa", "en": "France"},
    "IT": {"tr": "İtalya", "en": "Italy"},
    "ES": {"tr": "İspanya", "en": "Spain"},
    "NL": {"tr": "Hollanda", "en": "Netherlands"},
    "BE": {"tr": "Belçika", "en": "Belgium"},
    "AT": {"tr": "Avusturya", "en": "Austria"},
    "CH": {"tr": "İsviçre", "en": "Switzerland"},
    "SE": {"tr": "İsveç", "en": "Sweden"},
    "NO": {"tr": "Norveç", "en": "Norway"},
    "DK": {"tr": "Danimarka", "en": "Denmark"},
    "FI": {"tr": "Finlandiya", "en": "Finland"},
    "PL": {"tr": "Polonya", "en": "Poland"},
    "RO": {"tr": "Romanya", "en": "Romania"},
    "GR": {"tr": "Yunanistan", "en": "Greece"},
    "RU": {"tr": "Rusya", "en": "Russia"},
    "UA": {"tr": "Ukrayna", "en": "Ukraine"},
    "AZ": {"tr": "Azerbaycan", "en": "Azerbaijan"},
    "BR": {"tr": "Brezilya", "en": "Brazil"},
    "MX": {"tr": "Meksika", "en": "Mexico"},
    "AR": {"tr": "Arjantin", "en": "Argentina"},
    "CL": {"tr": "Şili", "en": "Chile"},
    "CO": {"tr": "Kolombiya", "en": "Colombia"},
    "CA": {"tr": "Kanada", "en": "Canada"},
    "AU": {"tr": "Avustralya", "en": "Australia"},
    "NZ": {"tr": "Yeni Zelanda", "en": "New Zealand"},
    "JP": {"tr": "Japonya", "en": "Japan"},
    "KR": {"tr": "Güney Kore", "en": "South Korea"},
    "IN": {"tr": "Hindistan", "en": "India"},
    "ID": {"tr": "Endonezya", "en": "Indonesia"},
    "MY": {"tr": "Malezya", "en": "Malaysia"},
    "TH": {"tr": "Tayland", "en": "Thailand"},
    "PH": {"tr": "Filipinler", "en": "Philippines"},
    "SA": {"tr": "Suudi Arabistan", "en": "Saudi Arabia"},
    "AE": {"tr": "Birleşik Arap Emirlikleri", "en": "United Arab Emirates"},
    "IL": {"tr": "İsrail", "en": "Israel"},
    "EG": {"tr": "Mısır", "en": "Egypt"},
    "MA": {"tr": "Fas", "en": "Morocco"},
    "ZA": {"tr": "Güney Afrika", "en": "South Africa"},
}

COUNTRY_NAMES.update({
    "AD": {"tr": "Andorra", "en": "Andorra"},
    "AF": {"tr": "Afganistan", "en": "Afghanistan"},
    "AG": {"tr": "Antigua ve Barbuda", "en": "Antigua and Barbuda"},
    "AI": {"tr": "Anguilla", "en": "Anguilla"},
    "AL": {"tr": "Arnavutluk", "en": "Albania"},
    "AM": {"tr": "Ermenistan", "en": "Armenia"},
    "AO": {"tr": "Angola", "en": "Angola"},
    "AQ": {"tr": "Antarktika", "en": "Antarctica"},
    "AS": {"tr": "Amerikan Samoasi", "en": "American Samoa"},
    "AW": {"tr": "Aruba", "en": "Aruba"},
    "AX": {"tr": "Aland Adalari", "en": "Aland Islands"},
    "BA": {"tr": "Bosna Hersek", "en": "Bosnia and Herzegovina"},
    "BB": {"tr": "Barbados", "en": "Barbados"},
    "BD": {"tr": "Banglades", "en": "Bangladesh"},
    "BF": {"tr": "Burkina Faso", "en": "Burkina Faso"},
    "BG": {"tr": "Bulgaristan", "en": "Bulgaria"},
    "BH": {"tr": "Bahreyn", "en": "Bahrain"},
    "BI": {"tr": "Burundi", "en": "Burundi"},
    "BJ": {"tr": "Benin", "en": "Benin"},
    "BL": {"tr": "Saint Barthelemy", "en": "Saint Barthelemy"},
    "BM": {"tr": "Bermuda", "en": "Bermuda"},
    "BN": {"tr": "Brunei", "en": "Brunei"},
    "BO": {"tr": "Bolivya", "en": "Bolivia"},
    "BQ": {"tr": "Karayip Hollandasi", "en": "Caribbean Netherlands"},
    "BS": {"tr": "Bahamalar", "en": "Bahamas"},
    "BT": {"tr": "Butan", "en": "Bhutan"},
    "BV": {"tr": "Bouvet Adasi", "en": "Bouvet Island"},
    "BW": {"tr": "Botsvana", "en": "Botswana"},
    "BY": {"tr": "Belarus", "en": "Belarus"},
    "BZ": {"tr": "Belize", "en": "Belize"},
    "CC": {"tr": "Cocos Adalari", "en": "Cocos Islands"},
    "CD": {"tr": "Kongo Demokratik Cumhuriyeti", "en": "Democratic Republic of the Congo"},
    "CF": {"tr": "Orta Afrika Cumhuriyeti", "en": "Central African Republic"},
    "CG": {"tr": "Kongo Cumhuriyeti", "en": "Republic of the Congo"},
    "CI": {"tr": "Fildisi Sahili", "en": "Cote d'Ivoire"},
    "CK": {"tr": "Cook Adalari", "en": "Cook Islands"},
    "CM": {"tr": "Kamerun", "en": "Cameroon"},
    "CN": {"tr": "Cin", "en": "China"},
    "CR": {"tr": "Kosta Rika", "en": "Costa Rica"},
    "CU": {"tr": "Kuba", "en": "Cuba"},
    "CV": {"tr": "Cape Verde", "en": "Cape Verde"},
    "CW": {"tr": "Curacao", "en": "Curacao"},
    "CX": {"tr": "Christmas Adasi", "en": "Christmas Island"},
    "CY": {"tr": "Kibris", "en": "Cyprus"},
    "CZ": {"tr": "Cekya", "en": "Czechia"},
    "DJ": {"tr": "Cibuti", "en": "Djibouti"},
    "DM": {"tr": "Dominika", "en": "Dominica"},
    "DO": {"tr": "Dominik Cumhuriyeti", "en": "Dominican Republic"},
    "DZ": {"tr": "Cezayir", "en": "Algeria"},
    "EC": {"tr": "Ekvador", "en": "Ecuador"},
    "EE": {"tr": "Estonya", "en": "Estonia"},
    "EH": {"tr": "Bati Sahra", "en": "Western Sahara"},
    "ER": {"tr": "Eritre", "en": "Eritrea"},
    "ET": {"tr": "Etiyopya", "en": "Ethiopia"},
    "FJ": {"tr": "Fiji", "en": "Fiji"},
    "FK": {"tr": "Falkland Adalari", "en": "Falkland Islands"},
    "FM": {"tr": "Mikronezya", "en": "Micronesia"},
    "FO": {"tr": "Faroe Adalari", "en": "Faroe Islands"},
    "GA": {"tr": "Gabon", "en": "Gabon"},
    "GD": {"tr": "Grenada", "en": "Grenada"},
    "GE": {"tr": "Gurcistan", "en": "Georgia"},
    "GF": {"tr": "Fransiz Guyanasi", "en": "French Guiana"},
    "GG": {"tr": "Guernsey", "en": "Guernsey"},
    "GH": {"tr": "Gana", "en": "Ghana"},
    "GI": {"tr": "Cebelitarik", "en": "Gibraltar"},
    "GL": {"tr": "Gronland", "en": "Greenland"},
    "GM": {"tr": "Gambiya", "en": "Gambia"},
    "GN": {"tr": "Gine", "en": "Guinea"},
    "GP": {"tr": "Guadeloupe", "en": "Guadeloupe"},
    "GQ": {"tr": "Ekvator Ginesi", "en": "Equatorial Guinea"},
    "GS": {"tr": "Guney Georgia ve Guney Sandwich Adalari", "en": "South Georgia and the South Sandwich Islands"},
    "GT": {"tr": "Guatemala", "en": "Guatemala"},
    "GU": {"tr": "Guam", "en": "Guam"},
    "GW": {"tr": "Gine-Bissau", "en": "Guinea-Bissau"},
    "GY": {"tr": "Guyana", "en": "Guyana"},
    "HK": {"tr": "Hong Kong", "en": "Hong Kong"},
    "HM": {"tr": "Heard Adasi ve McDonald Adalari", "en": "Heard Island and McDonald Islands"},
    "HN": {"tr": "Honduras", "en": "Honduras"},
    "HR": {"tr": "Hirvatistan", "en": "Croatia"},
    "HT": {"tr": "Haiti", "en": "Haiti"},
    "HU": {"tr": "Macaristan", "en": "Hungary"},
    "IE": {"tr": "Irlanda", "en": "Ireland"},
    "IM": {"tr": "Man Adasi", "en": "Isle of Man"},
    "IO": {"tr": "Britanya Hint Okyanusu Topraklari", "en": "British Indian Ocean Territory"},
    "IQ": {"tr": "Irak", "en": "Iraq"},
    "IR": {"tr": "Iran", "en": "Iran"},
    "IS": {"tr": "Izlanda", "en": "Iceland"},
    "JE": {"tr": "Jersey", "en": "Jersey"},
    "JM": {"tr": "Jamaika", "en": "Jamaica"},
    "JO": {"tr": "Urdun", "en": "Jordan"},
    "KE": {"tr": "Kenya", "en": "Kenya"},
    "KG": {"tr": "Kirgizistan", "en": "Kyrgyzstan"},
    "KH": {"tr": "Kambocya", "en": "Cambodia"},
    "KI": {"tr": "Kiribati", "en": "Kiribati"},
    "KM": {"tr": "Komorlar", "en": "Comoros"},
    "KN": {"tr": "Saint Kitts ve Nevis", "en": "Saint Kitts and Nevis"},
    "KP": {"tr": "Kuzey Kore", "en": "North Korea"},
    "KW": {"tr": "Kuveyt", "en": "Kuwait"},
    "KY": {"tr": "Cayman Adalari", "en": "Cayman Islands"},
    "KZ": {"tr": "Kazakistan", "en": "Kazakhstan"},
    "LA": {"tr": "Laos", "en": "Laos"},
    "LB": {"tr": "Lubnan", "en": "Lebanon"},
    "LC": {"tr": "Saint Lucia", "en": "Saint Lucia"},
    "LI": {"tr": "Lihtenstayn", "en": "Liechtenstein"},
    "LK": {"tr": "Sri Lanka", "en": "Sri Lanka"},
    "LR": {"tr": "Liberya", "en": "Liberia"},
    "LS": {"tr": "Lesotho", "en": "Lesotho"},
    "LT": {"tr": "Litvanya", "en": "Lithuania"},
    "LU": {"tr": "Luksemburg", "en": "Luxembourg"},
    "LV": {"tr": "Letonya", "en": "Latvia"},
    "LY": {"tr": "Libya", "en": "Libya"},
    "MC": {"tr": "Monako", "en": "Monaco"},
    "MD": {"tr": "Moldova", "en": "Moldova"},
    "ME": {"tr": "Karadag", "en": "Montenegro"},
    "MF": {"tr": "Saint Martin", "en": "Saint Martin"},
    "MG": {"tr": "Madagaskar", "en": "Madagascar"},
    "MH": {"tr": "Marshall Adalari", "en": "Marshall Islands"},
    "MK": {"tr": "Kuzey Makedonya", "en": "North Macedonia"},
    "ML": {"tr": "Mali", "en": "Mali"},
    "MM": {"tr": "Myanmar", "en": "Myanmar"},
    "MN": {"tr": "Mogolistan", "en": "Mongolia"},
    "MO": {"tr": "Makao", "en": "Macao"},
    "MP": {"tr": "Kuzey Mariana Adalari", "en": "Northern Mariana Islands"},
    "MQ": {"tr": "Martinik", "en": "Martinique"},
    "MR": {"tr": "Moritanya", "en": "Mauritania"},
    "MS": {"tr": "Montserrat", "en": "Montserrat"},
    "MT": {"tr": "Malta", "en": "Malta"},
    "MU": {"tr": "Mauritius", "en": "Mauritius"},
    "MV": {"tr": "Maldivler", "en": "Maldives"},
    "MW": {"tr": "Malavi", "en": "Malawi"},
    "MZ": {"tr": "Mozambik", "en": "Mozambique"},
    "NA": {"tr": "Namibya", "en": "Namibia"},
    "NC": {"tr": "Yeni Kaledonya", "en": "New Caledonia"},
    "NE": {"tr": "Nijer", "en": "Niger"},
    "NF": {"tr": "Norfolk Adasi", "en": "Norfolk Island"},
    "NG": {"tr": "Nijerya", "en": "Nigeria"},
    "NI": {"tr": "Nikaragua", "en": "Nicaragua"},
    "NP": {"tr": "Nepal", "en": "Nepal"},
    "NR": {"tr": "Nauru", "en": "Nauru"},
    "NU": {"tr": "Niue", "en": "Niue"},
    "OM": {"tr": "Umman", "en": "Oman"},
    "PA": {"tr": "Panama", "en": "Panama"},
    "PE": {"tr": "Peru", "en": "Peru"},
    "PF": {"tr": "Fransiz Polinezyasi", "en": "French Polynesia"},
    "PG": {"tr": "Papua Yeni Gine", "en": "Papua New Guinea"},
    "PK": {"tr": "Pakistan", "en": "Pakistan"},
    "PM": {"tr": "Saint Pierre ve Miquelon", "en": "Saint Pierre and Miquelon"},
    "PN": {"tr": "Pitcairn Adalari", "en": "Pitcairn Islands"},
    "PR": {"tr": "Porto Riko", "en": "Puerto Rico"},
    "PS": {"tr": "Filistin", "en": "Palestine"},
    "PT": {"tr": "Portekiz", "en": "Portugal"},
    "PW": {"tr": "Palau", "en": "Palau"},
    "PY": {"tr": "Paraguay", "en": "Paraguay"},
    "QA": {"tr": "Katar", "en": "Qatar"},
    "RE": {"tr": "Reunion", "en": "Reunion"},
    "RS": {"tr": "Sirbistan", "en": "Serbia"},
    "RW": {"tr": "Ruanda", "en": "Rwanda"},
    "SB": {"tr": "Solomon Adalari", "en": "Solomon Islands"},
    "SC": {"tr": "Seyseller", "en": "Seychelles"},
    "SD": {"tr": "Sudan", "en": "Sudan"},
    "SG": {"tr": "Singapur", "en": "Singapore"},
    "SH": {"tr": "Saint Helena", "en": "Saint Helena"},
    "SI": {"tr": "Slovenya", "en": "Slovenia"},
    "SJ": {"tr": "Svalbard ve Jan Mayen", "en": "Svalbard and Jan Mayen"},
    "SK": {"tr": "Slovakya", "en": "Slovakia"},
    "SL": {"tr": "Sierra Leone", "en": "Sierra Leone"},
    "SM": {"tr": "San Marino", "en": "San Marino"},
    "SN": {"tr": "Senegal", "en": "Senegal"},
    "SO": {"tr": "Somali", "en": "Somalia"},
    "SR": {"tr": "Surinam", "en": "Suriname"},
    "SS": {"tr": "Guney Sudan", "en": "South Sudan"},
    "ST": {"tr": "Sao Tome ve Principe", "en": "Sao Tome and Principe"},
    "SV": {"tr": "El Salvador", "en": "El Salvador"},
    "SX": {"tr": "Sint Maarten", "en": "Sint Maarten"},
    "SY": {"tr": "Suriye", "en": "Syria"},
    "SZ": {"tr": "Esvatini", "en": "Eswatini"},
    "TC": {"tr": "Turks ve Caicos Adalari", "en": "Turks and Caicos Islands"},
    "TD": {"tr": "Cad", "en": "Chad"},
    "TF": {"tr": "Fransiz Guney Topraklari", "en": "French Southern Territories"},
    "TG": {"tr": "Togo", "en": "Togo"},
    "TJ": {"tr": "Tacikistan", "en": "Tajikistan"},
    "TK": {"tr": "Tokelau", "en": "Tokelau"},
    "TL": {"tr": "Dogu Timor", "en": "Timor-Leste"},
    "TM": {"tr": "Turkmenistan", "en": "Turkmenistan"},
    "TN": {"tr": "Tunus", "en": "Tunisia"},
    "TO": {"tr": "Tonga", "en": "Tonga"},
    "TT": {"tr": "Trinidad ve Tobago", "en": "Trinidad and Tobago"},
    "TV": {"tr": "Tuvalu", "en": "Tuvalu"},
    "TW": {"tr": "Tayvan", "en": "Taiwan"},
    "TZ": {"tr": "Tanzanya", "en": "Tanzania"},
    "UG": {"tr": "Uganda", "en": "Uganda"},
    "UM": {"tr": "ABD Kucuk Dis Adalari", "en": "United States Minor Outlying Islands"},
    "UY": {"tr": "Uruguay", "en": "Uruguay"},
    "UZ": {"tr": "Ozbekistan", "en": "Uzbekistan"},
    "VA": {"tr": "Vatikan", "en": "Vatican City"},
    "VC": {"tr": "Saint Vincent ve Grenadinler", "en": "Saint Vincent and the Grenadines"},
    "VE": {"tr": "Venezuela", "en": "Venezuela"},
    "VG": {"tr": "Britanya Virgin Adalari", "en": "British Virgin Islands"},
    "VI": {"tr": "ABD Virgin Adalari", "en": "U.S. Virgin Islands"},
    "VN": {"tr": "Vietnam", "en": "Vietnam"},
    "VU": {"tr": "Vanuatu", "en": "Vanuatu"},
    "WF": {"tr": "Wallis ve Futuna", "en": "Wallis and Futuna"},
    "WS": {"tr": "Samoa", "en": "Samoa"},
    "YE": {"tr": "Yemen", "en": "Yemen"},
    "YT": {"tr": "Mayotte", "en": "Mayotte"},
    "ZM": {"tr": "Zambiya", "en": "Zambia"},
    "ZW": {"tr": "Zimbabve", "en": "Zimbabwe"},
})

REGION_LANG = {
    "TR": "tr", "US": "en", "GB": "en", "CA": "en", "AU": "en", "NZ": "en",
    "DE": "de", "AT": "de", "CH": "de", "FR": "fr", "BE": "fr", "IT": "it",
    "ES": "es", "MX": "es", "AR": "es", "CL": "es", "CO": "es", "BR": "pt",
    "NL": "nl", "SE": "sv", "NO": "no", "DK": "da", "FI": "fi", "PL": "pl",
    "RO": "ro", "GR": "el", "RU": "ru", "UA": "uk", "AZ": "az", "JP": "ja",
    "KR": "ko", "IN": "hi", "ID": "id", "MY": "ms", "TH": "th", "PH": "en",
    "SA": "ar", "AE": "ar", "IL": "he", "EG": "ar", "MA": "ar", "ZA": "en",
}

# Some region names work better in YouTube search when written in English.
SEARCH_COUNTRY_NAMES = {
    code: names.get("en", code) for code, names in COUNTRY_NAMES.items()
}

# YouTube Music playlist search works much better when the genre words are
# written the way listeners in that country actually search them. These are
# not UI labels; they are search hints for finding real playlists.
_REGION_PLAYLIST_TERMS = {
    "BR": {
        "new": ["lançamentos Brasil", "músicas novas Brasil", "novidades Brasil"],
        "pop": ["pop Brasil", "pop brasileiro", "pop nacional"],
        "rap": ["rap nacional", "trap Brasil", "hip hop brasileiro"],
        "rock": ["rock brasileiro", "rock nacional", "rock alternativo Brasil"],
        "indie": ["indie brasileiro", "indie Brasil", "alternativo brasileiro"],
    },
    "DE": {
        "new": ["neue Musik Deutschland", "Neuheiten Deutschland"],
        "pop": ["Deutschpop", "deutsche Pop Hits", "Pop Deutschland"],
        "rap": ["Deutschrap", "deutscher Hip Hop", "Rap Deutschland"],
        "rock": ["deutscher Rock", "Rock Deutschland", "Alternative Deutschland"],
        "indie": ["deutsch indie", "indie Deutschland", "alternative Deutschland"],
    },
    "FR": {
        "new": ["nouveautés France", "nouveautés musique française"],
        "pop": ["pop française", "hits pop France", "variété française"],
        "rap": ["rap français", "hip hop français", "trap français"],
        "rock": ["rock français", "rock France", "alternative France"],
        "indie": ["indie français", "indé France", "alternative française"],
    },
    "ES": {
        "new": ["novedades España", "música nueva España"],
        "pop": ["pop español", "pop España", "hits España"],
        "rap": ["rap español", "hip hop español", "trap España"],
        "rock": ["rock español", "rock España", "alternativo España"],
        "indie": ["indie español", "indie España", "alternativo España"],
    },
    "MX": {
        "new": ["novedades México", "música nueva México"],
        "pop": ["pop mexicano", "pop México", "hits México"],
        "rap": ["rap mexicano", "hip hop mexicano", "trap México"],
        "rock": ["rock mexicano", "rock México", "alternativo México"],
        "indie": ["indie mexicano", "indie México", "alternativo México"],
    },
    "US": {
        "new": ["new music USA", "new releases USA"],
        "pop": ["US pop hits", "American pop hits", "pop USA"],
        "rap": ["US rap hits", "American hip hop", "trap USA"],
        "rock": ["US rock hits", "American rock", "alternative rock USA"],
        "indie": ["US indie", "American indie", "indie pop USA"],
    },
    "GB": {
        "new": ["new music UK", "new releases UK"],
        "pop": ["UK pop hits", "British pop", "pop UK"],
        "rap": ["UK rap", "UK hip hop", "UK drill"],
        "rock": ["UK rock", "British rock", "alternative UK"],
        "indie": ["UK indie", "British indie", "indie UK"],
    },
    "JP": {
        "new": ["J-Pop new releases", "Japan new music", "新曲 J-POP"],
        "pop": ["J-Pop hits", "Japanese pop", "JPOP"],
        "rap": ["Japanese rap", "J hip hop", "日本語ラップ"],
        "rock": ["J-Rock", "Japanese rock", "Japan rock"],
        "indie": ["Japanese indie", "Japan indie", "indie J-Pop"],
    },
    "KR": {
        "new": ["K-pop new releases", "Korea new music"],
        "pop": ["K-pop hits", "Korean pop", "Kpop"],
        "rap": ["Korean rap", "K hip hop", "Korean hip hop"],
        "rock": ["Korean rock", "K-rock", "Korea rock"],
        "indie": ["Korean indie", "K-indie", "Korea indie"],
    },
}


def region_playlist_terms(code: str, profile: str) -> list[str]:
    code = normalize_region(code)
    profile = str(profile or "").strip().lower()
    if code in _REGION_PLAYLIST_TERMS and profile in _REGION_PLAYLIST_TERMS[code]:
        return list(_REGION_PLAYLIST_TERMS[code][profile])
    country = region_search_name(code)
    generic = {
        "new": [f"new music {country}", f"new releases {country}", f"latest hits {country}"],
        "pop": [f"{country} pop hits", f"pop music {country}", f"popular pop {country}"],
        "rap": [f"{country} rap", f"{country} hip hop", f"{country} trap"],
        "rock": [f"{country} rock", f"{country} alternative rock", f"rock music {country}"],
        "indie": [f"{country} indie", f"{country} alternative", f"indie pop {country}"],
        "slow": [f"{country} slow songs", f"{country} acoustic", f"romantic songs {country}"],
        "acoustic": [f"{country} acoustic", f"unplugged {country}", f"acoustic pop {country}"],
        "energetic": [f"{country} upbeat songs", f"party hits {country}", f"energetic pop {country}"],
    }
    return list(generic.get(profile, [f"{country} {profile}"]))


def normalize_region(value: Any, default: str = DEFAULT_CONTENT_REGION) -> str:
    code = str(value or "").strip().upper()
    code = re.sub(r"[^A-Z]", "", code)[:2]
    return code if len(code) == 2 else default


def region_language(code: str) -> str:
    return REGION_LANG.get(normalize_region(code), "en")


def region_display_name(code: str, ui_language: str = "tr") -> str:
    code = normalize_region(code)
    lang = "tr" if str(ui_language or "tr").lower().startswith("tr") else "en"
    return COUNTRY_NAMES.get(code, {}).get(lang) or COUNTRY_NAMES.get(code, {}).get("en") or code


def region_search_name(code: str) -> str:
    code = normalize_region(code)
    return SEARCH_COUNTRY_NAMES.get(code, code)


def _extract_region_from_locale(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    # tr_TR, en-US, Turkish_Turkey.1254 gibi değerleri yakala.
    match = re.search(r"(?:[_-])([A-Z]{2})(?:\.|@|$)", text, re.I)
    if match:
        return normalize_region(match.group(1), "")
    return ""


def detect_system_country_code() -> str:
    """Detect the OS/user region without sending a network request."""
    # Windows 10+: returns ISO-3166 country/region such as TR, US, DE.
    if platform.system().lower().startswith("win"):
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(16)
            func = ctypes.windll.kernel32.GetUserDefaultGeoName
            func.argtypes = [ctypes.c_wchar_p, ctypes.c_int]
            func.restype = ctypes.c_int
            if func(buf, len(buf)) > 0:
                return normalize_region(buf.value, "")
        except Exception:
            pass

    candidates = []
    try:
        candidates.extend(locale.getlocale())
    except Exception:
        pass
    try:
        candidates.append(locale.getdefaultlocale()[0])  # noqa: W1505 - old Python compatible fallback
    except Exception:
        pass
    for env_key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        candidates.append(os.environ.get(env_key, ""))
    for item in candidates:
        code = _extract_region_from_locale(item)
        if code:
            return code
    return ""


def _cache_path(base_dir: str) -> str:
    return os.path.join(str(base_dir or "."), _REGION_CACHE_FILE)


def _load_cached_region(base_dir: str) -> str:
    try:
        with open(_cache_path(base_dir), "r", encoding="utf-8") as f:
            data = json.load(f)
        if (time.time() - float(data.get("ts", 0) or 0)) <= _REGION_CACHE_TTL:
            return normalize_region(data.get("country"), "")
    except Exception:
        pass
    return ""


def _save_cached_region(base_dir: str, country: str, source: str) -> None:
    try:
        os.makedirs(str(base_dir or "."), exist_ok=True)
        with open(_cache_path(base_dir), "w", encoding="utf-8") as f:
            json.dump({"country": normalize_region(country), "source": source, "ts": time.time()}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def detect_ip_country_code(session=None, timeout: float = 2.0) -> str:
    """Detect region by public IP. Only stores/returns country code, not the IP."""
    urls = (
        "https://ipapi.co/json/",
        "https://ipwho.is/",
    )
    getter = session.get if session is not None else None
    if getter is None:
        try:
            import requests
            getter = requests.get
        except Exception:
            return ""
    for url in urls:
        try:
            resp = getter(url, timeout=timeout)
            if getattr(resp, "status_code", 0) >= 400:
                continue
            data = resp.json() if hasattr(resp, "json") else {}
            code = data.get("country_code") or data.get("countryCode") or data.get("country")
            code = normalize_region(code, "")
            if code:
                return code
        except Exception:
            continue
    return ""


def detect_content_region(settings: dict | None, session=None, base_dir: str = "") -> str:
    """Resolve the region used for charts/searches.

    Settings:
      content_region_mode = auto | ip | system | manual
      content_region = ISO-2 country code used when manual mode is selected
    """
    settings = settings or {}
    mode = str(settings.get("content_region_mode", "auto") or "auto").strip().lower()
    manual = normalize_region(settings.get("content_region"), "")
    if mode == "manual" and manual:
        return manual

    if mode in {"auto", "ip"}:
        cached = _load_cached_region(base_dir)
        if cached:
            return cached
        ip_code = detect_ip_country_code(session=session, timeout=2.0)
        if ip_code:
            _save_cached_region(base_dir, ip_code, "ip")
            return ip_code
        if mode == "ip":
            return manual or DEFAULT_CONTENT_REGION

    if mode in {"auto", "system"}:
        system_code = detect_system_country_code()
        if system_code:
            return system_code

    return manual or DEFAULT_CONTENT_REGION


def build_region_feed_spec(alias: str, region: str) -> dict | None:
    """Return a dynamic feed spec for local homepage aliases.

    Existing Turkey specs remain untouched when region is TR. For other countries,
    old feed:tr.* aliases are reinterpreted as local-country equivalents so the UI
    can keep using the same page code.
    """
    alias = str(alias or "").strip()
    region = normalize_region(region)
    if not alias or region == "TR":
        return None

    country = region_search_name(region)
    hl = region_language(region)
    base = {
        "gl": region,
        "hl": hl,
        "prefer_turkish": False,
        "recent_years": 2,
        "max_age_years": 4,
        "title_reject_tokens": ["new music friday", "top 20", "top 50", "spotify", "playlist", "new year"],
        "avoid_tokens": ["remix", "sped up", "slowed", "karaoke", "cover", "lyrics"],
    }

    if alias == "feed:charts.tr":
        return {
            **base,
            "kind": "charts",
            "country": region,
            "max_sources": 4,
            "fallback_queries": [
                f"{country} chart songs official audio {{year}}",
                f"{country} top songs official audio {{year}}",
                f"{country} viral songs official audio {{year}}",
                f"popular songs in {country} official audio {{year}}",
            ],
            "playlist_queries": [
                f"{country} top songs playlist",
                f"{country} charts YouTube Music",
                f"{country} viral hits playlist",
                f"top music {country} playlist",
            ],
            "playlist_prefer_tokens": ["chart", "top", "hits", "viral", country.lower(), region.lower()],
            "playlist_reject_tokens": ["spotify", "apple music", "karaoke", "cover", "sleep", "workout"],
            "playlist_search_limit": 8,
            "playlist_max_sources": 3,
        }

    profile_map = {
        "feed:new.music": ("new", ["new", "fresh", "release", "novidades", "neu", "nouveautés", "novedades"]),
        "feed:tr.pop": ("pop", ["pop", "hit", "viral"]),
        "feed:tr.rap": ("rap", ["rap", "hip hop", "hiphop", "trap", "drill"]),
        "feed:tr.rock": ("rock", ["rock", "alternative", "alternativo"]),
        "feed:tr.indie": ("indie", ["indie", "alternative", "alternativo", "indé"]),
        "feed:tr.slow": ("slow", ["slow", "romantic", "acoustic"]),
        "feed:tr.acoustic": ("acoustic", ["acoustic", "unplugged"]),
        "feed:tr.energetic": ("energetic", ["upbeat", "party", "pop"]),
        "feed:tr.morning.pop": ("pop", ["pop", "happy", "upbeat"]),
        "feed:tr.morning.rap": ("rap", ["rap", "hip hop", "upbeat"]),
        "feed:tr.evening.pop": ("pop", ["chill", "soft", "pop"]),
        "feed:tr.evening.rap": ("rap", ["rap", "hip hop", "chill"]),
    }
    item = profile_map.get(alias)
    if not item:
        return None

    profile, prefer_tokens = item
    playlist_terms = region_playlist_terms(region, profile)
    # First try real YouTube Music playlists; only then fall back to raw song
    # search. This makes homepage cards feel like actual country/genre lists
    # instead of random search results with a fake card title.
    playlist_queries = []
    for term in playlist_terms:
        playlist_queries.extend([
            f"{term} playlist",
            f"{term} YouTube Music",
            f"{term} mix",
        ])
    song_queries = []
    for term in playlist_terms:
        song_queries.extend([
            f"{term} official audio {{year}}",
            f"{term} songs {{year}}",
        ])
    spec = {
        **base,
        "kind": "playlist_search",
        "profile": profile,
        "playlist_queries": playlist_queries,
        "queries": song_queries,
        "search_limit": 18,
        "playlist_search_limit": 8,
        "max_sources": 3,
        "playlist_max_sources": 3,
        "prefer_tokens": prefer_tokens,
        "playlist_prefer_tokens": prefer_tokens + [country.lower(), region.lower()],
        "playlist_reject_tokens": [
            "spotify", "apple music", "deezer", "soundcloud", "karaoke",
            "workout", "sleep", "kids", "christmas", "xmas", "new year",
            "top 1000", "all time", "best of all time",
        ],
    }
    if alias in {"feed:tr.rap", "feed:tr.morning.rap", "feed:tr.evening.rap"}:
        spec["strict_profile"] = False
        spec["playlist_prefer_tokens"] = prefer_tokens + ["hip-hop", "hiphop", country.lower(), region.lower()]
        spec["hard_reject_tokens"] = ["acoustic", "ballad", "karaoke", "piano version"]
    return spec

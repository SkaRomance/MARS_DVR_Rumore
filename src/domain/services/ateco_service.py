from sqlalchemy import select
from src.infrastructure.database.models.ateco import AtecoCatalog
from src.bootstrap.database import get_db

ATECO_MACRO_CATEGORIES = {
    "A": {
        "name_it": "Agricoltura, silvicoltura e pesca",
        "name_en": "Agriculture, forestry and fishing",
        "description_it": "Settore agricolo con esposizione a rumore da trattori, mietitrebbie, pompe idrauliche e attrezzature per lavorazione terreno. L'esposizione è prevalentemente stagionale con LEX,8h tipico tra 75-90 dB(A).",
        "description_en": "Agricultural sector with exposure to noise from tractors, combine harvesters, hydraulic pumps and ground processing equipment. Exposure is predominantly seasonal with typical LEX,8h between 75-90 dB(A).",
        "typical_sources": [
            "trattore",
            "mietitrebbia",
            "trebbiatrice",
            "pompa irrigazione",
            "motosega",
        ],
        "typical_lex_range": [75, 90],
    },
    "B": {
        "name_it": "Estrazione di minerali da cave e miniere",
        "name_en": "Mining and quarrying",
        "description_it": "Attività estrattiva con esposizione prolungata a rumore da perforatrici, frantoi, nastri trasportatori e esplosivi. L'esposizione è continua con LEX,8h tipico tra 85-100 dB(A), superamento frequente dei valori limite.",
        "description_en": "Extractive activity with prolonged exposure to noise from drills, crushers, conveyor belts and explosives. Continuous exposure with typical LEX,8h between 85-100 dB(A), frequent exceeding of limit values.",
        "typical_sources": [
            "perforatrice",
            "frantoio",
            "nastro trasportatore",
            "escavatore",
            "betoniera",
        ],
        "typical_lex_range": [85, 100],
    },
    "C": {
        "name_it": "Attività manifatturiere",
        "name_en": "Manufacturing",
        "description_it": "Il settore manifatturiero presenta la più ampia casistica di rischio rumore: lavorazione metalli, legno, plastica, tessile. Fonti principali: presse, torni, fresatrici, saldatrici, compressori. LEX,8h tipico tra 80-95 dB(A) con picchi oltre 140 dB(C) per operazioni di stampaggio e fucinatura.",
        "description_en": "Manufacturing sector presents the widest range of noise risk: metalworking, wood, plastic, textile. Main sources: presses, lathes, milling machines, welders, compressors. Typical LEX,8h between 80-95 dB(A) with peaks above 140 dB(C) for stamping and forging operations.",
        "typical_sources": [
            "pressa",
            "torno",
            "fresatrice",
            "saldatrice",
            "compressore",
            "trapano",
            "molatrice",
        ],
        "typical_lex_range": [80, 95],
    },
    "D": {
        "name_it": "Fornitura di energia elettrica, gas, vapore e aria condizionata",
        "name_en": "Electricity, gas, steam and air conditioning supply",
        "description_it": "Centrali elettriche, sottostazioni e impianti di generazione con esposizione a turbine, generatori, trasformatori e caldaie. LEX,8h tipico tra 80-95 dB(A) con componenti a basse frequenze.",
        "description_en": "Power plants, substations and generation facilities with exposure to turbines, generators, transformers and boilers. Typical LEX,8h between 80-95 dB(A) with low-frequency components.",
        "typical_sources": [
            "turbina",
            "generatore",
            "trasformatore",
            "caldaia",
            "compressore",
        ],
        "typical_lex_range": [80, 95],
    },
    "E": {
        "name_it": "Fognatura, trattamento rifiuti, bonifica",
        "name_en": "Water supply, sewerage, waste management",
        "description_it": "Impianti di trattamento acque e rifiuti con esposizione a pompe, depuratori, impianti di incenerimento e mezzi pesanti. LEX,8h tipico tra 75-90 dB(A).",
        "description_en": "Water and waste treatment plants with exposure to pumps, purifiers, incinerators and heavy vehicles. Typical LEX,8h between 75-90 dB(A).",
        "typical_sources": [
            "pompa centrifuga",
            "depuratore",
            "inceneritore",
            "camion raccolta",
            "nastro trasportatore",
        ],
        "typical_lex_range": [75, 90],
    },
    "F": {
        "name_it": "Costruzioni",
        "name_en": "Construction",
        "description_it": "Cantieri edili con esposizione intensa a escavatori, betoniere, martelli pneumatici, seghe circolari e macchine movimento terra. L'esposizione variabile giornaliera con LEX,8h tipico tra 85-100 dB(A) e picchi da martellazione oltre 140 dB(C). Rischio critico per operaio specializzato.",
        "description_en": "Construction sites with intense exposure to excavators, concrete mixers, pneumatic hammers, circular saws and earthmoving equipment. Variable daily exposure with typical LEX,8h between 85-100 dB(A) and hammering peaks above 140 dB(C). Critical risk for specialized workers.",
        "typical_sources": [
            "martello pneumatico",
            "betoniera",
            "escavatore",
            "segapavè",
            "segaccio",
            "trapano",
        ],
        "typical_lex_range": [85, 100],
    },
    "G": {
        "name_it": "Commercio all'ingrosso e al dettaglio",
        "name_en": "Wholesale and retail trade",
        "description_it": "Attività commerciale con rischio rumore generalmente basso, tranne specifici contesti: grandi magazzini con impianti di ventilazione, mercati all'aperto con altoparlanti, reparti macelleria con seghe ossa. LEX,8h tipico tra 65-80 dB(A).",
        "description_en": "Commercial activity with generally low noise risk, except specific contexts: large stores with ventilation systems, outdoor markets with speakers, butcher departments with bone saws. Typical LEX,8h between 65-80 dB(A).",
        "typical_sources": [
            "impianto ventilazione",
            "altoparlante",
            "segatura ossa",
            "muletto",
        ],
        "typical_lex_range": [65, 80],
    },
    "H": {
        "name_it": "Trasporto e magazzinaggio",
        "name_en": "Transportation and storage",
        "description_it": "Trasporto su gomma, rotaia, nave e aereo. Muletti, camion, carrelli elevatori e sistemi di smistamento. Guidatori di automezzi pesanti con LEX,8h tra 75-85 dB(A). Addetti aeroportuali con esposizione a 85-95 dB(A).",
        "description_en": "Road, rail, sea and air transport. Forklifts, trucks, elevator cars and sorting systems. Heavy vehicle drivers with LEX,8h between 75-85 dB(A). Airport workers with exposure at 85-95 dB(A).",
        "typical_sources": [
            "camion",
            "muletto",
            "carrello elevatore",
            "nastro bagagli",
            "motore aereo",
        ],
        "typical_lex_range": [75, 95],
    },
    "I": {
        "name_it": "Attività dei servizi di alloggio e ristorazione",
        "name_en": "Accommodation and food service",
        "description_it": "Ristoranti, bar e alberghi con esposizione a cucine professionali, frigoriferi, macchine per caffè, impianti di ventilazione e musica di fondo. LEX,8h tipico tra 70-85 dB(A) per addetti cucina.",
        "description_en": "Restaurants, bars and hotels with exposure to professional kitchens, refrigerators, coffee machines, ventilation systems and background music. Typical LEX,8h between 70-85 dB(A) for kitchen staff.",
        "typical_sources": [
            "cappa cucina",
            "frigorifero commerciale",
            "macchina caffè",
            "friggitrice",
            "ventilazione",
        ],
        "typical_lex_range": [70, 85],
    },
    "J": {
        "name_it": "Servizi di informazione e comunicazione",
        "name_en": "Information and communication",
        "description_it": "Call center, studi di registrazione e trasmissioni radio/TV. Rischio relativamente basso tranne in studi con monitoraggio ad alto volume. LEX,8h tipico tra 60-80 dB(A).",
        "description_en": "Call centers, recording studios and radio/TV broadcasting. Relatively low risk except in studios with high-volume monitoring. Typical LEX,8h between 60-80 dB(A).",
        "typical_sources": ["cuffie call center", "monitor studio", "impianto audio"],
        "typical_lex_range": [60, 80],
    },
    "K": {
        "name_it": "Attività finanziarie e assicurative",
        "name_en": "Financial and insurance activities",
        "description_it": "Uffici con rischio rumore trascurabile. LEX,8h tipico sotto 70 dB(A).",
        "description_en": "Offices with negligible noise risk. Typical LEX,8h below 70 dB(A).",
        "typical_sources": [],
        "typical_lex_range": [55, 70],
    },
    "L": {
        "name_it": "Attività immobiliari",
        "name_en": "Real estate activities",
        "description_it": "Attività prevalentemente d'ufficio. Rischio rumore trascurabile.",
        "description_en": "Predominantly office activities. Negligible noise risk.",
        "typical_sources": [],
        "typical_lex_range": [55, 70],
    },
    "M": {
        "name_it": "Attività professionali, scientifiche e tecniche",
        "name_en": "Professional, scientific and technical activities",
        "description_it": "Consulenti HSE, laboratori di analisi e studi tecnici. I consulenti in sicurezza possono essere esposti durante sopralluoghi in ambienti produttivi. LEX,8h tipico tra 65-85 dB(A) per chi effettua misurazioni sul campo.",
        "description_en": "HSE consultants, analysis laboratories and technical studios. Safety consultants may be exposed during inspections in production environments. Typical LEX,8h between 65-85 dB(A) for field measurement personnel.",
        "typical_sources": [
            "fonometro (sopralluogo)",
            "laboratorio",
            "impianto pilota",
        ],
        "typical_lex_range": [65, 85],
    },
    "N": {
        "name_it": "Noleggio, agenzie di viaggio, servizi di supporto",
        "name_en": "Rental, travel agencies, support services",
        "description_it": "Servizi di supporto alle imprese. Rischio basso tranne per addetti a noleggio attrezzature industriali. LEX,8h tipico tra 60-75 dB(A).",
        "description_en": "Business support services. Low risk except for industrial equipment rental staff. Typical LEX,8h between 60-75 dB(A).",
        "typical_sources": [],
        "typical_lex_range": [60, 75],
    },
    "O": {
        "name_it": "Pubblica amministrazione e difesa",
        "name_en": "Public administration and defence",
        "description_it": "Attività amministrativa d'ufficio prevalentemente. Forze dell'ordine con esposizione ad armi da fuoco (picco oltre 160 dB(C)). Vigili del fuoco con sirene e attrezzature. LEX,8h variabile: 60-80 dB(A) ufficio, 85-100 dB(A) operativo.",
        "description_en": "Predominantly office administrative activity. Law enforcement with firearm exposure (peak above 160 dB(C)). Firefighters with sirens and equipment. Variable LEX,8h: 60-80 dB(A) office, 85-100 dB(A) operational.",
        "typical_sources": [
            "arma da fuoco",
            "sirena",
            "impianto ventilazione",
            "eldispositivo radio",
        ],
        "typical_lex_range": [60, 100],
    },
    "P": {
        "name_it": "Istruzione",
        "name_en": "Education",
        "description_it": "Scuole e università. Rischio contenuto tranne in laboratori tecnici, aule musica e officine scolastiche. LEX,8h tipico tra 65-80 dB(A).",
        "description_en": "Schools and universities. Contained risk except in technical laboratories, music rooms and school workshops. Typical LEX,8h between 65-80 dB(A).",
        "typical_sources": [
            "laboratorio",
            "aula musica",
            "officina scolastica",
            "mensa",
        ],
        "typical_lex_range": [65, 80],
    },
    "Q": {
        "name_it": "Sanità e assistenza sociale",
        "name_en": "Human health and social work",
        "description_it": "Ospedali e cliniche con esposizione a macchinari (risonanza magnetica, ventilatori, compressori), sale operatorie e unità di terapia intensiva. LEX,8h tipico tra 65-85 dB(A). Rischio significativo per tecnici di radiologia e manutenzione.",
        "description_en": "Hospitals and clinics with exposure to equipment (MRI, fans, compressors), operating rooms and intensive care units. Typical LEX,8h between 65-85 dB(A). Significant risk for radiology and maintenance technicians.",
        "typical_sources": [
            "risonanza magnetica",
            "compressore",
            "ventilatore",
            "allarme",
            "aspiratore",
        ],
        "typical_lex_range": [65, 85],
    },
    "R": {
        "name_it": "Attività artistiche, sportive, divertimento",
        "name_en": "Arts, entertainment and recreation",
        "description_it": "Discoteche, concerti, eventi sportivi, teatri e studi di registrazione musicale. Livelli sonori molto elevati per DJ, musicisti e personale di sala. LEX,8h tipico tra 85-100+ dB(A) con frequenti superamenti dei valori limite.",
        "description_en": "Discotheques, concerts, sporting events, theaters and music recording studios. Very high sound levels for DJs, musicians and venue staff. Typical LEX,8h between 85-100+ dB(A) with frequent exceeding of limit values.",
        "typical_sources": [
            "impianto audio",
            "strumento musicale",
            "folla",
            "cassa",
            "amplificatore",
        ],
        "typical_lex_range": [85, 105],
    },
    "S": {
        "name_it": "Altre attività di servizi",
        "name_en": "Other service activities",
        "description_it": "Servizi vari inclusi lavanderie industriali, parruccherie, centri estetici e servizi di riparazione. Lavanderie con LEX,8h 80-90 dB(A). Parruccherie con asciugacapelli a 75-85 dB(A).",
        "description_en": "Various services including industrial laundries, hair salons, beauty centers and repair services. Laundries with LEX,8h 80-90 dB(A). Hair salons with hair dryers at 75-85 dB(A).",
        "typical_sources": [
            "asciugacapelli",
            "lavatrice industriale",
            "asciugatrice",
            "ferro da stiro industriale",
        ],
        "typical_lex_range": [70, 90],
    },
    "T": {
        "name_it": "Attività di famiglie e convivenze come datori di lavoro",
        "name_en": "Activities of households as employers",
        "description_it": "Attività domestiche. Rischio rumore trascurabile.",
        "description_en": "Domestic activities. Negligible noise risk.",
        "typical_sources": [],
        "typical_lex_range": [50, 65],
    },
    "U": {
        "name_it": "Organizzazioni ed organismi extraterritoriali",
        "name_en": "Extraterritorial organizations",
        "description_it": "Ambasciate e organismi internazionali. Rischio rumore trascurabile.",
        "description_en": "Embassies and international organizations. Negligible noise risk.",
        "typical_sources": [],
        "typical_lex_range": [50, 65],
    },
}

DIVISION_TO_MACRO_CATEGORY = {
    "01": "A",
    "02": "A",
    "03": "A",
    "05": "B",
    "06": "B",
    "07": "B",
    "08": "B",
    "09": "B",
    "10": "C",
    "11": "C",
    "12": "C",
    "13": "C",
    "14": "C",
    "15": "C",
    "16": "C",
    "17": "C",
    "18": "C",
    "19": "C",
    "20": "C",
    "21": "C",
    "22": "C",
    "23": "C",
    "24": "C",
    "25": "C",
    "26": "C",
    "27": "C",
    "28": "C",
    "29": "C",
    "30": "C",
    "31": "C",
    "32": "C",
    "33": "C",
    "35": "D",
    "36": "E",
    "37": "E",
    "38": "E",
    "39": "E",
    "41": "F",
    "42": "F",
    "43": "F",
    "45": "G",
    "46": "G",
    "47": "G",
    "49": "H",
    "50": "H",
    "51": "H",
    "52": "H",
    "53": "H",
    "55": "I",
    "56": "I",
    "58": "J",
    "59": "J",
    "60": "J",
    "61": "J",
    "62": "J",
    "63": "J",
    "64": "K",
    "65": "K",
    "66": "K",
    "68": "L",
    "69": "M",
    "70": "M",
    "71": "M",
    "72": "M",
    "73": "M",
    "74": "M",
    "75": "M",
    "77": "N",
    "78": "N",
    "79": "N",
    "80": "N",
    "81": "N",
    "82": "N",
    "84": "O",
    "85": "P",
    "86": "Q",
    "87": "Q",
    "88": "Q",
    "90": "R",
    "91": "R",
    "92": "R",
    "93": "R",
    "94": "S",
    "95": "S",
    "96": "S",
    "97": "T",
    "98": "T",
    "99": "U",
}


def _format_macro(code: str, data: dict) -> dict:
    return {
        "code": code,
        "name_it": data["name_it"],
        "name_en": data["name_en"],
        "description_it": data["description_it"],
        "description_en": data["description_en"],
        "typical_sources": data["typical_sources"],
        "typical_lex_range": data["typical_lex_range"],
    }


def get_macro_category(category_code: str) -> dict | None:
    code = category_code.upper().strip()
    data = ATECO_MACRO_CATEGORIES.get(code)
    if data is None:
        return None
    return _format_macro(code, data)


def get_all_macro_categories() -> list[dict]:
    return [_format_macro(code, data) for code, data in ATECO_MACRO_CATEGORIES.items()]


def _division_from_ateco_code(ateco_code: str) -> str | None:
    parts = ateco_code.strip().split(".")
    if not parts:
        return None
    division = parts[0].zfill(2)[:2]
    if division.isdigit():
        return division
    return None


async def get_macro_category_for_ateco(ateco_code: str) -> dict | None:
    async with get_db() as session:
        result = await session.execute(
            select(AtecoCatalog).where(AtecoCatalog.code == ateco_code.strip())
        )
        ateco_entry = result.scalar_one_or_none()
        if ateco_entry and ateco_entry.category:
            macro = get_macro_category(ateco_entry.category)
            if macro:
                return macro

    division = _division_from_ateco_code(ateco_code)
    if division and division in DIVISION_TO_MACRO_CATEGORY:
        return get_macro_category(DIVISION_TO_MACRO_CATEGORY[division])

    return None

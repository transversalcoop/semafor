import re
import email
import datetime
import requests

from bs4 import BeautifulSoup


def extract_tenders(files):
    tenders = []
    for f in files:
        msg = email.message_from_bytes(f.read())
        msg = msg.get_payload()[0]  # first attachment, the body
        msg = msg.get_payload(decode=True)
        if msg is not None:
            msg = msg.decode("utf-8")  # decode the body
            tenders += extract_tenders_aux(msg)

    tenders = filter_expired(tenders)
    tenders = filter_small(tenders, amount=1000)
    tenders = add_location_data(tenders)
    return serialize(tenders)


def extract_tenders_aux(msg):
    tenders = []
    names_map = {
        "Título del Contrato": "name",
        "CPV": "cpv",
        "Importe": "amount",
        "Órgano de Contratación": "contractor",
        "Fecha final de presentación de ofertas": "offers_until",
        "Número de Expediente": "id",
        "Ver detalle": "href",
    }
    for lines in split_tenders(msg):
        tender = {}
        for line in lines:
            try:
                index = line.index(":")
                key = line[:index]
                value = line[index + 1 :].strip()
                if key in names_map:
                    if names_map[key] == "amount":
                        value = float(
                            value.replace(".", "")
                            .replace("Euros", "")
                            .replace(",", ".")
                        )
                    elif names_map[key] == "offers_until":
                        value = datetime.datetime.strptime(value, "%d/%m/%Y %H:%M")
                    tender[names_map[key]] = value
            except Exception:
                pass

        tenders.append(tender)

    return tenders


def split_tenders(msg):
    tender, tenders, inside_tender = [], [], False
    for line in msg.split("\n"):
        line = line.strip()
        if inside_tender:
            if line.startswith("Título del Contrato"):
                tenders.append(tender)
                tender = [line]
            else:
                tender.append(line)
        else:
            if line.startswith("Título del Contrato"):
                inside_tender = True
                tender.append(line)

    tenders.append(tender)
    return tenders


def filter_expired(tenders):
    return [
        t
        for t in tenders
        if "offers_until" in t and t["offers_until"] > datetime.datetime.now()
    ]


def filter_small(tenders, amount=1000):
    return [t for t in tenders if t["amount"] > amount]


def serialize(tenders):
    for t in tenders:
        t["offers_until"] = t["offers_until"].isoformat()
    return tenders


def add_location_data(tenders):
    for t in tenders:
        add_tender_location_data(t)
    return tenders


def add_tender_location_data(tender):
    response = requests.get(tender["href"])
    soup = BeautifulSoup(response.text, "lxml")
    for o in soup.find_all(
        "span", class_="outputText", id=re.compile("LugarEjecucion")
    ):
        tender["location"] = str(o.string)
    return tender

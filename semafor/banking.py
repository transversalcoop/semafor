import datetime as dt
import pandas as pd

from semafor.models import Transaction


class RuralVia:
    def __init__(self, filename):
        self.df = pd.read_excel(filename, skiprows=3)

    def get_field(self, row, labels):
        for label in labels:
            try:
                return row[label]
            except Exception:
                pass

        raise Exception(f"Could not find labels {labels}; got {row.index.to_list()}")

    def get_transactions(self):
        for _, row in self.df.iterrows():
            date_str = self.get_field(row, ["Fecha valor", "Data valor"])
            try:
                date = date_str.date()
            except Exception:
                date = dt.datetime.strptime(date_str, "%d/%m/%Y").date()

            yield Transaction(
                id=self.get_field(row, ["Núm. Apunt", "Nro. Apunte"]),
                date=date,
                concept=self.get_field(row, ["Concepto", "Tipo Movimiento"]),
                amount=self.get_field(row, ["Importe", "Import"]),
                balance=self.get_field(row, ["Saldo"]),
            )

import datetime
import pandas as pd

from semafor.models import Transaction


class RuralVia:
    def __init__(self, filename):
        self.df = pd.read_excel(filename, skiprows=2)

    def get_transactions(self):
        for _, row in self.df.iterrows():
            yield Transaction(
                id=row["Nro. Apunte"],
                date=datetime.datetime.strptime(row["Fecha valor"], "%d/%m/%Y").date(),
                concept=row["Concepto"],
                amount=row["Importe"],
                balance=row["Saldo"],
            )

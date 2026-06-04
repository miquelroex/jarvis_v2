from langchain.tools import tool
from datetime import datetime

@tool
def get_date() -> str:
    """Returns today's date in Spanish. Use when the user asks what day it is."""
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
             "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    now = datetime.now()
    return f"{now.day} de {meses[now.month - 1]} de {now.year}"
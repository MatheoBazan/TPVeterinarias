import time


def consultar_stock(vacuna: str) -> int:
    """Biblioteca del laboratorio: sincrónica, tarda un segundo."""
    time.sleep(1)
    return 10 + len(vacuna)

class DomainError(Exception):
    """
    Business-rule violation raised by the repository layer.
    Converted to an HTTP response by the handler registered in app/main.py,
    so that app/repo/ does not depend on FastAPI.
    """

    def __init__(self, detail: str, status_code: int = 400):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class NotFoundError(DomainError):
    def __init__(self, detail: str):
        super().__init__(detail, status_code=404)

import logging
import re


class RedigirDados(logging.Filter):
    def filter(self, record):
        """Oculta tokens de acompanhamento e parâmetros de consulta na mensagem do log, preservando sua emissão."""
        message = record.getMessage()
        message = re.sub(r'(/acompanhar/)[^/\s?]+', r'\1[privado]', message)
        message = re.sub(r'\?[^\s"\x27]+', '?[parametros-omitidos]', message)
        record.msg, record.args = message, ()
        return True

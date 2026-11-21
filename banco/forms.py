"""Compatibility import for the shared results form.

The Banco app no longer owns a Resultado model. The current model and form live in
resultados; this module keeps the legacy import path working without stale fields.
"""
from resultados.forms import ResultadoForm

__all__ = ["ResultadoForm"]

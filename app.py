"""Vstupní bod aplikace.

Lokálně:  python app.py  (spustí vývojový server na http://127.0.0.1:5000)
Na PythonAnywhere importuje WSGI soubor proměnnou `app` (viz DEPLOY.md).
"""
from pubquiz import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

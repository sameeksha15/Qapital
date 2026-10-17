"""Writes the API's OpenAPI description to web/src/api/openapi.json, from which the website generates its types
(cd web && npm run gen:api). Run after any change to qapital/api/schemas.py or the endpoints:
  python -m scripts.export_openapi"""

import json

from qapital.api.main import Config, create_app
from scripts.paths import ROOT

OUT = ROOT / "web" / "src" / "api" / "openapi.json"


def openapi_text() -> str:
    schema = create_app(Config(database_url="sqlite://")).openapi()
    return json.dumps(schema, indent=2, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    OUT.write_text(openapi_text(), encoding="utf-8")
    print(f"wrote {OUT}")

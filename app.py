"""WSGI entry point; application behavior lives in the MVC package."""

import os

from comedor import create_app


app = create_app()


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5000)

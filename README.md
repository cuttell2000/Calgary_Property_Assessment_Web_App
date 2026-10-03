---
title: Calgary Property Assessment Map
sdk: docker
app_port: 7860
---

# Calgary Property Assessment Map

This Flask app maps Calgary community boundaries and property assessment data
from the City of Calgary Open Data API.

## Run locally

Install the deployment dependencies and start the Flask development server:

```bash
pip install -r requirements-hf.txt
python app.py
```

Open `http://localhost:5000`.

## Deploy to Hugging Face Spaces

Create a Space named `Calgary_Property_Assessment_Map_App` with the Docker
SDK. Push the runtime files (`Dockerfile`, `README.md`, `app.py`,
`requirements-hf.txt`, and the `templates` directory) to the Space's Git
remote. Do not push the original repository's `venv` directory; it is tracked
in that repository but is not needed by the Space.

The Docker image installs the runtime dependencies and starts Gunicorn on
port 7860. The app fetches community boundaries at startup and requests
property data from the City of Calgary API when a community is selected, so
the Space needs outbound network access.

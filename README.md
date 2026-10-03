---
title: Calgary Property Assessment Map
emoji: 📊
colorFrom: indigo
colorTo: yellow
sdk: gradio
sdk_version: 6.29.1
python_version: "3.12"
app_file: gradio_app.py
pinned: false
---

# Calgary Property Assessment Map

This app maps Calgary community boundaries and property assessment data from
the City of Calgary Open Data API.

## Run locally

Install the app dependencies and start the Flask development server:

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:5000`.

## Deploy to Hugging Face Spaces

The Hugging Face Space uses Gradio on its free ZeroGPU hardware. Its
`gradio_app.py` interface reuses the existing Flask property-map route, while
`app.py` remains available for local Flask development. The Space installs
dependencies from `requirements.txt`.

The property-map callback uses ZeroGPU's required `@spaces.GPU` wrapper even
though its geospatial work is CPU-based; this can add queueing or execution
limits compared with CPU Basic hardware.

The app fetches community boundaries at startup and requests property data
from the City of Calgary API when a community is selected, so it needs
outbound network access.

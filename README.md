# InflatableModel — Custom Inflatable 3D Model Website

A full-stack web application for custom inflatable model ordering, targeting the
European and American markets. Users submit contact information, verify via email,
and then upload a reference image to generate a 3D model preview using
[Meshy AI](https://www.meshy.ai/) Image-to-3D API.

**Domain**: www.inflatablemodel.com.cn

---

## Features

- **Contact collection** — Name, Email, WhatsApp, Social Media, Company
- **Email verification** — 6-digit code challenge before unlocking the generator
- **Image upload** — Drag-and-drop + click-to-browse with instant preview
- **Meshy AI integration** — Image-to-3D task creation, polling, and result retrieval
- **3D preview** — GLB/GLTF model rendered in-browser with Three.js (orbit, zoom, rotate)
- **Responsive design** — Modern, clean UI for desktop and mobile
- **Demo mode** — Runs without an API key (shows placeholder behaviour)

---

## Project Structure

```
inflatable-website/
├── app.py                      # Flask backend (routes, Meshy integration)
├── config.py                   # API key, upload limits, session config
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── static/
│   ├── css/
│   │   └── style.css           # All styles
│   ├── js/
│   │   ├── main.js             # Contact form, verification, upload UI
│   │   └── three-preview.js    # Three.js GLB viewer (ES module)
│   └── images/                 # (reserved for static assets)
├── templates/
│   ├── index.html              # Landing page
│   ├── contact.html            # Contact form
│   ├── verify.html             # Verification code page
│   └── generate.html           # 3D generator + preview
└── uploads/                    # User-uploaded images (auto-created)
```

---

## Quick Start

### 1. Clone / copy the project

```bash
cd inflatable-website
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Meshy API Key

Open `config.py` and replace the placeholder:

```python
MESHY_API_KEY = os.getenv("MESHY_API_KEY", "YOUR_MESHY_API_KEY_HERE")
```

Or set the environment variable before running:

```bash
# Windows PowerShell
$env:MESHY_API_KEY = "msy_your_api_key_here"

# macOS / Linux
export MESHY_API_KEY="msy_your_api_key_here"
```

Get your API key at: https://www.meshy.ai/ → Dashboard → API Keys.

### 5. Run the app

```bash
python app.py
```

Open **http://localhost:5000** in your browser.

### 6. (Optional) Run with Gunicorn

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

---

## User Flow

```
Landing Page  →  Contact Form  →  Email Verification  →  3D Generator
                                                       (upload image,
                                                        describe model,
                                                        view 3D preview)
```

### Demo Verification Code
In demo mode the verification code is always: **123456**

---

## Meshy API Integration Details

The backend (`app.py`) handles the full Meshy pipeline:

| Step | Endpoint | Description |
|------|----------|-------------|
| 1 | `POST /openapi/v2/image-to-3d` | Create a new Image-to-3D task with the uploaded image URL |
| 2 | `GET /openapi/v2/image-to-3d/{task_id}` | Poll task status every 3 seconds |
| 3 | Extract `model_urls.glb` | When status is `SUCCEEDED`, send the GLB URL to the frontend |

The frontend Three.js module listens for a `model-ready` custom event and loads
the GLB file using `GLTFLoader`.

**Important**: Meshy requires a **publicly accessible image URL**. The current
implementation uses Flask's local URL. For production, upload images to a CDN
or cloud storage (S3, Cloudinary) before calling Meshy.

---

## Production Deployment Notes

1. **Set a strong `FLASK_SECRET_KEY`** (environment variable or in `config.py`)
2. **Replace in-memory stores** (verification codes, verified sessions) with Redis or a database
3. **Use HTTPS** — session cookies should be encrypted in transit
4. **Add rate limiting** on `/api/verify` and `/api/generate-3d`
5. **Upload images to cloud storage** before passing to Meshy
6. **Add real email sending** — replace the `print()` demo with SMTP / SendGrid / Mailgun

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.10+ / Flask |
| Frontend | HTML5 / CSS3 / Vanilla JS |
| 3D Rendering | Three.js (r160) |
| 3D Generation | Meshy AI Image-to-3D v2 API |
| Deployment | Gunicorn + WSGI server |

---

## License

Internal project — all rights reserved.
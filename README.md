# VHP4Safety UI Platform

Central HTML-based web application for the VHP4Safety project, providing access to tools, data, and resources for human safety assessment. The functionality of the platform is shown through three case studies.

## Table of Contents

- [VHP4Safety UI Platform](#vhp4safety-ui-platform)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Project Structure](#project-structure)
  - [Templates](#templates)
  - [CSS Styles](#css-styles)
    - [Bootstrap5 SASS maps](#bootstrap5-sass-maps)
  - [Key Files](#key-files)
  - [Tech Stack](#tech-stack)
  - [Installation \& Setup](#installation--setup)
  - [Deployment](#deployment)
    - [Deployment with Python](#deployment-with-python)
    - [Deployment with Docker](#deployment-with-docker)
    - [Published images](#published-images)
  - [Techniques](#techniques)
    - [Dynamic Page Filling: `tool.html` and `casestudy.html`](#dynamic-page-filling-toolhtml-and-casestudyhtml)
    - [Caching](#caching)
  - [Contributing](#contributing)

## Features

- GUI for the Virtual Human Platform
- Multiple tools for compound, gene, and risk assessment workflows
- Interactive molecular visualizations (JSmol)
- Modular templates and CSS for easy customization
- RESTful API endpoints (Flask)
- Data integration from Wikidata and custom sources
- Dockerized deployment for reproducibility

## Project Structure

```
├── app.py                # Main Flask app
├── patch.py              # Python patch for dependency fix
├── Dockerfile            # Docker build instructions
├── entrypoint.sh         # Entrypoint for Docker
├── requirements.txt      # Python dependencies
├── routes/               # Flask blueprints & API endpoints
├── static/
│   ├── css/              # CSS stylesheets
│   ├── js/               # JavaScript files
│   ├── images/           # Logos, icons, partners
│   └── data/             # Data files (CSV, JSON)
├── templates/            # Jinja2 HTML templates
└── README.md             # Project documentation
```

## Templates

- `base.html`: Main layout, includes navigation, header, footer, scripts, and styles
- `home.html`: Landing page with tab descriptions, about section, partner carousel and contact form
- `tools/tools.html`: Tool catalog with search and filter functionality
- `tools/tool.html`: Tool-specific template, dynamically filled from .json files based on URL
- `methods/methods.html`: Method catalog with search and filter functionality
- `methods/method.html`: Method-specific template, dynamically filled from .json files based on URL
- `tabs/casestudies.html`: Case study catalog where user can choose between the case studies
- `case_studies/casestudy.html`: Case study template, dynamically filled from .json files based on URL
- `tabs/data.html`: Data tab where metadata will be shared
- `legal/privacypolicy.html`, `legal/terms_of_service.html`: Pages to be filled with legal information

## CSS Styles

The new philosophy is to do as much as possible with bootstrap5 native css. Before defining new styles try to
accomplish the same (or similar) with bootstrap5. This will improve readability, maintainability, generate less 
unexpected behavior and makes extending the website much easier.

- `bootstrap-custom.css`: This repo uses a custom bootstrap5 cascading style sheet to reflect vhp4safety design-choices (colors) and defaults. The philosophy is to have a little as possible one-off css classes.
- `home.css`: Home page styles
- `tools.css`, `tool.css`: Tool and service card styles
- `casestudies.css`: Case study styles
- `hackathondemo.css`: Hackathon demo page styles _(not sure if still in use?)_

### Bootstrap5 SASS maps
Create a custom color compiled version of bootstrap5. 

```bash 
cd bootstrap-custom
npm install bootstrap sass --save-dev
```

Customize `custom.scss` for example with additional colors or padding specs etc. 
Then compile to css with
```bash
npx sass --load-path=node_modules custom.scss bootstrap-custom.css
```
Move bootstrap-custom.css to `static/css`. 

## Key Files

- `app.py`: Main Flask application, routing, and rendering
- `patch.py`: Patch script to fix dependency issues (e.g., pyshexc)
- `requirements.txt`: Python dependencies
- `Dockerfile` & `entrypoint.sh`: Containerization and startup

## Tech Stack

- **Backend:** Python 3.10+, Flask, requests, wikidataintegrator
- **Frontend:** HTML5, Jinja2, CSS3, JavaScript
- **Containerization:** Docker
- **Data:** CSV, JSON, integration with Wikidata

## Installation & Setup

1. **Clone the repository:**
   ```
   git clone https://github.com/VHP4Safety/ui-design.git
   cd ui-design
   ```
2. **Install Python dependencies:**
   ```
   pip install -r requirements.txt
   ```
3. **Apply the patch (required for pyshexc):**
   ```
   python patch.py
   ```

## Deployment

### Deployment with Python

Run the following command in your terminal:

```
python app.py
```

The application will be available at [http://localhost:5050/](http://localhost:5050/).

### Deployment with Docker

Build and run the Docker container:

```
docker build -t vhp4safety_ui .
docker run -d -p 5000:5050 vhp4safety_ui
```

The application will be available at [http://localhost:5000/](http://localhost:5000/).

### Published images

Every published GitHub Release builds the image and pushes it to Docker Hub as
[`vhp4safety/virtual-human-platform`](https://hub.docker.com/r/vhp4safety/virtual-human-platform),
tagged with the release version (and `latest` for non-prereleases). To run a released version
without building it yourself:

```
docker pull vhp4safety/virtual-human-platform:<version>
docker run -d -p 5000:5050 vhp4safety/virtual-human-platform:<version>
```

The workflow is `.github/workflows/docker-publish.yml`. It needs the repository secrets
`DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` (a Docker Hub access token with Read & Write scope).
It can also be run manually from the Actions tab to publish a specific tag.

---

## Techniques

### Dynamic Page Filling: `tool.html` and `casestudy.html`

This web app uses a dynamic content loading approach for both the tool and case study pages:

- **Routes in `app.py`:**

  - The route `/tools/<toolname>` renders `tools/tool.html` and passes the relevant JSON filename to the template.
  - The route `/casestudies/<case>` renders `case_studies/casestudy.html` and passes the case name to the template.

- **HTML Templates:**

  - `tools/tool.html` and `case_studies/casestudy.html` are designed to be generic containers. They do not contain hardcoded content for each tool or case study.
  - Instead, they include JavaScript that loads and displays content dynamically based on the URL.

- **JavaScript Files:**

  - A script (`tool.js` and `casestudies.js`) fetches the appropriate JSON file using the name from the URL. It then updates the HTML elements with the content from that file.

- **JSON Files:**
  - Each tool and case study has its own JSON file containing all the content and metadata needed for the page.
  - The JavaScript reads these files and populates the HTML elements, enabling a single template to serve multiple tools or case studies.

This technique allows for easy expansion and maintenance: new tools or case studies can be added simply by creating new JSON files, without modifying the HTML or Python backend.

### Caching

Index data fetched from the cloud repositories (tools, methods, data) is cached server-side for 5 days using Flask-Caching (`SimpleCache`, in-memory per worker process — also wiped on every restart). Most page loads therefore do not hit the source repositories.

You can force fresh data at any time by appending the `reset_cache` query parameter to any URL:

```
http://localhost:5050/tools?reset_cache
```

This clears the entire server-side cache; the current request and every subsequent one repopulate it with fresh data. No token or env var is required — the trigger is intentionally unprotected. Worst case, a stranger forces the cache to repopulate from the upstream indexes (low impact, slightly slower next requests).

## Contributing

1. **Fork** the repository on GitHub
2. **Clone** your fork locally
3. Create a new branch for your feature or fix
4. Make your changes and commit them
5. **Push** your branch to your fork
6. **Open a Pull Request** to the main repository

Please ensure your code is well-documented and tested. For major changes, discuss with the team first.

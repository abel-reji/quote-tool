# Quote Generator Tool

A lightweight internal quoting application built with **Python (Flask)**
that allows users to quickly generate professional PDF quotes,
track quote history, and manage quote defaults.

The tool provides a simple browser interface for creating quotes,
calculating pricing, exporting quote logs, and maintaining configurable
user and branch settings.

------------------------------------------------------------------------

## Features

### Quote Creation

-   Create quotes with multiple line items
-   Automatic pricing calculations
-   Margin or sell‑price based quoting
-   Automatic quote number generation

<img width="3039" height="1643" alt="image" src="https://github.com/user-attachments/assets/df43492f-433e-442b-ad01-972290274f80" />

### PDF Generation

-   Professionally formatted PDF output
-   Company branding
-   Configurable closing and signature block
-   Branch‑specific footer information

<img width="1118" height="1452" alt="image" src="https://github.com/user-attachments/assets/a20812ee-ab18-44a2-8e63-cd0029465a0e" />

### Quote Management

-   Dashboard showing all saved quotes
-   Search by:
    -   Quote number
    -   Customer
    -   Project description
-   Edit existing quotes
-   Track quote disposition:
    -   Won
    -   Lost
    -   Pending
-   Export quote log to CSV

<img width="3036" height="1639" alt="image" src="https://github.com/user-attachments/assets/82b93c7b-b4e3-49d1-b62c-7f9ec6bd0514" />

### Settings Management

Centralized settings page allows configuration of:

**User Information** - Sales engineer name - Phone - Email - Default
branch

**Branch Information** - Branch ID - Address - Phone and fax - Ability
to add new branches

**Quote Defaults** - Default cover page language - Quote validity text -
Default signature block

<img width="3036" height="1641" alt="image" src="https://github.com/user-attachments/assets/5f700feb-e048-4fa8-b0cf-bb1ec617d950" />

------------------------------------------------------------------------

## Project Structure

    quote-tool
    │
    ├── app.py
    ├── pdf_generator.py
    ├── requirements.txt
    │
    ├── data
    │   ├── quotes
    │   ├── settings.json
    │   └── quote_log.csv
    │
    ├── templates
    │   ├── landing.html
    │   ├── index.html
    │   └── settings.html
    │
    ├── static
    │   ├── styles.css
    │   ├── app.js
    │   └── img
    │       └── dxp_logo.png

------------------------------------------------------------------------

## Installation

Clone the repository:

``` bash
git clone https://github.com/abel-reji/quote-tool.git
cd quote-tool
```

Create a virtual environment:

``` bash
python -m venv venv
```

Activate the environment:

### Windows

``` bash
venv\Scripts\activate
```

Install dependencies:

``` bash
pip install -r requirements.txt
```

------------------------------------------------------------------------

## Running the Application

Start the Flask server:

``` bash
python app.py
```

Then open your browser:

    http://127.0.0.1:5000

------------------------------------------------------------------------

## Running on Vercel

This repo now includes a Vercel-compatible Flask entrypoint:

- `api/index.py` exposes the Flask app for Vercel's Python runtime
- `vercel.json` rewrites all routes to that entrypoint
- PDF and CSV downloads are generated in memory so they do not depend on a persistent local `output/` directory

Deploy with Vercel by importing the GitHub repository or using the Vercel CLI.

Important limitation:

- Vercel file storage is ephemeral. The current app still stores SQLite data, settings JSON, and uploaded attachments on the local filesystem, so quote data will not persist reliably across deployments or cold starts.
- For production use on Vercel, the next step is to move persistence to managed services such as Postgres for quote/settings data and blob/object storage for attachments.

------------------------------------------------------------------------

## How Quote Numbers Work

Quote numbers follow the format:

    (BranchID-YYMMDDXAR)

Example:

    325-2603077AR

Where:

-   **BranchID** = Sales branch
-   **YYMMDD** = Quote date
-   **X** = Daily quote sequence
-   **AR** = Sales engineer initials

------------------------------------------------------------------------

## Data Storage

For local desktop usage, the application stores all quote data locally:

    data/quotes.db
    data/settings.json
    data/uploads/

Uploads are stored per quote, and quote exports are generated on demand.

When running on Vercel, these local files are created in temporary runtime storage only.

------------------------------------------------------------------------

## Future Improvements

Planned enhancements include:

-   Compile application to standalone **EXE**
-   Dashboard metrics on landing page
-   Uploads container in quoting process
-   Quote template customization


------------------------------------------------------------------------

## Author

**Abel Reji**

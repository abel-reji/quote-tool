# Quote Generator Tool

For web deployment status, gateway limitations, and backup instructions, see
[WEB_DEPLOYMENT.md](WEB_DEPLOYMENT.md). Desktop mode remains the default.

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

The desktop executable stores its SQLite database, attachments, customers and
settings under `%LOCALAPPDATA%/Quote Tool/data`. Repository `data/` is used for
ordinary source launches unless storage is explicitly configured otherwise.

The single-user web installation uses private server storage shared by laptop
and phone browsers. It does not synchronize with the desktop executable. After
migration, use the website for ongoing quoting to avoid divergent copies.

See [WEB_DEPLOYMENT.md](WEB_DEPLOYMENT.md) for deployment, migration and manual
backup instructions. CSV export remains available from the application.

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

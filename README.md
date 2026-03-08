# Quote Generator Tool

A lightweight internal quoting application built with **Python (Flask)**
that allows sales engineers to quickly generate professional PDF quotes,
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

### PDF Generation

-   Professionally formatted PDF output
-   Company branding
-   Configurable closing and signature block
-   Branch‑specific footer information

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

### Settings Management

Centralized settings page allows configuration of:

**User Information** - Sales engineer name - Phone - Email - Default
branch

**Branch Information** - Branch ID - Address - Phone and fax - Ability
to add new branches

**Quote Defaults** - Default cover page language - Quote validity text -
Default signature block

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

The application stores all quote data locally:

    data/quotes/

Each quote is saved as a JSON file.

A summary log is maintained in:

    data/quote_log.csv

This allows easy export or integration with spreadsheets.

------------------------------------------------------------------------

## Future Improvements

Planned enhancements include:

-   Compile application to standalone **EXE**
-   Multi-user support
-   Cloud storage for quotes
-   Customer database integration
-   Quote template customization
-   Inventory or ERP integration
-   Email quote delivery

------------------------------------------------------------------------

## Author

**Abel Reji**

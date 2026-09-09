# Web Mode: Single-User Bluehost Deployment

The laptop executable is unchanged. Source launches remain local by default.
The verified laptop import is active at `https://quotes.abelreji.com`.
Credentials remain private on the server.

## Activation, September 6, 2026

The owner explicitly approved retaining the reference CGI gateway after its
production-use warning was explained, and requested manual backups only.
All 78 quotes, 137 line items, 3 attachment records, customers and settings are
active. Original quote numbers, dates, values and file hashes were preserved.
The laptop source was rechecked immediately before cutover and still matched;
it was not modified. The web database is now the working copy. Laptop EXE edits
will NOT synchronize to the website and must not be made in parallel.

The candidate was restored to a new private directory, upgraded additively, and
verified against the original manifest. All 78 PDFs generated and parsed both
before and after cutover (185 pages total). A representative quote, drawing
attachment and terms page were visually checked. One sample has an extra blank
quote-section page; attachment content is present. Existing attachment PDF
metadata/annotation warnings were logged, but originals remain byte-for-byte intact.
This was a generation/readability check, not visual review of all 185 pages.

The previous empty test database and launcher are preserved at
`/home3/finvestc/quote-tool-private/pre-activation-20260906`.
The active location is `/home3/finvestc/quote-tool-private/data`.
The actual web configuration was checked against that location and 78-quote count.
Maintenance is cleared; HTTPS login returned 200 and anonymous API access 401.
The user's authenticated dashboard after cutover remains a user acceptance check.

A post-activation backup verified on both server and laptop:
`snapshot-20260906-050026-14bcb324`, under the backup roots documented below.
Never roll back over newly entered web quotes without first preserving them.
`deploy/activate_import.py` is a one-time, path-specific cutover helper, not a
routine migration command; it refuses nonempty live data and existing rollback paths.

## Deployment history

The site began as synthetic-data staging at `https://quotes.abelreji.com/login`.
The source and its separate Python 3.12 environment are in
`/home3/finvestc/quote-tool-web`; the launcher uses `.venv/bin/python` there.
The private database was initialized empty using the user's existing configuration.
Only the quote subdomain's `.htaccess` and `staging.cgi` were published; the
SSL-validation directory, other websites, and laptop installation were left alone.

Pre-deployment configuration and public `.htaccess` backups are in
`/home3/finvestc/quote-tool-private/pre-staging-20260905-215408`.
These backups contain secrets and must remain outside every public document root.

Initial synthetic-data tests passed on Bluehost after deployment. Live checks
verified HTTPS, anonymous API/PDF/export rejection, dashboard login redirection,
static assets, rejection of invalid test credentials, and login layout at 390px.
Plain HTTP is rejected. A bare login POST was rejected with HTTP 406 by the hosting
stack; a normal browser form POST reached the app successfully.
The user subsequently confirmed successful login, quote/PDF workflows, and phone
access. Real-data activation followed the explicit gateway decision recorded above.

## Current readiness

The app now has opt-in single-user login, HTTPS-only signed sessions, CSRF
protection, persistent login throttling, private storage, and a WSGI entry point.
Database migrations are explicit, never run once per CGI request.

Bluehost has demonstrated Python 3.12 and CGI support, but its Passenger module
is not loaded. `deploy/staging.cgi` uses Python's reference CGI gateway. New
configurations DISABLE it by default. The existing owner opted in for single-user
real-data use; this does not make it a generally recommended production gateway.

Passing functional checks and owner acceptance do not supersede Python's warning
about the reference implementation. A maintained production gateway is preferred
when one becomes available on the hosting account.
Shared drafts and revision/conflict management remain future work.

## Readiness review, September 5, 2026

The baseline separate-process CGI test reproduced a numbering race: four of six
simultaneous new-quote saves failed. The deployed fix reserves the SQLite write
transaction before allocating a number. A cross-process storage lock additionally
coordinates request/file updates with snapshots. Requests wait up to 20 seconds
for storage and return 503 if busy. This intentionally serializes data requests
for a single-user workload; it is not a multi-user scaling strategy.

All 32 regression tests pass on Windows and Bluehost. The isolated Bluehost
`tests/cgi_load_check.py` run passed six saves with six unique numbers, three
duplicates with three unique numbers, and two simultaneous 10-page PDFs. Saves
took 0.83-1.00 seconds and PDFs 1.21-1.76 seconds. These are bounded synthetic
CGI subprocess tests on the hosting account, not an Apache HTTP load test or a
guarantee about larger files, sustained load, or provider timeouts. After deployment,
public HTTPS login returned 200 and anonymous quote API access returned 401.

Rollback code and a verified pre-change test-data snapshot are private at
`/home3/finvestc/quote-tool-private/pre-readiness-20260905`.
At the time of that review, the public app still had zero quotes. The subsequent
78-quote activation is recorded above.

CGI itself is not the categorical blocker. Apache terminates HTTPS and invokes
the adapter, rather than using Python's demonstration HTTP server. However,
Python's documentation warns against production use of the entire `wsgiref`
reference implementation, including the module used by this adapter. The warning
is not proof of a specific exploit in this installation, and these checks are not
a security certification. Retaining it for real data requires an explicit decision
to accept that support/security limitation; a maintained production gateway remains
the preferred long-term option. Last-write-wins edits and lack of server drafts
also remain workflow limitations.

## Manual off-server backups

From the repository, run `deploy/Backup-Bluehost.ps1`. It uses the authorized SSH
key with strict pinned-host verification, creates a new verified private server
snapshot, downloads it, and verifies records and attachment/settings hashes again.
It never overwrites an existing backup, exports login credentials, or automatically
deletes older copies. Backups can therefore grow; review storage periodically.

Server copies: `/home3/finvestc/quote-tool-private/backups`.
Laptop copies: `%LOCALAPPDATA%/Quote Tool Backups/bluehost`.
The end-to-end command passed with the activated 78-quote database and all five
referenced attachment/settings/customer files. The separate migration snapshot and restore
rehearsal remain available as described below. The backup command reads the active
`quote-tool-private/data` directory; update it if that storage location changes.
The user requested manual backups only: no recurring task or server cron was added.
Run a backup after important changes. Recover to a new private directory using
`quote_backup.py restore`, verify it, and use maintenance mode before any cutover.

## Duplication and packages

Saved quote editors also provide **Update Disposition** beside Pending/Won/Lost.
It sends a dedicated authenticated, CSRF-protected PATCH that changes only that
field. It does not validate/save other form edits, generate a PDF, or navigate
away. It uses the saved quote number even if the visible number has unsaved edits.
New quotes must be saved first. The ordinary Update Quote & Open PDF workflow
remains available for all other quote edits.

The feature update is deployed with 30 passing tests on both Windows and Bluehost.
The pre-feature server backup is
`/home3/finvestc/quote-tool-private/pre-features-20260905-222744`.
The CGI adapter checks a private `maintenance.flag` before importing the app so
schema/code upgrades can be performed without serving a partially updated version.

Duplicate Quote copies saved line items and independent attachment files, generates
a new normal app quote number, and resets date/status to today/Pending. It does not
include unsaved browser edits. P21 sources also produce a new normal app quote.

A package is one customer-facing line with private component names, quantities,
unit costs and unit selling prices. Component quantities are per package; the
outer quantity multiplies the complete package. Parent cost/price/margin are
calculated, not editable overrides. Nested packages are not supported. Internal
components and costs are excluded from the PDF template context. Existing quote
schemas are upgraded additively by `manage_web.py init`, preserving old records.

## Data snapshot

`quote_backup.py` offers `snapshot`, `verify`, and `restore` commands with positional
source/destination paths. Destinations must be new directories. Snapshot uses
SQLite's backup API and checks record counts/digests, integrity, foreign keys,
safe paths and referenced attachment hashes. It includes customers/settings, but
not obsolete legacy JSON quote files or unreferenced uploads. It never modifies
quote data (it creates/uses a sibling storage lock file). Close the desktop tool while snapshotting to keep attachments/settings
consistent with the database. Restore is to a new directory, never over live data.

The user's laptop snapshot and independent restore rehearsal verified 78 quotes,
137 line items and 3 attachment records, plus customers/settings. Snapshot:
`C:\Users\abel\AppData\Local\Quote Tool Backups\web-migration-20260905-232238`.
The source was rechecked after the laptop app closed and still matched the snapshot.
A private copy is now at
`/home3/finvestc/quote-tool-private/laptop-import-20260905/snapshot`.
An independent restored copy at `laptop-import-20260905/rehearsal/data` passed the
package-schema migration and the original record/file verification on Bluehost.
Both are beneath mode-700 private directories and remain unchanged recovery copies.
A fresh verified candidate was subsequently activated with the owner's approval,
as recorded above. Do not re-import the laptop copy over newer web quotes.

## Private layout

Keep code at `/home3/finvestc/quote-tool-web`, outside ALL website document roots.
Keep storage and credentials at `/home3/finvestc/quote-tool-private`, also outside
ALL document roots (including other addon websites).
The quote subdomain's public directory may remain
`/home3/finvestc/quote-tool-test/public`. Only the staging adapter and public
assets belong there, never the repo, database, configuration, backups or uploads.
The configuration loader rejects overlap with the declared public root; it cannot
discover the public roots of other hosting accounts or addon websites.

## Offline setup on the server

For a new installation, first test in isolation. Upload source to the
private code directory, excluding `data`, `output`, `.git`, build/dist and secrets.
Review runtime dependency versions before installing. `requirements-web.txt`
records the locally tested versions; the server probe used newer PDF packages.
Test the chosen versions in a separate web virtual environment before deployment.

Use the intended virtual environment's Python for all commands below. These
examples use `python` as shorthand for that full interpreter path.

```bash
python manage_web.py configure \
  --config /home3/finvestc/quote-tool-private/web-config.json \
  --storage-root /home3/finvestc/quote-tool-private \
  --public-root /home3/finvestc/quote-tool-test/public \
  --host quotes.abelreji.com --username abel
python manage_web.py init \
  --config /home3/finvestc/quote-tool-private/web-config.json
```

The password is prompted invisibly and stored only as a salted hash. The signing
secret is generated locally. Do not post this file in chat or commit it.
New private directories are created with mode 700 and the config with mode 600
on Unix. Verify existing directory permissions separately; never use chmod 777.
Ten login attempts per 15 minutes are allowed across all processes. A successful
login clears the counter. Lockout recovery is to wait 15 minutes. Sessions expire
after eight hours; changing the password hash or signing secret invalidates them.

## Optional synthetic-data CGI evaluation

1. Confirm valid HTTPS for `quotes.abelreji.com` before proceeding.
2. Explicitly set `allow_reference_cgi` to `true` in the PRIVATE config.
3. Check the interpreter and private code/config paths in `deploy/staging.cgi`.
4. Put that file in the public directory as `staging.cgi` with Unix LF endings
   and mode 755. The public folder must not be writable by other users.
5. Back up any existing public `.htaccess` privately. Remove only our old probes
   and merge `deploy/staging.htaccess` into that subdomain's file. Do not change
   the account-wide `.htaccess` or any other domain.
6. Visit HTTPS `/login`; use fake quotes only. No dev server or ProxyFix is needed.
   Apache must supply the correct HTTPS CGI environment. The app does not trust
   client-supplied X-Forwarded-* headers.
7. Verify login/logout, rejection of anonymous API/PDF/export access, creating
   and reopening an app quote and a P21 quote, editing numbers/dates, PDF uploads,
   PDF merge order, settings, CSV export, and two simultaneous browser tabs.
8. Record response times for saves and realistic PDFs. CGI starts Python afresh
   per request; import overhead and hosting limits must be measured.

To stop staging, remove the adapter from the public root and restore ONLY that
subdomain's prior `.htaccess`. Set `allow_reference_cgi` back to false. The laptop
app is independent and requires no rollback.

## Known workflow limits and migration precautions

- Web mode deliberately does not save quote drafts in browser localStorage.
  Unsaved edits are lost on navigation; shared server drafts are future work.
- Saved quotes are shared through one private SQLite database. Simultaneous
  edits are currently last-write-wins; don't edit one quote in two tabs/devices.
- Quote numbers must begin with a letter/number and may contain letters,
  numbers, periods, underscores and hyphens, not slashes or directory traversal.
  Audit legacy numbers before importing a copied database; don't rename live data.
- Web request uploads are capped at 25 MiB including the multipart payload.
- Before any real-data migration, close the laptop app and back up its actual
  `%LOCALAPPDATA%/Quote Tool/data` folder (database, uploads, settings, customers).
  Do not assume `dist/data` or the repository contains the latest data.
- Rehearse restoring that COPY into a separate private staging directory with
  access disabled during the copy. Compare counts, totals, PDF attachments and
  numbering before go-live. Never expose backups through the public directory.

## Local verification

```powershell
py -3.11 -m unittest discover -s tests -v
```

Tests use temporary storage and do not touch the laptop's saved quotes.

References: https://flask.palletsprojects.com/en/stable/web-security/
and https://docs.python.org/3.12/library/wsgiref.html

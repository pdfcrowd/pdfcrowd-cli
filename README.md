# PDFCrowd CLI

Install with Python 3.8 or newer using pipx or uv:

```sh
pipx install pdfcrowd-cli
# Alternatively: uv tool install pdfcrowd-cli
pdfcrowd html2pdf --output example.pdf https://example.com
pdfcrowd --help
pdfcrowd html2pdf help page-margins
pdfcrowd html2pdf help --json
```

The CLI package also provides the converter commands directly:

```sh
html2pdf --output example.pdf https://example.com
html2pdf --help
html2pdf help page-margins
html2pdf help --json
```

The available commands are `html2pdf`, `html2image`, `image2pdf`,
`image2image`, `pdf2pdf`, `pdf2html`, `pdf2text`, and `pdf2image`.
Without personal credentials, conversions use the demo account and produce
marked output. Set `PDFCROWD_USERNAME` and `PDFCROWD_API_KEY`, or save your
account with `pdfcrowd auth login`. For unattended login, set both environment
variables and run `pdfcrowd auth login --non-interactive`. Conversions never
prompt for credentials.

Environment credentials take priority over the saved account. To use demo
even when personal credentials are saved:

```sh
PDFCROWD_USERNAME=demo PDFCROWD_API_KEY=demo \
  html2pdf --output example.pdf https://example.com
```

Long options use `--name`. Account credentials are not accepted as arguments.
Boolean conversion options accept `true` or `false`. Compound option arguments
are separate values: `--page-margins 10mm 10mm 10mm 10mm`. Quote each value
individually when needed; semicolons inside values are preserved. Use
`--option=VALUE` for values that match an option name. Compound options can
also take a JSON array: `--http-auth='["username", "password"]'`.

`help`, version, and JSON help work offline. Conversion output uses
`--output FILE` or redirected stdout; only `pdf2text` writes results directly
to a terminal. Failed file conversions preserve the previous output.
Options can appear between input files:

```sh
pdfcrowd pdf2pdf first.pdf -o merged.pdf second.pdf
```

Diagnostics use stderr. Service errors preserve the SDK's complete message,
including URLs, option values, and documentation links.
Exit status 1 means an output
pipe closed; Ctrl-C exits with status 130.

Converter settings are read from a per-converter sectionless INI file, but
command invocations never automatically save settings. `--init-config` creates
a commented starter; `--show-config` inspects effective defaults; `--no-config`
bypasses saved conversion defaults while keeping credentials available.
`--show-config` lists conversion settings from the file and command line;
other options use their API defaults. Compound configuration values use JSON
arrays of strings. `auth login` explicitly saves shared credentials;
`auth logout` removes them. Use `help configuration` and `help authentication`
for paths, precedence, examples, and details.

For example:

```sh
pdfcrowd html2pdf --init-config
# Open the created file and uncomment the settings you want to use.
pdfcrowd html2pdf --show-config
pdfcrowd html2pdf help --init-config
```

For scripts, integrations, and AI agents, `pdfcrowd html2pdf help --json`
describes available options, argument types, defaults, and exit codes as JSON.
Use `pdfcrowd help --json` for all converters.

pipx and uv expose `pdfcrowd` and all eight converter commands. The CLI
installation includes the compatible SDK automatically.

The Python SDK contains only the API clients. All commands are provided by
`pdfcrowd-cli`, so the SDK and CLI can share a virtual environment:

```sh
python -m pip install pdfcrowd-cli
html2pdf --help
```

This public source builds independently of the private generator checkout:

```sh
python -m pip install .
make build
```

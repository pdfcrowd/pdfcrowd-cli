# PDFCrowd CLI

Convert documents and images from your terminal or scripts using the PDFCrowd service.

## Installation

Requires Python 3.8 or newer.

```sh
python -m pip install pdfcrowd-cli
```

See [installation options](https://pdfcrowd.com/api/client-library/command-line/)
for other ways to install the CLI.

## Quick start

Convert a web page to PDF:

```sh
pdfcrowd html2pdf --output example.pdf https://example.com
```

Conversions use demo credentials automatically when no account is configured.
See [authentication](https://pdfcrowd.com/api/authentication/#command-line)
to use your own account.

## Help

Discover available converters, look up an option, or get machine-readable help:

```sh
pdfcrowd --help
pdfcrowd html2pdf help page-margins
pdfcrowd help --json
```

These commands work offline. Converter commands are also available directly,
for example `html2pdf`.

## Documentation

- [HTML-to-PDF guide](https://pdfcrowd.com/api/html-to-pdf-command-line/): conversion basics and result handling.
- [Examples](https://pdfcrowd.com/api/html-to-pdf-command-line/examples/): common conversion tasks.
- [Command reference](https://pdfcrowd.com/api/html-to-pdf-command-line/ref/): commands and options.

## Build from source

From the source directory, install the build frontend and create a wheel and
source distribution:

```sh
python -m pip install build
python -m build
```

The packages are written to `dist/`.

# Copyright (C) 2009-2026 pdfcrowd.com
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation
# files (the "Software"), to deal in the Software without
# restriction, including without limitation the rights to use,
# copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the
# Software is furnished to do so, subject to the following
# conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES
# OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
# WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.

"""Load the build-generated command contract without importing the SDK."""

import json
import pkgutil


def command_options(converter, catalog):
    return catalog['command_options'] + converter.get('output_info', [])


class CLIError(Exception):
    def __init__(self, message, code=2, prefix='PDFCrowd'):
        super().__init__(message)
        self.code = code
        self.prefix = prefix


def load_catalog():
    catalog = json.loads(pkgutil.get_data('pdfcrowd_cli', 'command-spec.json'))
    if catalog.get('schema_version') != 1:
        raise CLIError('The CLI help data is incompatible with this '
                       'installation. Reinstall pdfcrowd-cli.')
    return catalog

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

"""Invoke exact SDK bindings, with no parsing or saved-state discovery."""

import os
import re
import sys
import tempfile
from pathlib import Path

from .catalog import CLIError
from .parser import option_value


def validate_sources(converter, sources):
    if not sources:
        raise CLIError('An input source is required. '
                       f'Run {converter["name"]} --help for examples.')
    if converter['name'] == 'pdf2pdf':
        if any(not Path(source).is_file() for source in sources):
            raise CLIError('PDF manipulation requires existing input files.')
    elif len(sources) != 1:
        raise CLIError('This converter requires exactly one input source.')
    elif sources[0] != '-' and not re.match(r'(?i)^https?://', sources[0]):
        if not Path(sources[0]).is_file():
            raise CLIError('Input must be an HTTP(S) URL, an existing file, '
                           "or '-' for stdin.")


def service_failure(error):
    status = str(error.getStatusCode())
    code = 3 if status in ('401', '403') else 2 if status == '470' else 4
    return CLIError(str(error), code, prefix='PDFCrowd Error')


def sdk_module(catalog):
    import pdfcrowd
    version = tuple(int(part) for part in pdfcrowd.__version__.split('.'))
    release = catalog['release']
    minimum = tuple(int(part) for part in release['sdk_minimum'].split('.'))
    maximum = tuple(int(part) for part in release['sdk_maximum'].split('.'))
    if not minimum <= version < maximum:
        raise CLIError('The installed PDFCrowd SDK is incompatible with this '
                       'CLI. Reinstall pdfcrowd-cli with its dependencies.', 4)
    return pdfcrowd


def convert(converter, settings, credentials, sources, destination, catalog,
            output_info=(), invocation_options=()):
    validate_sources(converter, sources)
    # Resolve local values before opening output or contacting the service.
    # Invocation setters also override saved setters sharing the same fields.
    options = sorted(converter['options'], key=lambda option:
                     option['name'] in invocation_options)
    calls = []
    for option in options:
        if option['name'] not in settings:
            continue
        values = settings[option['name']]
        values = values if option['repeatable'] else [values]
        for value in values:
            calls.append((option['sdk_method'], option_value(
                option, value, converter['name'])))
    sdk = sdk_module(catalog)
    client = getattr(sdk, converter['sdk_class'])(*credentials)

    def perform(output):
        client.setClientUserAgent('pdfcrowd_cli_client/1.1.0 (https://pdfcrowd.com)')
        for method, arguments in calls:
            getattr(client, method)(*arguments)
        bindings = converter['input']
        if converter['name'] == 'pdf2pdf':
            for source in sources:
                getattr(client, bindings['add_file'])(source)
            output.write(getattr(client, bindings['convert'])())
        else:
            source = sources[0]
            if source == '-':
                if not sys.stdin.buffer.peek(1):
                    raise CLIError('Input from stdin must not be empty.')
                method, argument = bindings['stream'], sys.stdin.buffer
            elif re.match(r'(?i)^https?://', source):
                method, argument = bindings['url'], source
            else:
                method, argument = bindings['file'], source
            # The generated SDK has matching streaming-output variants.
            getattr(client, method + 'ToStream')(argument, output)

    temporary = None
    try:
        if destination == '-':
            if os.name == 'nt':
                import msvcrt
                msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
            perform(sys.stdout.buffer)
            sys.stdout.buffer.flush()
        else:
            target = Path(destination)
            with tempfile.NamedTemporaryFile(
                    mode='wb', dir=target.parent, prefix=f'.{target.name}.',
                    delete=False) as output:
                temporary = output.name
                perform(output)
            os.replace(temporary, target)
            temporary = None
    except sdk.Error as error:
        raise service_failure(error) from None
    except BrokenPipeError:
        raise
    except (OSError, ValueError):
        raise CLIError('Could not read input or write output. '
                       'Check file paths and access permissions.', 4) from None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass

    for option in output_info:
        value = getattr(client, option['sdk_method'])()
        print(f'{option["label"]}: {value}', file=sys.stderr)

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

"""One runtime boundary shared by CLI launchers and module invocation."""

import os
import sys
import traceback
from functools import wraps

from .catalog import CLIError, load_catalog


def report_failure(message, error):
    print(f'PDFCrowd: {message}', file=sys.stderr)
    if os.environ.get('PDFCROWD_CLI_DEBUG') != '1':
        return
    print('Traceback (most recent call last):', file=sys.stderr)
    # Report code locations without source text, locals, or exception values,
    # which can contain credentials or private conversion inputs.
    for frame in traceback.extract_tb(error.__traceback__):
        print(f'  File "{frame.filename}", line {frame.lineno}, '
              f'in {frame.name}', file=sys.stderr)
    if isinstance(error, SyntaxError) and error.filename:
        print(f'  File "{error.filename}", line {error.lineno}',
              file=sys.stderr)
    detail = type(error).__name__
    if isinstance(error, ModuleNotFoundError):
        detail += f': No module named {error.name!r}'
    elif isinstance(error, OSError) and error.errno is not None:
        detail += f': {os.strerror(error.errno)} (errno {error.errno})'
    print(detail, file=sys.stderr)


def boundary(function):
    @wraps(function)
    def guarded(*args, **kwargs):
        try:
            result = function(*args, **kwargs)
            sys.stdout.flush()
            return result
        except BrokenPipeError:
            # Prevent a second broken-pipe diagnostic during interpreter exit.
            try:
                with open(os.devnull, 'wb') as sink:
                    os.dup2(sink.fileno(), sys.stdout.fileno())
            except (OSError, ValueError):
                pass
            return 1
        except KeyboardInterrupt:
            print('PDFCrowd: Operation cancelled.', file=sys.stderr)
            return 130
        except CLIError as error:
            print(f'{error.prefix}: {error}', file=sys.stderr)
            return error.code
        except (OSError, UnicodeError, ImportError) as error:
            report_failure('Could not load the CLI or access local files. '
                           'Check the installation and file permissions.',
                           error)
            return 4
        except EOFError as error:
            report_failure('Input ended before the command completed. '
                           'Run the command again to finish.', error)
            return 4
        except Exception as error:
            report_failure('Command failed. Check the installation, input, '
                           'and options before retrying.', error)
            return 4
    return guarded


def requested(arguments, flags):
    before_end = arguments[:arguments.index('--')] if '--' in arguments else (
        arguments)
    return any(flag in before_end for flag in flags)


def auth_arguments(arguments):
    if arguments[:2] == ['--non-interactive', 'auth']:
        return ['auth'] + arguments[2:] + ['--non-interactive']
    return arguments


@boundary
def main(command, argv=None, program=None):
    program = program or command
    arguments = auth_arguments(list(sys.argv[1:] if argv is None else argv))
    catalog = load_catalog()
    converter = catalog['converters'].get(command)
    if converter is None:
        raise CLIError('Unknown converter. Use pdfcrowd --help.')
    from . import help as discovery
    from . import state
    if arguments and arguments[0] == 'auth':
        sys.stdout.write(state.authentication(
            command, arguments[1:], catalog, program))
        return 0
    if arguments and arguments[0] == 'help':
        sys.stdout.write(discovery.render(
            converter, catalog, arguments[1:], program))
        return 0
    if not arguments or requested(arguments, ('--help', '-h')):
        # Help remains available even with invalid options or local state.
        sys.stdout.write(discovery.render(converter, catalog, [], program))
        return 0
    if requested(arguments, ('--version', '-V')):
        print(f'PDFCrowd CLI {catalog["release"]["version"]}')
        return 0
    from .parser import make_parser, normalize, invocation_settings
    normalized = normalize(arguments, converter, catalog, program)
    # argparse's two-pass intermixed parser can reinterpret options after --.
    end = normalized.index('--') if '--' in normalized else len(normalized)
    namespace = make_parser(converter, catalog, program).parse_intermixed_args(
        normalized[:end])
    namespace.sources.extend(normalized[end + 1:])
    if namespace.init_config:
        sys.stdout.write(state.init_configuration(namespace, converter))
        return 0
    if not namespace.show_config and namespace.output == '-' and (
            command != 'pdf2text' and sys.stdout.isatty()):
        raise CLIError('Binary results cannot be displayed in a terminal. '
                       'Use --output FILE or redirect/pipe stdout.')
    config_path, saved = state.configuration(namespace, converter, program)
    supplied = invocation_settings(namespace, converter, program)
    settings = dict(saved, **supplied)
    origins = {name: 'invocation' if name in supplied else 'configuration'
               for name in settings}
    if namespace.show_config:
        sys.stdout.write(state.inspect_settings(
            converter, settings, origins, config_path, namespace.no_config))
        return 0
    from .adapter import convert, validate_sources
    validate_sources(converter, namespace.sources)
    settings = state.expand_text(converter, settings, origins, config_path)
    credentials, source = state.select_credentials(command)
    if source == 'demo':
        print('Using the PDFCrowd demo account.\n'
              f'{converter["demo_notice"]}\n'
              'To use your own account, run: pdfcrowd auth login\n'
              'Or set both PDFCROWD_USERNAME and PDFCROWD_API_KEY.',
              file=sys.stderr)
    output_info = [option for option in converter.get('output_info', [])
                   if getattr(namespace, option['name'].replace('-', '_'))]
    convert(converter, settings, credentials, namespace.sources,
            namespace.output, catalog, output_info,
            invocation_options=supplied)
    return 0


@boundary
def cli_main(argv=None):
    arguments = auth_arguments(list(sys.argv[1:] if argv is None else argv))
    catalog = load_catalog()
    from . import help as discovery
    if arguments and arguments[0] == 'auth':
        return main('html2pdf', arguments, 'pdfcrowd')
    if not arguments or arguments in (['help'], ['--help'], ['-h']):
        sys.stdout.write(discovery.root_overview(catalog))
        return 0
    if arguments in (['--version'], ['-V']):
        print(f'PDFCrowd CLI {catalog["release"]["version"]}')
        return 0
    if arguments[:2] == ['help', '--json'] and len(arguments) == 2:
        import json
        print(json.dumps(catalog, indent=2))
        return 0
    if arguments[0] == 'help' and len(arguments) > 1:
        return main(arguments[1], ['help'] + arguments[2:],
                    f'pdfcrowd {arguments[1]}')
    if arguments[0] not in catalog['converters'] and requested(
            arguments, ('--help', '-h')):
        sys.stdout.write(discovery.root_overview(catalog))
        return 0
    return main(arguments[0], arguments[1:], f'pdfcrowd {arguments[0]}')


def html2pdf():
    return main('html2pdf')


def html2image():
    return main('html2image')


def image2image():
    return main('image2image')


def pdf2pdf():
    return main('pdf2pdf')


def image2pdf():
    return main('image2pdf')


def pdf2html():
    return main('pdf2html')


def pdf2text():
    return main('pdf2text')


def pdf2image():
    return main('pdf2image')



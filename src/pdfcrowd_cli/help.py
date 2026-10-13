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

"""Offline text and JSON discovery from the packaged catalog."""

import json
import shutil
import textwrap

from .catalog import CLIError, command_options


TOPICS = {
    'syntax': (
        'Options use two leading dashes, for example --output FILE.\n\n'
        'Boolean options accept true or false. Using a boolean flag alone '
        'passes true; --option=false passes false.\n\n'
        'For options with several arguments, supply each value separately '
        'and quote values containing spaces or shell punctuation. For '
        'example, an HTTP password containing a semicolon:\n'
        "  --http-auth username 'pass;word'\n\n"
        'Use --option=VALUE when a value matches an option name. Compound '
        'options can use a JSON array for such values:\n'
        '  --http-auth=\'["--help", "--version"]\'\n\n'
        'Repeatable options can be supplied several times; their order is '
        'preserved. Use -- before filenames starting with dashes. '
        'Prefix filenames such as help or auth with ./.'),
    'configuration': (
        'Save conversion defaults in a separate config file for each '
        'converter. The default file is read automatically when it exists. '
        'Command-line options override saved settings. Commands do not '
        'automatically save settings.\n\n'
        'Create a starter file, then open it and uncomment the settings '
        'you want to use:\n'
        '  {command} --init-config\n\n'
        'Inspect saved defaults and command-line overrides:\n'
        '  {command} --show-config\n\n'
        'Use --config PATH to select another file, or --no-config to ignore '
        'saved conversion settings for one command. Saved credentials '
        'still apply.\n\n'
        'The file contains option-name = value lines, without leading '
        'dashes or [section] headings. Compound settings use JSON arrays '
        'of strings. Older semicolon-separated settings are also accepted. '
        'For repeatable options, place additional values on indented '
        'continuation lines.\n\n'
        'HTML, CSS, and JavaScript options accept @{PATH} to read UTF-8 '
        'text from a file. Relative paths in the config use the config file '
        'directory; command-line paths use the current directory.\n\n'
        'Keep credentials and other sensitive settings out of this file. '
        'Use auth login or the credential environment variables.'),
    'authentication': (
        'Save your PDFCrowd username and API key for all converters:\n'
        '  {command} auth login\n\n'
        'The API-key prompt hides your input. Use your API key, rather than '
        'your account password.\n\n'
        'For scripts, set both PDFCROWD_USERNAME and PDFCROWD_API_KEY. '
        'To save that account without prompts:\n'
        '  {command} auth login --non-interactive\n\n'
        'Check which credentials will be used, or remove the saved account:\n'
        '  {command} auth status\n'
        '  {command} auth logout\n\n'
        'Status shows local settings; it does not validate the account '
        'with the service. Logout removes saved credentials; environment '
        'variables still apply.\n\n'
        'Credentials come from environment variables first, then saved '
        'credentials. Without either, conversions use the demo account '
        'and produce marked output. To use demo even with a saved account:\n'
        '  PDFCROWD_USERNAME=demo PDFCROWD_API_KEY=demo \\\n'
        '    {command} -o example.pdf https://example.com\n\n'
        'Conversions never prompt. Supply both credential environment '
        'variables together. Invalid selected credentials cause an error; '
        'the CLI will not retry with the demo account.'),
    'input-output': (
        'Supply an HTTP(S) URL, a local file, or - to read standard input. '
        'pdf2pdf accepts local PDF files in the order supplied.\n\n'
        'Save the result with --output FILE (or -o FILE). An existing file '
        'is replaced only after success. Omitted output and --output - '
        'write to standard output.\n\n'
        'Only pdf2text writes directly to a terminal; other converters require '
        'a file, pipe, or redirection. Diagnostics use stderr. '
        'A failed stdout conversion can leave partial output; check the exit '
        'status. Some converters produce ZIP archives containing '
        'their results.'),
    'exit-codes': (
        'Use the exit status to check whether a command succeeded:\n\n'
        '  0    Success\n'
        '  1    The program reading the output pipe closed it\n'
        '  2    Invalid arguments, conversion settings, or config file\n'
        '  3    Authentication failed\n'
        '  4    Conversion, file access, or installation failed\n'
        '  130  Cancelled with Ctrl-C'),
}


def paragraph(text, indent=''):
    width = max(40, min(100, shutil.get_terminal_size((80, 24)).columns))
    return '\n'.join(
        textwrap.fill(line, width=width, initial_indent=indent,
                      subsequent_indent=indent, break_on_hyphens=False,
                      break_long_words=False)
        if line and not line.startswith('  ') else indent + line
        for line in text.splitlines())


def signature(option):
    if len(option['arguments']) == 1 and (
            option['arguments'][0]['type'] == 'bool'):
        return f'--{option["name"]}[=true|false]'
    suffix = ' '.join(arg['name'].upper() for arg in option['arguments'])
    return f'--{option["name"]} {suffix}'


def control_signature(option):
    suffix = f' {option["metavar"]}' if 'metavar' in option else ''
    return ', '.join(option['flags']) + suffix


def control_detail(option, command, converter_name, include_signature=True):
    lines = [paragraph(option['description'])]
    if include_signature:
        lines[:0] = [control_signature(option), '']
    if option.get('usage'):
        lines.extend(['', 'Usage: ' + option['usage'].format(command=command)])
    if 'default' in option and option.get('action') != 'store_true':
        default = option.get('default_description', option['default'])
        lines.extend(['', f'Default: {default}'])
    for text in option.get('details', []):
        lines.extend(['', paragraph(text)])
    if option.get('scope'):
        lines.extend(['', f'Use this option with {option["scope"]}.'])
    if option.get('topic') == 'configuration':
        from .state import paths
        config, _ = paths(converter_name)
        lines.extend(['', f'Default config file: {config}'])
    if option.get('examples'):
        lines.extend(['', 'Examples'])
        lines.extend('  ' + example.format(command=command)
                     for example in option['examples'])
    if option.get('topic'):
        lines.extend(['', f'More help: {command} help {option["topic"]}'])
    return '\n'.join(lines)


def detail(option, include_signature=True):
    lines = [paragraph(option['description'])]
    if include_signature:
        lines[:0] = [signature(option), '']
    for argument in option['arguments']:
        default = argument['default']
        kind = {'bool': 'true or false', 'int': 'whole number',
                'str': 'text'}[argument['type']]
        label = argument['name'].replace('_', ' ')
        label = label.upper() if label in ('css', 'html', 'url', 'dpi') else (
            label.capitalize())
        lines.extend(['', f'{label}: {kind}'])
        if argument['description']:
            lines.append(paragraph(argument['description']))
        if default is not None:
            displayed = str(default).lower() if isinstance(default, bool) else (
                default)
            lines.append(f'Default: {displayed}')
        if argument['allowed_values']:
            values = argument['allowed_values']
            if any(item['description'] for item in values):
                lines.append('Allowed values:')
                for item in values:
                    text = str(item['value'])
                    if item['description']:
                        text += f': {item["description"]}'
                    lines.append(paragraph(text, indent='  '))
            else:
                names = ', '.join(str(item['value']) for item in values)
                lines.append(paragraph(f'Allowed values: {names}'))
        lines.extend(paragraph(hint) for hint in argument['constraints']
                     if not (argument['allowed_values'] and
                             hint.startswith('Allowed values')))
    if option['repeatable']:
        lines.extend(['', paragraph(
            'You can repeat this option. Command-line values replace the '
            'saved list and keep their supplied order.')])
    if option['sensitive']:
        lines.extend(['', paragraph(
            'Sensitive values are hidden by --show-config. Supply this option '
            'on the command line; it cannot be saved in the conversion '
            'config file.')])
    if option['text_file']:
        lines.extend(['', 'Use @{PATH} to read UTF-8 text from a file.'])
    if len(option['arguments']) == 1 and (
            option['arguments'][0]['type'] == 'bool'):
        lines.extend(['', f'Use --{option["name"]} for true, or '
                      f'--{option["name"]}=false for false.'])
    if option['warnings']:
        lines.append(paragraph(option['warnings']))
    if option['deprecated']:
        lines.append('Deprecated; consult the converter reference.')
    return '\n'.join(lines)


def render(converter, catalog, arguments, program=None):
    name = converter['name']
    command = program or name
    if arguments == ['--json']:
        result = dict(catalog, converters={name: converter})
        from .state import paths
        config, credentials = paths(name)
        result['invocation'] = {
            'converter': name, 'command': command, 'config_path': str(config),
            'credentials_path': str(credentials)}
        return json.dumps(result, indent=2) + '\n'
    if len(arguments) > 1:
        raise CLIError(f'Choose one help topic, for example '
                       f'{command} help configuration. '
                       f'For JSON, run {command} help --json.')
    topic = arguments[0] if arguments else None
    if topic and topic.startswith('--'):
        topic = topic[2:]
    if topic is None:
        return overview(converter, catalog, command)
    if topic in TOPICS:
        text = TOPICS[topic]
        if topic == 'input-output' and name == 'pdf2pdf':
            _, rest = text.split('\n\n', 1)
            text = ('Supply one or more existing local PDF files. Files are '
                    'processed in the order supplied.\n\n' + rest)
        if topic == 'syntax' and not any(option['name'] == 'http-auth'
                                         for option in converter['options']):
            text = text.replace('an HTTP password', 'a text value')
            text = text.replace("--http-auth username 'pass;word'",
                                "--option 'value;word'")
            text = text.replace('--http-auth', '--option')
        result = paragraph(text.replace('{command}', command))
        if topic in ('configuration', 'authentication'):
            from .state import paths
            config, credentials = paths(name)
            result += (f'\n\nDefault config file: {config}\n'
                       f'Shared credentials file: {credentials}')
        if topic == 'authentication':
            auth = catalog['authentication']
            result += (f'\nAPI key: {auth["api_key_url"]}\n'
                       f'{converter["demo_notice"]}')
        return result + '\n'
    options = converter['options']
    categories = {option['category']['id']: option['category']['name']
                  for option in options if not option['hidden']}
    if topic == 'categories':
        return ('Help topics\n  syntax: How to supply arguments\n'
                '  configuration: Save and load conversion defaults\n'
                '  authentication: Set up your PDFCrowd account\n'
                '  input-output: Read inputs and save results\n'
                '  exit-codes: Check whether a command succeeded\n'
                '  json: Machine-readable help for scripts and AI agents\n'
                '\nConversion option groups\n' +
                '\n'.join(f'  {key}: {value}'
                          for key, value in categories.items()) +
                f'\n\nUse {command} help CATEGORY or help OPTION.\n')
    if topic == 'all' or topic in categories:
        selected = [option for option in options if not option['hidden'] and (
            topic == 'all' or option['category']['id'] == topic)]
        controls = [control_detail(option, command, name)
                    for option in command_options(converter, catalog)]
        details = [detail(option) for option in selected]
        return '\n\n'.join(
            (controls if topic == 'all' else []) + details) + '\n'
    for option in command_options(converter, catalog):
        if option['name'] == topic or topic in option['flags']:
            return control_detail(option, command, name) + '\n'
    for option in options:
        if option['name'] == topic:
            return detail(option) + '\n'
    raise CLIError(f'Unknown help topic. Run {command} help categories '
                   f'to list topics, or {command} help all for every option.')


def overview(converter, catalog, program=None):
    name = converter['name']
    command = program or name
    from .state import paths
    config, _ = paths(name)
    sources = 'SOURCE [SOURCE ...]' if name == 'pdf2pdf' else 'SOURCE'
    input_file = 'input.pdf' if name.startswith('pdf') else 'input.png'
    example = f'{command} --output result {input_file}'
    if name == 'html2pdf':
        example = f'{command} --output result.pdf https://example.com'
    elif name == 'pdf2pdf':
        example = f'{command} first.pdf --output result.pdf second.pdf'
    elif name == 'html2image':
        example = f'{command} --output result.png https://example.com'
    elif name in ('image2pdf', 'pdf2text'):
        suffix = 'pdf' if name == 'image2pdf' else 'txt'
        example = f'{command} --output result.{suffix} {input_file}'
    input_description = ('One or more local PDF files, in the supplied order.'
                         if name == 'pdf2pdf' else
                         'An HTTP(S) URL, an existing file, or - for stdin.')
    lines = [f'PDFCrowd: {converter["description"]}',
             f'Guide: {converter["guide_url"]}', '',
             f'Usage: {command} [options] {sources}',
             f'Input: {input_description}', '', 'Command options']
    for option in command_options(converter, catalog):
        if option.get('topic') == 'configuration' or option.get('scope'):
            continue
        lines.append(f'  {control_signature(option)}')
        lines.append(f'      {option["description"]}')
    lines.extend(['', 'Examples', f'  {example}'])
    common = {'page-size', 'orientation', 'page-margins', 'no-margins',
              'viewport-width', 'header-html', 'footer-html', 'custom-css',
              'custom-javascript', 'output-format', 'pages', 'scale-factor'}
    common_options = [f'  {signature(option)}'
                      for option in converter['options']
                      if option['name'] in common]
    if common_options:
        lines.extend(['', 'Common conversion options'] + common_options)
    lines.extend(['', f'See all options: {command} help all', '',
                  'Authentication',
                  f'  {command} auth login       Save your account',
                  f'  {command} auth status      Show which account is used',
                  f'  {command} auth logout      Remove the saved account',
                  '  Or set PDFCROWD_USERNAME and PDFCROWD_API_KEY.',
                  '  Credentials: environment, saved account, then demo.',
                  '  Scripts: auth login --non-interactive requires both '
                  'environment variables.',
                  f'  {converter["demo_notice"]}', '', 'Configuration',
                  f'  Default file: {config}',
                  '  Saved conversion defaults are loaded automatically.',
                  '  Commands do not automatically save conversion settings.',
                  '  Saved credentials are managed separately.', ''])
    for option in catalog['command_options']:
        if option.get('topic') == 'configuration':
            lines.append(f'  {control_signature(option)}')
            lines.append(f'      {option["description"]}')
    lines.extend(['', f'  More details: {command} help configuration',
                  '', 'More help',
                  f'  {command} help all          List every option',
                  f'  {command} help OPTION       Explain one option',
                  f'  {command} help categories   List help topics and groups',
                  f'  {command} help --json       JSON for scripts and AI '
                  'agents'])
    return '\n'.join(lines) + '\n'


def root_overview(catalog):
    lines = ['PDFCrowd CLI', '',
             'Usage: pdfcrowd CONVERTER [options] SOURCE',
             '       pdfcrowd auth ACTION',
             '       pdfcrowd help CONVERTER [TOPIC]', '',
             'Available converters']
    lines.extend(f'  {name}: {converter["description"]}'
                 for name, converter in catalog['converters'].items())
    lines.extend(['', 'Account setup',
                  '  auth login    Save your PDFCrowd username and API key',
                  '  auth status   Show which credentials will be used',
                  '  auth logout   Remove saved credentials',
                  '  Credentials are shared by all converter commands.',
                  '  Without personal credentials, conversions use the demo '
                  'account.', '', 'Examples',
                  '  pdfcrowd html2pdf -o example.pdf https://example.com',
                  '  pdfcrowd pdf2pdf first.pdf -o merged.pdf second.pdf',
                  '  pdfcrowd auth login',
                  '  pdfcrowd html2pdf help all', '',
                  'Options',
                  '  --help, -h       Show this overview',
                  '  --version, -V    Show the PDFCrowd CLI version', '',
                  'Machine-readable help for scripts and AI agents',
                  '  pdfcrowd help --json',
                  'Module invocation: python -m pdfcrowd_cli ...'])
    return '\n'.join(lines) + '\n'

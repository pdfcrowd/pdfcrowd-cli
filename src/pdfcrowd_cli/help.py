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


def command_summaries(catalog, program, parent):
    return [paragraph(f'{program} {name}: {record["description"]}', '  ')
            for name, record in catalog['commands'].items()
            if name.startswith(parent + ' ')]


def summary_rows(rows):
    width = max(40, min(100, shutil.get_terminal_size((80, 24)).columns))
    column = max(len(label) for label, _ in rows) + 4
    lines = []
    for label, description in rows:
        if width - column < 24:
            lines.extend([paragraph(label, '  '),
                          paragraph(description, '    ')])
        else:
            lines.append(textwrap.fill(
                description, width=width,
                initial_indent='  ' + label.ljust(column - 2),
                subsequent_indent=' ' * column, break_on_hyphens=False,
                break_long_words=False))
    return lines


def authentication_summary(catalog):
    auth = catalog['authentication']
    return [
        *summary_rows([
            ('pdfcrowd auth login',
             catalog['commands']['auth login']['description'])]),
        paragraph('Or set ' + ' and '.join(auth['environment']) + '.', '  '),
        paragraph(auth['sources']['demo'], '  '),
    ]


def help_summary(catalog, command):
    topics = catalog['commands']['help']['topics']
    json_option = next(option for option in catalog['command_options']
                       if option['name'] == 'json')
    return summary_rows([
        (f'{command} help all', topics['all']),
        (f'{command} help OPTION', 'Explain one option.'),
        (f'{command} help categories', topics['categories']),
        (f'{command} help authentication', topics['authentication']),
        (f'{command} help configuration', topics['configuration']),
        (json_option['usage'].format(command=command),
         json_option['description']),
    ])


def heading(title):
    return title + '\n' + '=' * len(title)


def section(title, *blocks):
    return title + '\n' + '\n\n'.join(
        paragraph(block, '  ') for block in blocks)


def authentication_topic(converter, catalog, command):
    from .state import paths
    _, credentials = paths(converter['name'])
    auth = catalog['authentication']
    commands = catalog['commands']
    login = commands['auth login']
    unattended = next(option for option in catalog['command_options']
                      if option['name'] == 'non-interactive')
    actions = []
    for action in ('status', 'logout'):
        record = commands['auth ' + action]
        actions.extend([record['usage'].format(command=command),
                        record['description'], *record.get('details', [])])
    precedence = '\n'.join(
        f'{index}. {auth["sources"][source]}'
        for index, source in enumerate(auth['precedence'], 1))
    return '\n\n'.join([
        heading('Authentication'),
        section('Save an account', f'{command} auth login',
                login['description'], login['details'][0],
                auth['hint'], 'API key: ' + auth['api_key_url']),
        section('Environment variables',
                'Set ' + ' and '.join(auth['environment']) +
                ' to use your account for conversions.',
                unattended['usage'].format(command=command),
                unattended['description'], *unattended.get('details', [])),
        section('Inspect or remove saved credentials', *actions),
        section('Credential selection', precedence, *auth['details'],
                converter['demo_notice']),
        section('Credentials file', str(credentials)),
    ])


def configuration_topic(converter, catalog, command):
    from .state import paths
    config, _ = paths(converter['name'])
    return '\n\n'.join([
        heading('Configuration'),
        section('Create saved defaults',
                f'{command} --init-config',
                'Open the created file and uncomment the settings you want '
                'to use. Conversion defaults are saved separately for each '
                'converter. The default file is read automatically when it '
                'exists. Commands do not automatically save settings.'),
        section('Inspect defaults', f'{command} --show-config',
                'Command-line options override saved settings.'),
        section('Select or bypass a file',
                'Use --config PATH to select another file, or --no-config '
                'to ignore saved conversion settings for one command. '
                'Saved credentials still apply.'),
        section('File syntax',
                'The file contains option-name = value lines, without '
                'leading dashes or [section] headings.',
                'Compound settings use JSON arrays of strings. Older '
                'semicolon-separated settings are also accepted. For '
                'repeatable options, place additional values on indented '
                'continuation lines.',
                'HTML, CSS, and JavaScript options accept @{PATH} to read '
                'UTF-8 text from a file. Relative paths in the config use '
                'the config file directory; command-line paths use the '
                'current directory.',
                'Keep credentials and other sensitive settings out of this '
                'file. Use auth login or the credential environment variables.'),
        section('Default config file', str(config)),
        section('Related help', f'{command} help --config',
                f'{command} help authentication'),
    ])


def syntax_topic(converter, catalog, command):
    has_http_auth = any(option['name'] == 'http-auth'
                        for option in converter['options'])
    compound = '--http-auth' if has_http_auth else '--option'
    sample = ("--http-auth username 'pass;word'" if has_http_auth else
              "--option 'value;word'")
    return '\n\n'.join([
        heading('Argument syntax'),
        section('Option names',
                'Options use two leading dashes, for example --output FILE.'),
        section('Boolean options',
                'Boolean options accept true or false. Using a boolean flag '
                'alone passes true; --option=false passes false.'),
        section('Multiple arguments and quoting',
                'For options with several arguments, supply each value '
                'separately and quote values containing spaces or shell '
                'punctuation. Semicolons inside quoted values are preserved.',
                sample),
        section('Values that look like options',
                'Use --option=VALUE when a value matches an option name. '
                'Compound options can use a JSON array for such values:',
                compound + "='[\"--help\", \"--version\"]'"),
        section('Repeated options',
                'Repeatable options can be supplied several times; their '
                'order is preserved.'),
        section('Special filenames',
                'Use -- before filenames starting with dashes. Prefix '
                'filenames such as help or auth with ./.'),
    ])


def input_output_topic(converter, catalog, command):
    if 'add_file' in converter['input']:
        input_text = ('Supply one or more existing local PDF files. Files '
                      'are processed in the order supplied. URLs and '
                      'standard input are not accepted.')
    else:
        input_text = ('Supply an HTTP(S) URL, a local file, or - to read '
                      'standard input.')
    terminal = ('Text results can be written directly to a terminal.'
                if converter['name'] == 'pdf2text' else
                'Results require a file, pipe, or redirection; conversion '
                'output is not written directly to a terminal.')
    output = [
        'Save the result with --output FILE (or -o FILE). An existing file '
        'is replaced only after success. Omitted output and --output - '
        'write to standard output.', terminal,
    ]
    if any(option['name'] == 'print-is-zipped-output'
           for option in converter['output_info']):
        output.append('The result can be a ZIP archive containing multiple '
                      'output files.')
    return '\n\n'.join([
        heading('Input and output'), section('Input', input_text),
        section('Output', *output),
        section('Diagnostics',
                'Diagnostics use stderr. A failed stdout conversion can '
                'leave partial output; check the exit status.'),
        section('Related help', f'{command} help --output',
                f'{command} help exit-codes'),
    ])


def exit_codes_topic(converter, catalog, command):
    descriptions = {
        'success': 'Success',
        'broken_pipe': 'The program reading the output pipe closed it',
        'usage': 'Invalid arguments, conversion settings, or config file',
        'authentication': 'Authentication failed',
        'conversion': 'Conversion, file access, or installation failed',
        'interrupted': 'Cancelled with Ctrl-C',
    }
    rows = [(str(code), descriptions[name])
            for name, code in sorted(catalog['exit_codes'].items(),
                                     key=lambda item: item[1])]
    return heading('Exit codes') + '\n\n' + '\n'.join(summary_rows(rows))


TOPICS = {
    'authentication': authentication_topic,
    'configuration': configuration_topic,
    'syntax': syntax_topic,
    'input-output': input_output_topic,
    'exit-codes': exit_codes_topic,
}


def command_detail(name, catalog, program, converter_name):
    record = catalog['commands'][name]
    lines = ['Usage: ' + record['usage'].format(command=program), '',
             paragraph(record['description'])]
    lines.extend(paragraph(text) for text in record.get('details', []))
    for argument in record.get('arguments', []):
        lines.extend(['', paragraph(argument['name'] + ': ' +
                                    argument['description'])])
    children = command_summaries(catalog, program, name)
    if children:
        lines.extend(['', 'Commands', *children])
    if record.get('topics'):
        lines.extend(['', 'Topics', *[
            f'  {topic}: {description}'
            for topic, description in record['topics'].items()]])
    for option in catalog['command_options']:
        if option.get('scope') == name:
            lines.extend(['', control_detail(option, program, converter_name)])
    if record.get('examples'):
        lines.extend(['', 'Examples', *[
            '  ' + example.format(command=program)
            for example in record['examples']]])
    if name == 'auth login':
        auth = catalog['authentication']
        lines.extend(['', auth['hint'], 'API key: ' + auth['api_key_url']])
    return '\n'.join(lines)


def control_detail(option, command, converter_name):
    label = control_signature(option)
    if option.get('scope'):
        label = option['scope'] + ' ' + label
    parts = [label, paragraph(option['description'], '  ')]
    if option.get('usage'):
        parts.append('Usage: ' + option['usage'].format(command=command))
    if 'default' in option and option.get('action') != 'store_true':
        default = option.get('default_description', option['default'])
        parts.append(f'Default: {default}')
    notes = []
    if option.get('scope'):
        notes.append(f'Use this option with {option["scope"]}.')
    notes.extend(option.get('details', []))
    if option.get('topic') == 'configuration':
        from .state import paths
        config, _ = paths(converter_name)
        notes.append(f'Default config file: {config}')
    if notes:
        parts.append(section('Notes', *notes))
    if option.get('examples'):
        parts.append(section('Examples', *[
            example.format(command=command)
            for example in option['examples']]))
    if option.get('topic'):
        parts.append(section('Related help',
                             f'{command} help {option["topic"]}'))
    return '\n\n'.join(parts)


def detail(option):
    parts = [signature(option), paragraph(option['description'], '  ')]
    arguments = []
    for argument in option['arguments']:
        default = argument['default']
        kind = {'bool': 'true or false', 'int': 'whole number',
                'str': 'text'}[argument['type']]
        label = argument['name'].replace('_', ' ')
        label = label.upper() if label in ('css', 'html', 'url', 'dpi') else (
            label.capitalize())
        lines = [f'  {label}: {kind}']
        if argument['description']:
            lines.append(paragraph(argument['description'], '    '))
        if default is not None:
            displayed = str(default).lower() if isinstance(default, bool) else (
                default)
            lines.append(paragraph(f'Default: {displayed}', '    '))
        if argument['allowed_values']:
            values = argument['allowed_values']
            if any(item['description'] for item in values):
                lines.append('    Allowed values:')
                for item in values:
                    text = str(item['value'])
                    if item['description']:
                        text += f': {item["description"]}'
                    lines.append(paragraph(text, '      '))
            else:
                names = ', '.join(str(item['value']) for item in values)
                lines.append(paragraph(f'Allowed values: {names}', '    '))
        lines.extend(paragraph(hint, '    ')
                     for hint in argument['constraints']
                     if not (argument['allowed_values'] and
                             hint.startswith('Allowed values')))
        arguments.append('\n'.join(lines))
    if arguments:
        parts.append('Arguments\n' + '\n\n'.join(arguments))
    notes = []
    if option['repeatable']:
        notes.append('You can repeat this option. Command-line values replace '
                     'the saved list and keep their supplied order.')
    if option['sensitive']:
        notes.append('Sensitive values are hidden by --show-config. Supply '
                     'this option on the command line; it cannot be saved '
                     'in the conversion config file.')
    if option['text_file']:
        notes.append('Use @{PATH} to read UTF-8 text from a file.')
    if len(option['arguments']) == 1 and (
            option['arguments'][0]['type'] == 'bool'):
        notes.append(f'Use --{option["name"]} for true, or '
                     f'--{option["name"]}=false for false.')
    if option['warnings']:
        notes.append(option['warnings'])
    if notes:
        parts.append(section('Notes', *notes))
    return '\n\n'.join(parts)


def option_listing(converter, catalog, command, topic, categories):
    groups = {}
    if topic == 'all':
        for option in catalog['command_options']:
            group = ('Options for ' + option['scope'] if option.get('scope')
                     else 'Configuration' if option.get('topic') ==
                     'configuration' else 'Command options')
            groups.setdefault(group, []).append(
                control_detail(option, command, converter['name']))
        groups['Conversion information'] = [
            control_detail(option, command, converter['name'])
            for option in converter['output_info']]
    sections = list(groups.items())
    for key, title in categories.items():
        if topic not in ('all', key):
            continue
        sections.append((title, [
            detail(option) for option in converter['options']
            if not option['hidden'] and option['category']['id'] == key]))
    return '\n\n'.join(heading(title) + '\n\n' + '\n\n'.join(entries)
                         for title, entries in sections if entries)


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
        return TOPICS[topic](converter, catalog, command) + '\n'
    options = converter['options']
    categories = {option['category']['id']: option['category']['name']
                  for option in options if not option['hidden']}
    if topic == 'categories':
        return ('Help topics\n' + '\n'.join(summary_rows(list(
                catalog['commands']['help']['topics'].items()))) +
                '\n\nConversion option groups\n' +
                '\n'.join(summary_rows(list(categories.items()))) +
                '\n\n' + paragraph(
                    f'Use {command} help CATEGORY or help OPTION.') + '\n')
    if topic == 'all' or topic in categories:
        return option_listing(converter, catalog, command, topic,
                              categories) + '\n'
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
             'Usage: ' + converter['usage'].replace(name, command, 1),
             f'Input: {input_description}', '', 'Command options']
    for option in catalog['command_options']:
        if option.get('topic') == 'configuration' or option.get('scope'):
            continue
        lines.append(f'  {control_signature(option)}')
        lines.append(f'      {option["description"]}')
    lines.extend(['', 'Examples', f'  {example}'])
    common = {'page-size', 'orientation', 'page-margins', 'no-margins',
              'content-viewport-width', 'header-html', 'footer-html', 'custom-css',
              'custom-javascript', 'output-format', 'pages', 'scale-factor'}
    common_options = [f'  {signature(option)}'
                      for option in converter['options']
                      if option['name'] in common]
    if common_options:
        lines.extend(['', 'Common conversion options'] + common_options)
    lines.extend(['', 'Authentication', *authentication_summary(catalog),
                  '', 'Configuration',
                  f'  Default file: {config}',
                  '  Saved conversion defaults are loaded automatically.',
                  '  Commands do not automatically save conversion settings.',
                  '  Saved credentials are managed separately.', ''])
    for option in catalog['command_options']:
        if option.get('topic') == 'configuration':
            lines.append(f'  {control_signature(option)}')
            lines.append(f'      {option["description"]}')
    lines.extend(['', 'More help', *help_summary(catalog, command)])
    return '\n'.join(lines) + '\n'


def root_overview(catalog):
    lines = ['PDFCrowd CLI', '',
             'Usage: pdfcrowd CONVERTER [options] SOURCE',
             '       ' + catalog['commands']['auth']['usage'].format(
                 command='pdfcrowd'),
             '       ' + catalog['commands']['help']['root_usage'], '',
             'Available converters']
    lines.extend(f'  {name}: {converter["description"]}'
                 for name, converter in catalog['converters'].items())
    lines.extend(['', 'Account setup', *authentication_summary(catalog),
                  '', 'Examples',
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

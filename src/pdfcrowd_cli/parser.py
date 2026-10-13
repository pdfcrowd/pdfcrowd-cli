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

"""Canonical argument parsing and catalog-based option resolution."""

import argparse
import json
import re

from .catalog import CLIError, command_options


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's messages may contain raw argv, URLs, or secret values.
        match = re.match(r'argument ([^:]+):', message)
        if match:
            flags = match.group(1).split('/')
            action = next((self._option_string_actions.get(flag)
                           for flag in flags
                           if flag in self._option_string_actions), None)
            if action is not None:
                flag = action.option_strings[0]
                if 'not allowed with argument' in message:
                    raise CLIError(
                        '--config and --no-config cannot be used together.')
                if action.choices:
                    choices = ', '.join(action.choices)
                    raise CLIError(f'{flag} requires one of: {choices}.')
                if action.nargs == 0:
                    raise CLIError(f'{flag} does not take a value. '
                                   f'Use {flag} on its own.')
                raise CLIError(f'Invalid value for {flag}. '
                               f'Run {self.prog} help {flag}.')
        raise CLIError('Unrecognized command arguments. '
                       f'Run {self.prog} --help or {self.prog} help syntax.')


def make_parser(converter, catalog, program=None):
    parser = Parser(prog=program or converter['name'], add_help=False,
                    allow_abbrev=False, argument_default=argparse.SUPPRESS)
    parser.add_argument('sources', nargs='*', default=[])
    groups = {}
    for option in command_options(converter, catalog):
        if option.get('scope'):
            continue
        target = parser
        if option.get('group'):
            group = option['group']
            if group not in groups:
                groups[group] = parser.add_mutually_exclusive_group()
            target = groups[group]
        kwargs = {key: option[key] for key in (
            'action', 'default', 'choices', 'metavar') if key in option}
        target.add_argument(*option['flags'], **kwargs)
    for index, option in enumerate(converter['options']):
        parser.add_argument(
            *option['flags'], dest=f'option_{index}',
            action='append' if option['repeatable'] else 'store')
    return parser


def normalize(argv, converter, catalog, program=None):
    program = program or converter['name']
    options = {option['flags'][0]: option for option in converter['options']}
    controls = {flag: option for option in command_options(converter, catalog)
                for flag in option['flags']}
    known = set(options) | set(controls)
    removed = {
        option['unsupported']['flag']: option['unsupported']['replacement']
        for option in converter['options']}
    result = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == '--':
            result.extend(argv[index:])
            break
        flag = token.split('=', 1)[0]
        if flag in ('--user-name', '--api-key', '-user-name', '-api-key'):
            raise CLIError('Account credentials are not accepted as options. '
                           f'Run {program} auth login, or set '
                           'PDFCROWD_USERNAME and PDFCROWD_API_KEY.')
        if flag in removed:
            raise CLIError(f'Removed option {flag}. Use {removed[flag]}.')
        option = options.get(flag)
        control = controls.get(flag)
        if control and control.get('scope'):
            usage = control['usage'].format(command=program)
            raise CLIError(f'{flag} applies only to {control["scope"]}. '
                           f'Run {usage}.')
        if option and len(option['arguments']) == 1 and (
                option['arguments'][0]['type'] == 'bool') and '=' not in token:
            value = 'true'
            if index + 1 < len(argv) and argv[index + 1].lower() in (
                    'true', 'false'):
                index += 1
                value = argv[index].lower()
            result.append(f'{flag}={value}')
        elif (option or control) and '=' not in token and (
                option or 'metavar' in control):
            count = len(option['arguments']) if option else 1
            values = []
            for offset in range(1, count + 1):
                if index + offset >= len(argv) or (
                        argv[index + offset].split('=', 1)[0] in known) or (
                        argv[index + offset] == '--'):
                    label = 'value' if count == 1 else 'values'
                    names = ' '.join(arg['name'].upper() for arg in (
                        option['arguments'])) if option else (
                            control['metavar'])
                    raise CLIError(f'{flag} requires {count} {label}: {names}. '
                                   f'Run {program} help {flag}.')
                values.append(argv[index + offset])
            value = json.dumps(values) if count > 1 else values[0]
            canonical = option['flags'][0] if option else control['flags'][0]
            result.append(f'{canonical}={value}')
            index += count
        else:
            result.append(token)
        index += 1
    return result


def option_value(option, value, command):
    count = len(option['arguments'])
    values = [value]
    if count > 1:
        try:
            # JSON arrays preserve literal separators in saved settings.
            # Existing sectionless configurations may still use semicolons.
            values = json.loads(value) if value.startswith('[') else (
                value.split(';'))
        except ValueError:
            values = None
        if not isinstance(values, list) or len(values) != count or any(
                not isinstance(part, str) for part in values):
            raise CLIError(f'--{option["name"]} requires {count} values. '
                           f'Run {command} help {option["name"]}.')
    resolved = []
    for definition, part in zip(option['arguments'], values):
        kind = definition['type']
        try:
            if kind == 'bool':
                if part.lower() not in ('true', 'false'):
                    raise ValueError()
                part = part.lower() == 'true'
            elif kind == 'int':
                part = int(part)
        except ValueError:
            expected = 'true or false' if kind == 'bool' else 'a whole number'
            raise CLIError(f'Invalid value for --{option["name"]}. '
                           f'Use {expected}. Run {command} help '
                           f'{option["name"]}.') from None
        resolved.append(part)
    return resolved


def invocation_settings(namespace, converter, program=None):
    values = vars(namespace)
    result = {}
    for index, option in enumerate(converter['options']):
        if f'option_{index}' not in values:
            continue
        value = values[f'option_{index}']
        for item in value if option['repeatable'] else [value]:
            option_value(option, item, program or converter['name'])
        result[option['name']] = value
    return result

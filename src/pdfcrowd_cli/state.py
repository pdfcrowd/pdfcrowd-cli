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

"""Explicit converter defaults and separately protected account storage."""

import configparser
import getpass
import json
import os
from pathlib import Path
import stat
import sys
import tempfile

from .catalog import CLIError
from .parser import option_value


def paths(command):
    from platformdirs import user_config_dir
    directory = Path(user_config_dir('pdfcrowd', appauthor=False)) / 'cli'
    return directory / f'{command}.ini', directory / 'credentials.json'


def configuration(namespace, converter, program=None):
    program = program or converter['name']
    default, _ = paths(converter['name'])
    selected = Path(getattr(namespace, 'config', default))
    if namespace.no_config:
        return selected, {}
    try:
        text = selected.read_text(encoding='utf-8')
    except FileNotFoundError:
        if not hasattr(namespace, 'config'):
            return selected, {}
        raise CLIError('The selected config file does not exist. '
                       'Choose an existing file with --config PATH, or create '
                       'one with --init-config --config PATH.') from None
    except (OSError, UnicodeError):
        raise CLIError('Could not read the config file. Check its permissions '
                       'and save it as UTF-8 text.') from None
    parser = configparser.ConfigParser(interpolation=None, strict=True,
                                       empty_lines_in_values=False)
    try:
        parser.read_string('[converter]\n' + text)
        if parser.sections() != ['converter']:
            raise ValueError()
        values = dict(parser['converter'])
    except (configparser.Error, ValueError):
        raise CLIError(
            'Invalid config file. Use option-name = value lines without '
            f'[section] headings. Run {program} help '
            'configuration for examples.') from None
    options = {option['name']: option for option in converter['options']}
    result = {}
    for name, value in values.items():
        option = options.get(name)
        if option is None:
            raise CLIError('The config file contains an unknown setting. '
                           'Use option names without leading dashes. '
                           f'Run {program} help configuration.')
        if not option['configuration']:
            raise CLIError(f'--{option["name"]} contains sensitive data '
                           'and cannot be saved in a conversion config file. '
                           'Pass this option on the command line.')
        if option['repeatable']:
            value = [line.strip() for line in value.splitlines()
                     if line.strip()]
        for item in value if isinstance(value, list) else [value]:
            option_value(option, item, program)
        result[name] = value
    return selected, result


def expand_text(converter, settings, origins, config_path):
    result = dict(settings)
    for option in converter['options']:
        name = option['name']
        if not option['text_file'] or name not in result:
            continue
        value = result[name]
        if not isinstance(value, str) or not (
                value.startswith('@{') and value.endswith('}')):
            continue
        reference = Path(value[2:-1])
        if not reference.is_absolute() and origins[name] == 'configuration':
            reference = config_path.parent / reference
        try:
            result[name] = reference.read_bytes().decode('utf-8')
        except UnicodeDecodeError:
            raise CLIError(f'Cannot read file "{reference}" for --{name}: '
                           'the file is not encoded as UTF-8.') from None
        except OSError as error:
            reason = error.strerror or str(error)
            raise CLIError(f'Cannot read file "{reference}" for --{name}: '
                           f'{reason}.') from None
    return result


def inspect_settings(converter, settings, origins, config_path,
                     no_config=False):
    status = ('ignored by --no-config' if no_config else
              'loaded' if config_path.exists() else 'not created')
    lines = [f'Config file: {config_path} ({status})', '',
             'Conversion settings from the config file and command line.',
             'Other options use their API defaults.', '']
    if not settings:
        return '\n'.join(lines + ['No conversion settings configured.']) + '\n'
    for option in converter['options']:
        name = option['name']
        if name not in settings:
            continue
        value = settings[name]
        if option['sensitive']:
            value = '[hidden: sensitive value]'
        elif option['text_file'] and not (
                isinstance(value, str) and value.startswith('@{') and
                value.endswith('}')):
            value = '[hidden: inline text]'
        elif isinstance(value, list):
            value = json.dumps(value)
        elif '\n' in value or '\r' in value:
            value = json.dumps(value)
        origin = ('command line' if origins[name] == 'invocation' else
                  'config file')
        lines.append(f'--{name}: {value} ({origin})')
    return '\n'.join(lines) + '\n'


def init_configuration(namespace, converter):
    default, _ = paths(converter['name'])
    target = Path(getattr(namespace, 'config', default))
    if namespace.no_config:
        raise CLIError('--init-config cannot be combined with --no-config.')
    lines = [
        '# PDFCrowd converter defaults; no sections are needed.',
        '# Remove a comment marker to enable a setting.',
        '# Command-line options override these defaults.',
        '# Conversion commands do not automatically save settings here.',
        '# Text-content settings accept @{PATH}; '
        'paths are relative to this file.',
        f'# Reference: {converter["reference_url"]}', '', '# Common options',
    ]
    for name in ('page-size', 'orientation', 'output-format', 'debug-log'):
        for option in converter['options']:
            if option['name'] == name:
                default_value = option['arguments'][0]['default']
                if default_value is not None:
                    lines.append(f'# {name} = {default_value}')
    try:
        target.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        with target.open('x', encoding='utf-8') as output:
            output.write('\n'.join(lines) + '\n')
    except FileExistsError:
        raise CLIError('The config file already exists and was left unchanged. '
                       'Edit it directly, or use --config PATH to choose '
                       'another file.')
    except OSError:
        raise CLIError(
            'Could not create configuration. Check directory access.')
    return (f'Created config file: {target}\n'
            'Open this file and remove the leading # from settings you want '
            'to use.\n'
            'The default file is loaded automatically. For a custom file, '
            'pass --config PATH when converting.\n')


def validate_pair(username, key):
    if not all(isinstance(value, str) and value and '\n' not in value and
               '\r' not in value for value in (username, key)):
        raise CLIError('Supply a complete username and API-key pair.', 3)
    return username, key


def environment_pair():
    names = ('PDFCROWD_USERNAME', 'PDFCROWD_API_KEY')
    if not any(name in os.environ for name in names):
        return None
    try:
        return validate_pair(*(os.environ.get(name) for name in names))
    except CLIError:
        raise CLIError('Set both PDFCROWD_USERNAME and PDFCROWD_API_KEY. '
                       'Clear both to use saved credentials or the demo '
                       'account.', 3) from None


def check_protection(path, metadata):
    if os.name == 'nt':
        from .windows import check_private
        check_private(path)
    elif metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        raise CLIError('Credential file or directory is not private. '
                       'It must belong to you. Set file permissions to 600 '
                       'and directory permissions to 700.', 3)


def file_pair(path):
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    except FileNotFoundError:
        return None
    except OSError:
        raise CLIError('Could not read saved credentials.', 3) from None
    with os.fdopen(descriptor, 'r', encoding='utf-8') as source:
        if path.is_symlink() or path.parent.is_symlink():
            raise CLIError('Credential storage must not use symlinks.', 3)
        check_protection(path.parent, path.parent.lstat())
        metadata = os.fstat(source.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise CLIError('Credential storage must be a regular file.', 3)
        check_protection(path, metadata)
        try:
            pair = json.load(source)
            if not isinstance(pair, dict):
                raise ValueError()
            return validate_pair(pair.get('username'), pair.get('api_key'))
        except (ValueError, UnicodeError, CLIError):
            raise CLIError('Saved credentials are invalid. '
                           'Run pdfcrowd auth login to save your account '
                           'again.', 3) from None


def select_credentials(command):
    _, path = paths(command)
    pair = environment_pair()
    source = 'environment'
    if pair is None:
        pair = file_pair(path)
        source = 'credentials_file'
    if pair is None or pair == ('demo', 'demo'):
        return ('demo', 'demo'), 'demo'
    return pair, source


def save_pair(path, pair):
    temporary = None
    try:
        path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        if path.parent.is_symlink():
            raise CLIError('Credential directory must not be a symlink.', 3)
        if os.name == 'nt':
            from .windows import protect
            protect(path.parent)
        check_protection(path.parent, path.parent.stat())
        descriptor, temporary = tempfile.mkstemp(dir=path.parent)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as output:
            if os.name == 'nt':
                protect(Path(temporary))
            output.write(json.dumps({'username': pair[0], 'api_key': pair[1]})
                         + '\n')
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise CLIError('Could not save protected credentials. '
                       'Previous credentials were retained.', 3) from None
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def authentication(command, arguments, catalog, program=None):
    program = program or command
    from .help import command_detail
    actions = {name.split(' ', 1)[1] for name in catalog['commands']
               if name.startswith('auth ')}
    if not arguments:
        return command_detail('auth', catalog, program, command) + '\n'
    action = arguments[0]
    extra = arguments[1:]
    if any(flag in arguments for flag in ('--help', '-h')):
        name = f'auth {action}' if action in actions else 'auth'
        _, path = paths(command)
        return (command_detail(name, catalog, program, command) +
                f'\n\nShared credentials file: {path}\n')
    if action not in actions:
        raise CLIError('Unknown authentication action. '
                       f'Run {program} auth --help.')
    if extra and extra != ['--non-interactive']:
        raise CLIError('Invalid authentication arguments. '
                       f'Run {program} auth {action} --help.')
    if extra == ['--non-interactive'] and action != 'login':
        raise CLIError('--non-interactive applies only to auth login.')
    _, path = paths(command)
    if action == 'logout':
        try:
            path.unlink()
        except FileNotFoundError:
            return ('No saved credentials to remove.\n'
                    'Credential environment variables still apply if set.\n')
        except OSError:
            raise CLIError('Could not remove saved credentials.', 3)
        return ('Saved credentials removed for all converter commands.\n'
                'Credential environment variables still apply if set.\n')
    if action == 'status':
        pair, source = select_credentials(command)
        labels = {'environment': 'environment variables',
                  'credentials_file': 'saved credentials',
                  'demo': 'demo account'}
        result = f'Account source: {labels[source]}\nUsername: {pair[0]}\n'
        if source == 'credentials_file':
            result += f'Credentials file: {path}\n'
        if source == 'demo':
            result += catalog['converters'][command]['demo_notice'] + '\n'
        return (result + 'This status check does not verify the account '
                'with PDFCrowd.\n')
    pair = environment_pair()
    if pair is None:
        if extra == ['--non-interactive'] or not sys.stdin.isatty():
            raise CLIError('Login without prompts requires PDFCROWD_USERNAME '
                           'and PDFCROWD_API_KEY. Set both, or run '
                           f'{program} auth login in a terminal.', 3)
        auth = catalog['authentication']
        print(f'Save your PDFCrowd account for all converter commands.\n'
              f'API key: {auth["api_key_url"]}\n{auth["hint"]}',
              file=sys.stderr)
        pair = validate_pair(input('Username: '), getpass.getpass('API key: '))
    if pair == ('demo', 'demo'):
        raise CLIError('Login requires personal account credentials.', 3)
    save_pair(path, pair)
    return (f'Saved account for all converter commands.\n'
            f'Credentials file: {path}\n'
            'The account will be verified during conversion.\n')

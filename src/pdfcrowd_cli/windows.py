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

"""Owner-only credential DACLs using native Windows security APIs.

See Microsoft's GetNamedSecurityInfoW and SetNamedSecurityInfoW contracts.
Native Windows validation remains part of platform release acceptance.
"""

import ctypes
from ctypes import wintypes

from .catalog import CLIError


class ACLSize(ctypes.Structure):
    _fields_ = [('count', wintypes.DWORD), ('used', wintypes.DWORD),
                ('free', wintypes.DWORD)]


class ACEHeader(ctypes.Structure):
    _fields_ = [('kind', wintypes.BYTE), ('flags', wintypes.BYTE),
                ('size', wintypes.WORD)]


class Security:
    def __init__(self):
        self.advapi = ctypes.WinDLL('advapi32', use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        pointer = ctypes.c_void_p
        output = ctypes.POINTER(pointer)
        integer = wintypes.DWORD
        self.function(self.kernel, 'GetCurrentProcess', pointer, [])
        self.function(self.kernel, 'CloseHandle', wintypes.BOOL, [pointer])
        self.function(self.kernel, 'LocalFree', pointer, [pointer])
        signatures = {
            'OpenProcessToken': (wintypes.BOOL, [pointer, integer, output]),
            'GetTokenInformation': (wintypes.BOOL, [
                pointer, integer, pointer, integer, ctypes.POINTER(integer)]),
            'ConvertSidToStringSidW': (wintypes.BOOL, [pointer, output]),
            'ConvertStringSecurityDescriptorToSecurityDescriptorW': (
                wintypes.BOOL, [wintypes.LPCWSTR, integer, output, pointer]),
            'GetSecurityDescriptorDacl': (wintypes.BOOL, [
                pointer, ctypes.POINTER(wintypes.BOOL), output,
                ctypes.POINTER(wintypes.BOOL)]),
            'GetNamedSecurityInfoW': (integer, [wintypes.LPCWSTR, integer,
                integer, output, output, output, output, output]),
            'SetNamedSecurityInfoW': (integer, [wintypes.LPWSTR, integer,
                integer, pointer, pointer, pointer, pointer]),
            'GetAclInformation': (wintypes.BOOL, [pointer, pointer,
                                                integer, integer]),
            'GetAce': (wintypes.BOOL, [pointer, integer, output]),
        }
        for name, (result, arguments) in signatures.items():
            self.function(self.advapi, name, result, arguments)

    @staticmethod
    def function(library, name, result, arguments):
        function = getattr(library, name)
        function.restype, function.argtypes = result, arguments

    @staticmethod
    def require(succeeded):
        if not succeeded:
            raise CLIError('Could not establish or verify private Windows '
                           'credential access. Use environment credentials.', 3)

    def sid_text(self, sid):
        text = ctypes.c_void_p()
        self.require(self.advapi.ConvertSidToStringSidW(
            sid, ctypes.byref(text)))
        try:
            return ctypes.wstring_at(text)
        finally:
            self.kernel.LocalFree(text)

    def current_sid(self):
        token = ctypes.c_void_p()
        self.require(self.advapi.OpenProcessToken(
            self.kernel.GetCurrentProcess(), 8, ctypes.byref(token)))
        try:
            size = wintypes.DWORD()
            self.advapi.GetTokenInformation(token, 1, None, 0,
                                             ctypes.byref(size))
            self.require(size.value)
            buffer = ctypes.create_string_buffer(size.value)
            self.require(self.advapi.GetTokenInformation(
                token, 1, buffer, size, ctypes.byref(size)))
            sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
            return self.sid_text(sid)
        finally:
            self.kernel.CloseHandle(token)

    def descriptor(self, path):
        owner, dacl, descriptor = (ctypes.c_void_p() for _ in range(3))
        result = self.advapi.GetNamedSecurityInfoW(
            str(path), 1, 5, ctypes.byref(owner), None, ctypes.byref(dacl),
            None, ctypes.byref(descriptor))
        self.require(result == 0)
        return owner, dacl, descriptor


def check_private(path):
    security = Security()
    current = security.current_sid()
    owner, dacl, descriptor = security.descriptor(path)
    try:
        security.require(owner and security.sid_text(owner) == current and dacl)
        size = ACLSize()
        security.require(security.advapi.GetAclInformation(
            dacl, ctypes.byref(size), ctypes.sizeof(size), 2))
        allowed = False
        for index in range(size.count):
            ace = ctypes.c_void_p()
            security.require(security.advapi.GetAce(dacl, index,
                                                     ctypes.byref(ace)))
            header = ctypes.cast(ace, ctypes.POINTER(ACEHeader)).contents
            if header.flags & 8 or header.kind == 1:
                continue  # Inherit-only or denying ACEs cannot grant access.
            security.require(header.kind == 0)
            security.require(security.sid_text(ace.value + 8) == current)
            allowed = True
        security.require(allowed)
    finally:
        security.kernel.LocalFree(descriptor)


def protect(path):
    security = Security()
    current = security.current_sid()
    owner, _, existing = security.descriptor(path)
    try:
        security.require(owner and security.sid_text(owner) == current)
    finally:
        security.kernel.LocalFree(existing)
    descriptor = ctypes.c_void_p()
    inheritance = 'OICI' if path.is_dir() else ''
    security.require(
        security.advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            f'D:P(A;{inheritance};FA;;;{current})', 1,
            ctypes.byref(descriptor), None))
    try:
        present, defaulted = wintypes.BOOL(), wintypes.BOOL()
        dacl = ctypes.c_void_p()
        security.require(security.advapi.GetSecurityDescriptorDacl(
            descriptor, ctypes.byref(present), ctypes.byref(dacl),
            ctypes.byref(defaulted)))
        security.require(present.value and dacl)
        security.require(security.advapi.SetNamedSecurityInfoW(
            str(path), 1, 0x80000004, None, None, dacl, None) == 0)
        check_private(path)
    finally:
        security.kernel.LocalFree(descriptor)

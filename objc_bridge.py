"""Low-level Objective-C / ctypes plumbing.

A tiny bridge over `libobjc`'s `objc_msgSend` plus the handful of Cocoa/Core
Graphics structs the overlay needs. This is write-once glue: everything else
in the project calls Objective-C through `_msg` and the helpers here.
"""

import ctypes
import ctypes.util


class NSPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double)]


class NSSize(ctypes.Structure):
    _fields_ = [("width", ctypes.c_double), ("height", ctypes.c_double)]


class NSRect(ctypes.Structure):
    _fields_ = [("origin", NSPoint), ("size", NSSize)]


class CGRect(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_double),
        ("y", ctypes.c_double),
        ("w", ctypes.c_double),
        ("h", ctypes.c_double),
    ]


def _objc_setup():
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.objc_getClass.argtypes = [ctypes.c_char_p]
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.sel_registerName.argtypes = [ctypes.c_char_p]
    return objc


def _msg(objc, obj, selector, *args, restype=None, argtypes=None):
    sel = objc.sel_registerName(selector.encode())
    if restype is None:
        restype = ctypes.c_void_p
    if argtypes is None:
        argtypes = [ctypes.c_void_p] * len(args)

    proto = ctypes.CFUNCTYPE(restype, ctypes.c_void_p, ctypes.c_void_p, *argtypes)
    fn = ctypes.cast(objc.objc_msgSend, proto)
    converted = []
    for argtype, value in zip(argtypes, args):
        if isinstance(value, ctypes._SimpleCData) or isinstance(value, argtype):
            converted.append(value)
        else:
            converted.append(argtype(value))
    return fn(obj, sel, *converted)


def _nsstring(objc, text):
    NSString = objc.objc_getClass(b"NSString")
    return _msg(
        objc,
        NSString,
        "stringWithUTF8String:",
        text.encode(),
        argtypes=[ctypes.c_char_p],
    )


def _nsnumber_double(objc, number):
    if not number:
        return 0.0
    return _msg(objc, number, "doubleValue", restype=ctypes.c_double)


def _nsnumber_int(objc, number):
    if not number:
        return 0
    return _msg(objc, number, "intValue", restype=ctypes.c_int)


def _nsstring_text(objc, ns_string):
    if not ns_string:
        return ""
    value = _msg(objc, ns_string, "UTF8String", restype=ctypes.c_char_p)
    return value.decode(errors="ignore") if value else ""

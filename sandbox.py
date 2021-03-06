import __builtin__
import code
import ctypes
import json
import linecache
import os
import sys
import traceback
import types
if sys.stdin.isatty():
	import readline

import protocol


execFilename = sys.argv[-1]
if not (len(sys.argv) > 1 and execFilename.endswith('.py')):
	execFilename = None

#
# sanitize some properties of a few builtin types
#

getDict = ctypes.pythonapi._PyObject_GetDictPtr
getDict.restype = ctypes.POINTER(ctypes.py_object)
getDict.argtypes = [ctypes.py_object]

def delDictAttr(obj, name):
	dictPtr = getDict(obj)
	if dictPtr and dictPtr.contents:
		dictObj = dictPtr.contents.value
		if dictObj and name in dictObj:
			del dictPtr.contents.value[name]

delDictAttr(type, '__subclasses__')

delDictAttr(types.CodeType, 'co_code')
delDictAttr(types.CodeType, 'co_consts')
delDictAttr(types.CodeType, 'co_names')
delDictAttr(types.CodeType, 'co_varnames')

delDictAttr(types.FrameType, 'f_builtins')
#delDictAttr(types.FrameType, 'f_code') # this seems okay to leave in
delDictAttr(types.FrameType, 'f_globals')
delDictAttr(types.FrameType, 'f_locals')

delDictAttr(types.FunctionType, '__closure__') # >= 2.6
delDictAttr(types.FunctionType, '__code__') # >= 2.6
delDictAttr(types.FunctionType, '__globals__') # >= 2.6
delDictAttr(types.FunctionType, 'func_closure')
delDictAttr(types.FunctionType, 'func_code')
delDictAttr(types.FunctionType, 'func_globals')

delDictAttr(types.GeneratorType, 'gi_code') # >= 2.6
delDictAttr(types.GeneratorType, 'gi_frame')


#
# restrict importing modules
#

allowedModules = set((
	'string', 're', 'sre_compile', 'sre_parse', '_sre', 'sre_constants', 'strop', 'struct', '_struct',
		'StringIO', 'cStringIO', 'textwrap', 'encodings', 'unicodedata', 'stringprep', # 7
	'datetime', 'calendar', 'collections', 'heapq', 'bisect', 'array', 'sets',
		'queue', 'copy', 'pprint', 'repr', # 8
	'numbers', 'math', 'cmath', 'decimal', 'fractions', 'random', 'itertools', 'functools', '_functools', 'operator', # 9
	'pickle', 'cPickle', 'copy_reg', 'marshal', # 11 # no dbm stuff, no shelve
	'hashlib', 'hmac', # 14
	'time', # 15
	'json', 'base64', 'binascii', # 18
	'xml',
	#'traceback', # super dangerous, never allow this
	'protocol', 'sandcastle',
))
restrictedModules = {
	'types': (
		('NoneType', 'TypeType', 'BooleanType', 'IntType', 'LongType', 'FloatType', 'ComplexType',
		 'StringType', 'UnicodeType', 'TupleType', 'ListType', 'DictType', 'DictionaryType',
		 'FunctionType', 'LambdaType', 'GeneratorType',
		 'ClassType', 'InstanceType', 'MethodType', 'UnboundMethodType',
		 'BuiltinFunctionType', 'BuiltinMethodType', 'ModuleType',
		 'XRangeType', 'SliceType', 'EllipsisType', 'TracebackType', 'FrameType', 'BufferType', 'DictProxyType',
		 'NotImplementedType', 'GetSetDescriptorType', 'MemberDescriptorType', 'StringTypes'),
		{}
	),
#	'codecs': (
#		('register', 'lookup', 'getencoder', 'getdecoder', 'getincrementalencoder', 'getincrementaldecoder',
#		 'getreader', 'getwriter',
#		 'register_error', 'lookup_error', 'strict_errors', 'replace_errors', 'ignore_errors',
#		 'xmlcharrefreplace_errors', 'backslashreplace_errors',
#		 'iterencode', 'iterdecode',
#		 'BOM', 'BOM_BE', 'BOM_LE', 'BOM_UTF8', 'BOM_UTF16', 'BOM_UTF16_BE', 'BOM_UTF16_LE',
#		 'BOM_UTF32', 'BOM_UTF32_BE', 'BOM_UTF32_LE',
#		 'Codec', 'IncrementalEncoder', 'IncrementalDecoder',
#		 'StreamWriter', 'StreamReader', 'StreamReaderWriter', 'StreamRecoder'),
#		{}
#	),
	'os': (
		('altsep', 'extsep', 'name', 'pathsep', 'sep'),
		{
			'path': (['sep'], {})
		}
	),
	'sys': (
		('api_version', 'byteorder', 'copyright', 'float_info', 'getrecursionlimit', 'getrefcount', 'getsizeof',
		 'hexversion', 'maxint', 'maxsize', 'maxunicode', 'subversion', 'version_info'),
		 # exclude meta_path and path_hooks, they're too voodoo to deal with right now
		{}
	),
}

def loadRestrictedModule(src, dst, variables, fullname):
	newSys.modules[fullname] = dst
	for key in ('__doc__', '__name__', '__package__'):
		setattr(dst, key, getattr(src, key))
	for key in variables[0]:
		setattr(dst, key, getattr(src, key))
	for (key, value) in variables[1].iteritems():
		srcVar = getattr(src, key)
		assert type(srcVar) is types.ModuleType
		submodule = types.ModuleType(key)
		loadRestrictedModule(srcVar, submodule, value, '%s.%s' % (fullname, key))
		setattr(dst, key, submodule)

newSys = types.ModuleType('sys')
newSys.modules = {}
loadRestrictedModule(sys, newSys, restrictedModules['sys'], 'sys')

oldImport = __builtin__.__import__
def __import__(name, g=None, l=None, fromlist=None, level=-1):
	existingModule = newSys.modules.get(name)
	if existingModule:
		return existingModule
	tokens = name.split('.')
	module = newSys.modules.get(tokens[0])
	if not module:
		#print "import", name
		try:
			sitePkgs = os.listdir('site-packages')
		except OSError:
			sitePkgs = []
		filename = tokens[0] + '.py'
		if filename in sitePkgs:
			module = types.ModuleType(tokens[0])
			newSys.modules[tokens[0]] = module
			module.__file__ = filename
			module.__dict__['__builtins__'] = restrictedBuiltins
			execfile('site-packages/' + filename, module.__dict__)
		elif tokens[0] in allowedModules:
			module = oldImport(name, g, l, fromlist, level)
		else:
			restrictedVars = restrictedModules.get(tokens[0])
			if not restrictedVars:
				raise ImportError("No module named " + tokens[0])
			module = types.ModuleType(tokens[0])
			loadRestrictedModule(oldImport(name, g, l, fromlist, level), module, restrictedVars, name)
		newSys.modules[tokens[0]] = module
	submodule = module
	for token in tokens[1:]: # make sure submodules exist
		try:
			submodule = getattr(module, token)
			assert type(submodule) is types.ModuleType
		except:
			raise ImportError("No module named " + token)
	return module


#
# new open() will return a proxy for file objects
#

proxiedFileAttrs = (
	'__delattr__', '__doc__', '__enter__', '__exit__', '__format__', '__hash__',
	'__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__str__', '__subclasshook__',
	'close', 'closed', 'encoding', 'errors', 'fileno', 'flush', 'isatty', 'mode',
	'name', 'newlines', 'next', 'read', 'readinto', 'readline', 'readlines', 'seek',
	'softspace', 'tell', 'truncate', 'write', 'writelines', 'xreadlines')
blockedFileAttrs = ('__class__', '__getattribute__', '__iter__')

def restrictedOpen(filename, mode='r', bufsize=-1):
	#print "restrictedOpen", filename
	if type(mode) not in (str, unicode):
		raise TypeError("file() argument 2 must be string, not " + type(mode).__name__)
	mode = str(mode)
	if filename != execFilename or 'w' in mode or 'a' in mode:
		raise IOError(13, "Permission denied: '%s'" % filename)
	_file = open(filename, mode, bufsize)
	def __getattribute__(self, name):
		if name in proxiedFileAttrs: return _file.__getattribute__(name)
		if name in blockedFileAttrs: return object.__getattribute__(self, name)
	def __iter__(self): return self
	namespace = {'__getattribute__': __getattribute__, '__iter__': __iter__}
	return type('file', (object,), namespace)()
restrictedOpen.func_name = 'open'


#
# context manager for printing sanitized tracebacks
#

# our replacement for traceback.print_tb which doesn't use FrameType.f_globals
# copied shamelessly from traceback.py, 4-space indenting and all
def print_tb(tb, limit=None, file=None):
    """Print up to 'limit' stack trace entries from the traceback 'tb'.

    If 'limit' is omitted or None, all entries are printed.  If 'file'
    is omitted or None, the output goes to sys.stderr; otherwise
    'file' should be an open file or file-like object with a write()
    method.
    """
    if file is None:
        file = sys.stderr
    if limit is None:
        if hasattr(sys, 'tracebacklimit'):
            limit = sys.tracebacklimit
    n = 0
    while tb is not None and (limit is None or n < limit):
        f = tb.tb_frame
        lineno = tb.tb_lineno
        co = f.f_code
        filename = co.co_filename
        name = co.co_name
        traceback._print(file,
               '  File "%s", line %d, in %s' % (filename,lineno,name))
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, {})#f.f_globals)
        if line: traceback._print(file, '    ' + line.strip())
        tb = tb.tb_next
        n = n+1
traceback.print_tb = print_tb

class TracebackPrinter(object):
	def __init__(self):
		self.skipLines = 0
	def write(self, s):
		if s.startswith('  File "%s",' % __file__) or 'protocol.py", line' in s:
			self.skipLines = 2
		if self.skipLines:
			self.skipLines -= 1
			return
		if 'RuntimeError' in s:
			s = s.replace('maximum recursion depth exceeded while calling a Python object',
			              'maximum recursion depth exceeded')
		sys.stderr.write(s)
class Restricted(object):
	@staticmethod
	def __enter__(): pass
	@staticmethod
	def __exit__(exc_type, exc_value, tb):
		if not tb: return
		if exc_type is not SystemExit:
			try:
				if issubclass(exc_type, SyntaxError) and isinstance(exc_value, tuple) and len(exc_value) == 2:
					exc_value = SyntaxError(*exc_value)
				traceback.print_exception(exc_type, exc_value, tb, file=TracebackPrinter())
			finally:
				exc_type = exc_value = tb = None
			return True
restricted = Restricted()


#
# new locals/globals namespace
#

newSys.modules['__builtin__'] = restrictedBuiltins = types.ModuleType('__builtin__')

for allowedAttr in ('ArithmeticError', 'AssertionError', 'AttributeError', 'BaseException', 'BufferError', 'BytesWarning', 'DeprecationWarning', 'EOFError', 'Ellipsis', 'EnvironmentError', 'Exception', 'False', 'FloatingPointError', 'FutureWarning', 'GeneratorExit', 'IOError', 'ImportError', 'ImportWarning', 'IndentationError', 'IndexError', 'KeyError', 'KeyboardInterrupt', 'LookupError', 'MemoryError', 'NameError', 'None', 'NotImplemented', 'NotImplementedError', 'OSError', 'OverflowError', 'PendingDeprecationWarning', 'ReferenceError', 'RuntimeError', 'RuntimeWarning', 'StandardError', 'StopIteration', 'SyntaxError', 'SyntaxWarning', 'SystemError', 'SystemExit', 'TabError', 'True', 'TypeError', 'UnboundLocalError', 'UnicodeDecodeError', 'UnicodeEncodeError', 'UnicodeError', 'UnicodeTranslateError', 'UnicodeWarning', 'UserWarning', 'ValueError', 'Warning', 'ZeroDivisionError', '__debug__', '__doc__', '__package__', 'abs', 'all', 'any', 'apply', 'basestring', 'bin', 'bool', 'buffer', 'bytearray', 'bytes', 'callable', 'chr', 'classmethod', 'cmp', 'coerce', 'complex', 'copyright', 'credits', 'delattr', 'dict', 'dir', 'divmod', 'enumerate', 'eval', 'exit', 'filter', 'float', 'format', 'frozenset', 'getattr', 'globals', 'hasattr', 'hash', 'hex', 'id', 'int', 'intern', 'isinstance', 'issubclass', 'iter', 'len', 'license', 'list', 'locals', 'long', 'map', 'max', 'min', 'next', 'object', 'oct', 'open', 'ord', 'pow', 'print', 'property', 'quit', 'range', 'reduce', 'repr', 'reversed', 'round', 'set', 'setattr', 'slice', 'sorted', 'staticmethod', 'str', 'sum', 'super', 'tuple', 'type', 'unichr', 'unicode', 'vars', 'xrange', 'zip'):
	setattr(restrictedBuiltins, allowedAttr, getattr(__builtin__, allowedAttr))

def notImplemented(*args, **kwargs): raise NotImplementedError
for disabledFunc in ('compile', 'execfile', 'help', 'input', 'raw_input', 'reload'):
	setattr(restrictedBuiltins, disabledFunc, notImplemented)

restrictedBuiltins.__import__ = __import__
restrictedBuiltins.open = restrictedOpen

restrictedScope = {
	'__builtins__': restrictedBuiltins,
	'__name__': '__main__',
	'__file__': execFilename,
	'__doc__': None,
	'__package__': None
}
sys.setrecursionlimit(50) # reasonable for newbies... right?


if execFilename:
	with restricted:
		execfile(execFilename, restrictedScope)
print "Python", sys.version
newSys.ps1 = '>>> '
newSys.ps2 = '... '


srcStr = ''
promptStr = newSys.ps1
def readObject():
	global promptStr
	ps = newSys.ps1 if not srcStr else newSys.ps2
	if ps is not promptStr:
		protocol.writeObj({'msg': 'setPrompt', 'ps': ps})
		promptStr = ps
	msg = raw_input()
	assert msg != '.'
	try:
		obj = json.loads(msg)
		assert type(obj) is dict
		return obj
	except:
		return {'msg': 'eval', 'cmd': msg}

def evalCmd(msg):
	global srcStr
	srcStr += msg['cmd']
	try:
		codeObj = code.compile_command(srcStr, '<stdin>')
		if codeObj:
			try:
				# if srcStr is an expr, eval it and store any non-None result in _
				codeObj = code.compile_command(srcStr, '<stdin>', 'eval')
				if codeObj is None: # empty line
					return
				with restricted:
					result = eval(codeObj, restrictedScope)
					if result is not None:
						print repr(result)
						restrictedScope['_'] = result
			except SyntaxError:
				# non-expressions are just exec'd and have no effect on _
				with restricted: exec codeObj in restrictedScope
			srcStr = ''
		else:
			srcStr += '\n'
	except:
		try:
			(exc_type, exc_value) = sys.exc_info()[:2]
			traceback.print_exception(exc_type, exc_value, None)
		finally:
			exc_type = exc_value = None
		srcStr = ''
protocol.addMessageHook('eval', evalCmd)


while True:
	try:
		protocol.dispatchMessage(readObject())
	except:
		break

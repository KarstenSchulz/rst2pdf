# -*- coding: utf-8 -*-

# :Author: a Pygments author|contributor; Felix Wiemann; Guenter Milde
# :Date: $Date$
# :Copyright: This module has been placed in the public domain.
#
# This is a merge of `Using Pygments in ReST documents`_ from the pygments_
# documentation, and a `proof of concept`_ by Felix Wiemann.
#
# ========== ===========================================================
# 2007-06-01 Removed redundancy from class values.
# 2007-06-04 Merge of successive tokens of same type
#            (code taken from pygments.formatters.others).
# 2007-06-05 Separate docutils formatter script
#            Use pygments' CSS class names (like the html formatter)
#            allowing the use of pygments-produced style sheets.
# 2007-06-07 Merge in the formatting of the parsed tokens
#            (misnamed as docutils_formatter) as class DocutilsInterface
# 2007-06-08 Failsave implementation (fallback to a standard literal block
#            if pygments not found)
# ========== ===========================================================
#
# ::

"""Define and register a code-block directive using pygments"""


# Requirements
# ------------
# ::

import codecs

from docutils import nodes
from docutils.parsers.rst import directives

try:
    import pygments
    from pygments.lexers import get_lexer_by_name
    from pygments.formatters.html import _get_ttype_class
except ImportError:
    pass

from ..log import log


# Customisation
# -------------
#
# Do not insert inline nodes for the following tokens.
# (You could add e.g. Token.Punctuation like ``['', 'p']``.) ::

unstyled_tokens = ['']


# DocutilsInterface
# -----------------
#
# This interface class combines code from
# pygments.formatters.html and pygments.formatters.others.
#
# It does not require anything of docutils and could also become a part of
# pygments::


class DocutilsInterface(object):
    """Parse `code` string and yield "classified" tokens.

    Arguments

      code     -- string of source code to parse
      language -- formal language the code is written in.

    Merge subsequent tokens of the same token-type.

    Yields the tokens as ``(ttype_class, value)`` tuples,
    where ttype_class is taken from pygments.token.STANDARD_TYPES and
    corresponds to the class argument used in pygments html output.

    """

    def __init__(self, code, language, custom_args={}):
        self.code = code
        self.language = language
        self.custom_args = custom_args

    def lex(self):
        # Get lexer for language (use text as fallback)
        try:
            if self.language and str(self.language).lower() != 'none':
                lexer = get_lexer_by_name(self.language.lower(), **self.custom_args)
            else:
                lexer = get_lexer_by_name('text', **self.custom_args)
        except ValueError:
            log.info("no pygments lexer for %s, using 'text'" % self.language)
            # what happens if pygment isn't present ?
            lexer = get_lexer_by_name('text')
        return pygments.lex(self.code, lexer)

    def join(self, tokens):
        """join subsequent tokens of same token-type"""
        tokens = iter(tokens)
        (lasttype, lastval) = next(tokens)
        for ttype, value in tokens:
            if ttype is lasttype:
                lastval += value
            else:
                yield (lasttype, lastval)
                (lasttype, lastval) = (ttype, value)
        yield (lasttype, lastval)

    def __iter__(self):
        """parse code string and yield "clasified" tokens"""
        try:
            tokens = self.lex()
        except IOError:
            log.info("Pygments lexer not found, using fallback")
            # TODO: write message to INFO
            yield ('', self.code)
            return

        for ttype, value in self.join(tokens):
            yield (_get_ttype_class(ttype), value)


# code_block_directive
# --------------------
# ::


def code_block_directive(
    name,
    arguments,
    options,
    content,
    lineno,
    content_offset,
    block_text,
    state,
    state_machine,
):
    """Parse and classify content of a code_block."""
    if 'include' in options:
        try:
            if 'encoding' in options:
                encoding = options['encoding']
            else:
                encoding = 'utf-8'
            content = codecs.open(options['include'], 'r', encoding).read().rstrip()
        except (IOError, UnicodeError):  # no file or problem finding it or reading it
            log.error('Error reading file: "%s" L %s' % (options['include'], lineno))
            content = u''
        line_offset = 0
        if content:
            # here we define the start-at and end-at options
            # so that limit is included in extraction
            # this is different than the start-after directive of docutils
            # (docutils/parsers/rst/directives/misc.py L73+)
            # which excludes the beginning
            # the reason is we want to be able to define a start-at like
            # def mymethod(self)
            # and have such a definition included

            after_text = options.get('start-at', None)
            if after_text:
                # skip content in include_text before *and NOT incl.* a matching text
                after_index = content.find(after_text)
                if after_index < 0:
                    raise state_machine.reporter.severe(
                        'Problem with "start-at" option of "%s" '
                        'code-block directive:\nText not found.' % options['start-at']
                    )
                # patch mmueller start
                # Move the after_index to the beginning of the line with the
                # match.
                for char in content[after_index:0:-1]:
                    # codecs always opens binary. This works with '\n', '\r' and
                    # '\r\n'. We are going backwards, so '\n' is found first
                    # in '\r\n'.
                    # Going with .splitlines() seems more appropriate
                    # but needs a few more changes.
                    if char == u'\n' or char == u'\r':
                        break
                    after_index -= 1
                # patch mmueller end

                content = content[after_index:]
                line_offset = len(content[:after_index].splitlines()) - 1

            after_text = options.get('start-after', None)
            if after_text:
                # skip content in include_text before *and incl.* a matching text
                after_index = content.find(after_text)
                if after_index < 0:
                    raise state_machine.reporter.severe(
                        'Problem with "start-after" option of "%s" '
                        'code-block directive:\nText not found.'
                        % options['start-after']
                    )
                after_index = after_index + len(after_text)

                # Move the after_index to the start of the line after the match
                for char in content[after_index:]:
                    if char == u'\n':
                        break
                    after_index += 1

                line_offset = len(content[:after_index].splitlines())
                content = content[after_index:]

            # same changes here for the same reason
            before_text = options.get('end-at', None)
            if before_text:
                # skip content in include_text after *and incl.* a matching text
                before_index = content.find(before_text)
                if before_index < 0:
                    raise state_machine.reporter.severe(
                        'Problem with "end-at" option of "%s" '
                        'code-block directive:\nText not found.' % options['end-at']
                    )
                content = content[: before_index + len(before_text)]

            before_text = options.get('end-before', None)
            if before_text:
                # skip content in include_text after *and NOT incl.* a matching text
                before_index = content.find(before_text)
                if before_index < 0:
                    raise state_machine.reporter.severe(
                        'Problem with "end-before" option of "%s" '
                        'code-block directive:\nText not found.' % options['end-before']
                    )
                content = content[:before_index]

    else:
        line_offset = options.get('linenos_offset')
        content = u'\n'.join(content)

    if 'tabsize' in options:
        tabw = options['tabsize']
    else:
        tabw = int(options.get('tab-width', 8))

    content = content.replace('\t', ' ' * tabw)

    # hl_lines is the option, but if it isn't used, the alias emphasize-lines is also supported for Sphinx compatibility
    hl_lines = options.get('hl_lines', [])
    # if hl_lines isn't used, check if emphasize-lines should be
    if hl_lines == []:
        hl_lines = options.get('emphasize-lines', [])

    withln = 'linenos' in options
    if 'linenos_offset' not in options:
        line_offset = 0

    try:
        language = arguments[0]
    except IndexError:
        language = 'text'

    # create a literal block element and set class argument
    code_block = nodes.literal_block(classes=["code", language])

    lineno = 1 + line_offset
    total_lines = content.count('\n') + 1 + line_offset
    if withln:
        lnwidth = len(str(total_lines))
        fstr = "\n%%%dd " % lnwidth
        linenumber_cls = 'linenumber'
        if hl_lines and lineno not in hl_lines:
            linenumber_cls = 'pygments-diml'
        code_block += nodes.inline(
            fstr[1:] % lineno, fstr[1:] % lineno, classes=[linenumber_cls]
        )

    # parse content with pygments and add to code_block element
    for cls, value in DocutilsInterface(content, language, options):
        if hl_lines and lineno not in hl_lines:
            cls = "diml"
        if withln and "\n" in value:
            # Split on the "\n"s
            values = value.split("\n")
            # The first piece, pass as-is
            c = ''
            if cls != '':
                c = 'pygments-diml'
            code_block += nodes.inline(values[0], values[0], classes=[c])

            # On the second and later pieces, insert \n and linenos
            linenos = range(lineno, lineno + len(values))
            for chunk, ln in list(zip(values, linenos))[1:]:
                if ln <= total_lines:
                    linenumber_cls = 'linenumber'
                    c = ''
                    if hl_lines and (ln) not in hl_lines:
                        linenumber_cls = 'pygments-diml'
                        c = 'pygments-diml'

                    code_block += nodes.inline(
                        fstr % ln, fstr % ln, classes=[linenumber_cls]
                    )
                    code_block += nodes.inline(chunk, chunk, classes=[c])
            lineno += len(values) - 1

        elif cls in unstyled_tokens:
            if "\n" in value:
                lineno = lineno + value.count("\n")
            # insert as Text to decrease the verbosity of the output.
            code_block += nodes.Text(value, value)
        else:
            if "\n" in value:
                lineno = lineno + value.count("\n")
            code_block += nodes.inline(value, value, classes=["pygments-" + cls])

    return [code_block]


# Custom argument validators
# --------------------------
# ::
#
# Move to separated module??


def zero_or_positive_int(argument):
    """
    Converts a string into python positive integer including zero.
    None is a special case; it is regarded as zero.
    """
    if argument is None:
        return 0
    elif argument == '0':
        return 0
    else:
        return directives.positive_int(argument)


def string_list(argument):
    """
    Converts a space- or comma-separated list of values into a python list
    of strings.
    (Directive option conversion function)
    Based in positive_int_list of docutils.parsers.rst.directives
    """
    if ',' in argument:
        entries = argument.split(',')
    else:
        entries = argument.split()
    return entries


def string_bool(argument):
    """
    Converts True, true, False, False in python boolean values
    """
    if argument is None:
        msg = 'argument required but none supplied; choose from "True" or "False"'
        raise ValueError(msg)

    elif argument.lower() == 'true':
        return True
    elif argument.lower() == 'false':
        return False
    else:
        raise ValueError('"%s" unknown; choose from "True" or "False"' % argument)


def csharp_unicodelevel(argument):
    return directives.choice(argument, ('none', 'basic', 'full'))


def lhs_litstyle(argument):
    return directives.choice(argument, ('bird', 'latex'))


def raw_compress(argument):
    return directives.choice(argument, ('gz', 'bz2'))


# Register Directive
# ------------------
# ::

code_block_directive.arguments = (0, 1, 1)
code_block_directive.content = 1
code_block_directive.options = {
    'include': directives.unchanged_required,
    'start-at': directives.unchanged_required,
    'end-at': directives.unchanged_required,
    'start-after': directives.unchanged_required,
    'end-before': directives.unchanged_required,
    'linenos': directives.unchanged,
    'linenos_offset': zero_or_positive_int,
    'tab-width': directives.unchanged,
    'hl_lines': directives.positive_int_list,
    'emphasize-lines': directives.positive_int_list,
    # generic
    'stripnl': string_bool,
    'stripall': string_bool,
    'ensurenl': string_bool,
    'tabsize': directives.positive_int,
    'encoding': directives.encoding,
    # Lua
    'func_name_hightlighting': string_bool,
    'disabled_modules': string_list,
    # Python Console
    'python3': string_bool,
    # Delphi
    'turbopascal': string_bool,
    'delphi': string_bool,
    'freepascal': string_bool,
    'units': string_list,
    # Modula2
    'pim': string_bool,
    'iso': string_bool,
    'objm2': string_bool,
    'gm2ext': string_bool,
    # CSharp
    'unicodelevel': csharp_unicodelevel,
    # Literate haskell
    'litstyle': lhs_litstyle,
    # Raw
    'compress': raw_compress,
    # Rst
    'handlecodeblocks': string_bool,
    # Php
    'startinline': string_bool,
    'funcnamehighlighting': string_bool,
    'disabledmodules': string_list,
}


# .. _doctutils: http://docutils.sf.net/
# .. _pygments: http://pygments.org/
# .. _Using Pygments in ReST documents: http://pygments.org/docs/rstdirective/
# .. _proof of concept:
#      http://article.gmane.org/gmane.text.docutils.user/3689
#
# Test output
# -----------
#
# If called from the command line, call the docutils publisher to render the
# input::

if __name__ == '__main__':
    from docutils.core import publish_cmdline, default_description
    from docutils.parsers.rst import directives

    directives.register_directive('code-block', code_block_directive)
    description = "code-block directive test output" + default_description
    try:
        import locale

        locale.setlocale(locale.LC_ALL, '')
    except Exception:
        pass
    publish_cmdline(writer_name='html', description=description)

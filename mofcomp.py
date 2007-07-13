#
# (C) Copyright 2006-2007 Novell, Inc. 
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as
# published by the Free Software Foundation; either version 2 of the
# License, or (at your option) any later version.
#   
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#   
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
#

# Author: Bart Whiteley <bwhiteley suse.de>

import sys
import os
import ply.lex as lex
import ply.yacc as yacc
from ply.lex import TOKEN
import pywbem
import cimdb

reserved = {
    'any':'ANY',
    'as':'AS',
    'association':'ASSOCIATION',
    'class':'CLASS',
    'disableoverride':'DISABLEOVERRIDE',
    'boolean':'DT_BOOL',
    'char16':'DT_CHAR16',
    'datetime':'DT_DATETIME',
    'pragma':'PRAGMA',
    'real32':'DT_REAL32',
    'real64':'DT_REAL64',
    'sint16':'DT_SINT16',
    'sint32':'DT_SINT32',
    'sint64':'DT_SINT64',
    'sint8':'DT_SINT8',
    'string':'DT_STR',
    'uint16':'DT_UINT16',
    'uint32':'DT_UINT32',
    'uint64':'DT_UINT64',
    'uint8':'DT_UINT8',
    'enableoverride':'ENABLEOVERRIDE',
    'false':'FALSE',
    'flavor':'FLAVOR',
    'indication':'INDICATION',
    'instance':'INSTANCE',
    'method':'METHOD',
    'null':'NULL',
    'of':'OF',
    'parameter':'PARAMETER',
    'property':'PROPERTY',
    'qualifier':'QUALIFIER',
    'ref':'REF',
    'reference':'REFERENCE',
    'restricted':'RESTRICTED',
    'schema':'SCHEMA',
    'scope':'SCOPE',
    'tosubclass':'TOSUBCLASS',
    'translatable':'TRANSLATABLE',
    'true':'TRUE',
    }

tokens = reserved.values() + [
        'IDENTIFIER',
        'stringValue',
        'floatValue',
        'charValue',
        'binaryValue',
        'octalValue',
        'decimalValue',
        'hexValue',
    ]

literals = '#(){};[],$:='

# UTF-8 (from Unicode 4.0.0 standard):
# Table 3-6. Well-Formed UTF-8 Byte Sequences Code Points
# 1st Byte 2nd Byte 3rd Byte 4th Byte
# U+0000..U+007F     00..7F
# U+0080..U+07FF     C2..DF   80..BF
# U+0800..U+0FFF     E0       A0..BF   80..BF
# U+1000..U+CFFF     E1..EC   80..BF   80..BF
# U+D000..U+D7FF     ED       80..9F   80..BF
# U+E000..U+FFFF     EE..EF   80..BF   80..BF
# U+10000..U+3FFFF   F0       90..BF   80..BF   80..BF
# U+40000..U+FFFFF   F1..F3   80..BF   80..BF   80..BF
# U+100000..U+10FFFF F4       80..8F   80..BF   80..BF

utf8_2 = r'[\xC2-\xDF][\x80-\xBF]'
utf8_3_1 = r'\xE0[\xA0-\xBF][\x80-\xBF]'
utf8_3_2 = r'[\xE1-\xEC][\x80-\xBF][\x80-\xBF]'
utf8_3_3 = r'\xED[\x80-\x9F][\x80-\xBF]'
utf8_3_4 = r'[\xEE-\xEF][\x80-\xBF][\x80-\xBF]'
utf8_4_1 = r'\xF0[\x90-\xBF][\x80-\xBF][\x80-\xBF]'
utf8_4_2 = r'[\xF1-\xF3][\x80-\xBF][\x80-\xBF][\x80-\xBF]'
utf8_4_3 = r'\xF4[\x80-\x8F][\x80-\xBF][\x80-\xBF]'

utf8Char = r'(%s)|(%s)|(%s)|(%s)|(%s)|(%s)|(%s)|(%s)' % (utf8_2, utf8_3_1,
        utf8_3_2, utf8_3_3, utf8_3_4, utf8_4_1, utf8_4_2, utf8_4_3)

def t_COMMENT(t):
    r'//.*'
    pass

def t_MCOMMENT(t):
    r' /\*(.|\n)*?\*/'
    t.lineno += t.value.count('\n')


t_binaryValue = r'[+-]?[01]+[bB]'
t_octalValue = r'[+-]?0[0-7]+'
t_decimalValue = r'[+-]?([1-9][0-9]*|0)'
t_hexValue = r'[+-]?0[xX][0-9a-fA-F]+'
t_floatValue = r'[+-]?[0-9]*\.[0-9]+([eE][+-]?[0-9]+)?'

simpleEscape = r"""[bfnrt'"\\]"""
hexEscape = r'x[0-9a-fA-F]{1,4}'
escapeSequence = r'[\\]((%s)|(%s))' % (simpleEscape, hexEscape)
cChar = r"[^'\\\n\r]|(%s)" % escapeSequence
sChar = r'[^"\\\n\r]|(%s)' % escapeSequence
charValue = r"'%s'" % cChar

t_stringValue = r'"(%s)*"' % sChar

identifier_re = r'([a-zA-Z_]|(%s))([0-9a-zA-Z_]|(%s))*' % (utf8Char, utf8Char)

@TOKEN(identifier_re)
def t_IDENTIFIER(t):
    t.type = reserved.get(t.value.lower(),'IDENTIFIER') # check for reserved word
    return t

# Define a rule so we can track line numbers
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    t.lexer.linestart = t.lexpos

t_ignore = ' \r\t'

# Error handling rule
def t_error(t):
    msg = "Illegal character '%s' " % t.value[0]
    msg+= "Line %d, col %d" % (t.lineno, find_column(mof, t))
    print msg
    t.lexer.skip(1)

def p_mofSpecification(p):
    """mofSpecification : mofProductionList"""

def p_mofProductionList(p):
    """mofProductionList : empty
                         | mofProductionList mofProduction
                           """

def p_mofProduction(p):
    """mofProduction : compilerDirective
                     | mp_createClass
                     | mp_setQualifier
                     | mp_createInstance
                     """

def p_mp_createClass(p):
    """mp_createClass : classDeclaration
                      | assocDeclaration
                      | indicDeclaration
                      """
    cc = p[1]
    print 'Creating class %s...' % cc.classname
    try:
        cimdb.CreateClass(cc, p.parser.ns)
    except pywbem.CIMError, ce:
        if ce.args[0] != pywbem.CIM_ERR_ALREADY_EXISTS:
            raise
        print 'Class %s already exist.  Modifying...' % cc.classname
        cimdb.ModifyClass(cc, p.parser.ns)

def p_mp_createInstance(p):
    """mp_createInstance : instanceDeclaration"""
    inst = p[1]
    print 'Creating instance of %s.' % inst.classname
    cimdb.CreateInstance(inst)

def p_mp_setQualifier(p):
    """mp_setQualifier : qualifierDeclaration"""
    qualdecl = p[1]
    print 'Setting qualifier %s' % qualdecl.name
    cimdb.SetQualifier(qualdecl, p.parser.ns)

def p_compilerDirective(p): 
    """compilerDirective : '#' PRAGMA pragmaName '(' pragmaParameter ')'"""
    directive = p[3].lower()
    param = p[5]
    if directive == 'include':
        fname = os.path.dirname(p.parser.file) + '/' + param
        print 'Compiling', fname
        f = open(fname, 'r')
        mof = f.read()
        f.close()
        parser = yacc.yacc()
        parser.file = fname
        parser.mof = mof
        lexer = lex.lex()
        lexer.parser = parser
        parser.ns = p.parser.ns
        parser.parse(mof, lexer=lexer)
    elif directive == 'namespace':
        p.parser.ns = param
    
    p[0] = None

def p_pragmaName(p):
    """pragmaName : identifier"""
    p[0] = p[1]

def p_pragmaParameter(p):
    """pragmaParameter : stringValue"""
    p[0] = p[1][1:-1]

def p_classDeclaration(p):
    """classDeclaration : CLASS className '{' classFeatureList '}' ';'
                        | CLASS className superClass '{' classFeatureList '}' ';'
                        | CLASS className alias '{' classFeatureList '}' ';'
                        | CLASS className alias superClass '{' classFeatureList '}' ';'
                        | qualifierList CLASS className '{' classFeatureList '}' ';'
                        | qualifierList CLASS className superClass '{' classFeatureList '}' ';'
                        | qualifierList CLASS className alias '{' classFeatureList '}' ';'
                        | qualifierList CLASS className alias superClass '{' classFeatureList '}' ';'
                        """
    superclass = None
    alias = None
    quals = []
    if isinstance(p[1], basestring): # no class qualifiers
        cname = p[2]
        if p[3][0] == '$': # alias present
            alias = p[3][1:]
            if p[4] == '{': # no superclass
                cfl = p[5]
            else: # superclass
                superclass = p[4]
                cfl = p[6]
        else: # no alias
            if p[3] == '{': # no superclass
                cfl = p[4]
            else: # superclass
                superclass = p[3]
                cfl = p[5]
    else: # class qualifiers
        quals = p[1]
        cname = p[3]
        if p[4][0] == '$': # alias present
            alias = p[4][1:]
            if p[5] == '{': # no superclass
                cfl = p[6]
            else: # superclass
                superclass = p[5]
                cfl = p[7]
        else: # no alias
            if p[4] == '{': # no superclass
                cfl = p[5]
            else: # superclass
                superclass = p[4]
                cfl = p[6]
    quals = dict([(x.name, x) for x in quals])
    methods = {}
    props = {}
    for item in cfl:
        item.class_origin = cname
        if isinstance(item, pywbem.CIMMethod):
            methods[item.name] = item
        else:
            props[item.name] = item
    p[0] = pywbem.CIMClass(cname, properties=props, methods=methods, 
            superclass=superclass, qualifiers=quals)
    # TODO store alias. 

def p_classFeatureList(p):
    """classFeatureList : empty
                        | classFeatureList classFeature
                        """
    if len(p) == 2:
        p[0] = []
    else:
        p[0] = p[1] + [p[2]]

def p_assocDeclaration(p):
    """assocDeclaration : '[' ASSOCIATION qualifierListEmpty ']' CLASS className '{' associationFeatureList '}' ';'
                        | '[' ASSOCIATION qualifierListEmpty ']' CLASS className superClass '{' associationFeatureList '}' ';'
                        | '[' ASSOCIATION qualifierListEmpty ']' CLASS className alias '{' associationFeatureList '}' ';'
                        | '[' ASSOCIATION qualifierListEmpty ']' CLASS className alias superClass '{' associationFeatureList '}' ';'
                        """
    aqual = pywbem.CIMQualifier('ASSOCIATION', True, type='boolean')
    # TODO flavor trash. 
    quals = [aqual] + p[3]
    p[0] = _assoc_or_inic_decl(quals, p)
    
def p_indicDeclaration(p):
    """indicDeclaration : '[' INDICATION qualifierListEmpty ']' CLASS className '{' classFeatureList '}' ';'
                        | '[' INDICATION qualifierListEmpty ']' CLASS className superClass '{' classFeatureList '}' ';'
                        | '[' INDICATION qualifierListEmpty ']' CLASS className alias '{' classFeatureList '}' ';'
                        | '[' INDICATION qualifierListEmpty ']' CLASS className alias superClass '{' classFeatureList '}' ';'
                        """
    iqual = pywbem.CIMQualifier('INDICATION', True, type='boolean')
    # TODO flavor trash. 
    quals = [iqual] + p[3]
    p[0] = _assoc_or_inic_decl(quals, p)

def _assoc_or_indic_decl(quals, p):
    """(refer to grammer rules on p_assocDeclaration and p_indicDeclaration)"""
    superclass = None
    alias = None
    cname = p[6]
    if p[7] == '{':
        cfl = p[8]
    elif p[7][0] == '$': # alias
        alias = p[7][1:]
        if p[8] == '{':
            cfl = p[9]
        else:
            superclass = p[8]
            cfl = p[10]
    else:
        superclass = p[7]
        cfl = p[9]
    props = {}
    methods = {}
    for item in cfl:
        item.class_origin = came
        if isinstance(item, pywbem.CIMMethod):
            methods[item.name] = item
        else:
            props[item.name] = item
    quals = dict([(x.name, x) for x in quals])
    return pywbem.CIMClass(cname, properties=props, methods=methods, 
            superclass=superclass, qualifiers=quals)

def p_qualifierListEmpty(p):
    """qualifierListEmpty : empty
                          | qualifierListEmpty ',' qualifier
                          """
    if len(p) == 2:
        p[0] = []
    else:
        p[0] = p[1] + [p[3]]

def p_associationFeatureList(p):
    """associationFeatureList : empty 
                              | associationFeatureList associationFeature
                              """
    if len(p) == 2:
        p[0] = []
    else:
        p[0] = p[1] + [p[2]]

def p_className(p):
    """className : identifier"""
    p[0] = p[1]

def p_alias(p):
    """alias : AS aliasIdentifier"""
    p[0] = p[2]

def p_aliasIdentifier(p):
    """aliasIdentifier : '$' identifier"""
    p[0] = '$%s' % p[2]

def p_superClass(p):
    """superClass : ':' className"""
    p[0] = p[2]

def p_classFeature(p):
    """classFeature : propertyDeclaration
                    | methodDeclaration
                    | referenceDeclaration
                    """
    p[0] = p[1]

def p_associationFeature(p):
    """associationFeature : classFeature"""
    p[0] = p[1]

def p_qualifierList(p):
    """qualifierList : '[' qualifier qualifierListEmpty ']'"""
    p[0] = [p[2]] + p[3]

def p_qualifier(p): 
    """qualifier : qualifierName
                 | qualifierName ':' flavorList
                 | qualifierName qualifierParameter
                 | qualifierName qualifierParameter ':' flavorList
                 """
    qname = p[1]
    qval = None
    flavorlist = []
    if len(p) == 3:
        qval = p[2]
    elif len(p) == 4:
        flavorlist = p[3]
    elif len(p) == 5:
        qval = p[2]
        flavorlist = p[4]
    qt = _get_qualifier_decl(p.parser.ns, qname)
    if qval is None: 
        qval = qt.value # default value
    propagated = True # 'RESTRICTED' in flavorlist or qt.flavors['RESTRICTED']
    overridable = True # 'ENABLEOVERRIDE' in flavorlist or qt.flavors['ENABLEOVERRIDE']
    if 'DISABLEOVERRIDE' in flavorlist:
        overridable = False
    tosubclass = True # 'TOSUBCLASS' in flavorlist or qt.flavors['TOSUBCLASS']
    toinstance = True # TODO ???
    translatable = True # 'TRANSLATABLE' in flavorlist or qt.flavors['TRANSLATABLE']
    if qval is not None: 
        qval = pywbem.tocimobj(qt.type, qval)
    p[0] = pywbem.CIMQualifier(qname, qval, type=qt.type, 
            propagated=propagated, overridable=overridable, 
            tosubclass=tosubclass, toinstance=toinstance, 
            translatable=translatable)

def p_flavorList(p):
    """flavorList : flavor
                  | flavorList flavor
                  """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[2]]

def p_qualifierParameter(p):
    """qualifierParameter : '(' constantValue ')'
                          | arrayInitializer
                          """
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = p[2]

def p_flavor(p):
    """flavor : ENABLEOVERRIDE
              | DISABLEOVERRIDE
              | RESTRICTED
              | TOSUBCLASS
              | TRANSLATABLE
              """
    p[0] = p[1].upper()

def p_propertyDeclaration(p):
    """propertyDeclaration : propertyDeclaration_1
                           | propertyDeclaration_2
                           | propertyDeclaration_3
                           | propertyDeclaration_4
                           | propertyDeclaration_5
                           | propertyDeclaration_6
                           | propertyDeclaration_7
                           | propertyDeclaration_8
                           """
    p[0] = p[1]

def p_propertyDeclaration_1(p):
    """propertyDeclaration_1 : dataType propertyName ';'"""
    p[0] = pywbem.CIMProperty(p[2], None, type=p[1])

def p_propertyDeclaration_2(p):
    """propertyDeclaration_2 : dataType propertyName defaultValue ';'"""
    p[0] = pywbem.CIMProperty(p[2], p[3], type=p[1])

def p_propertyDeclaration_3(p):
    """propertyDeclaration_3 : dataType propertyName array ';'"""
    p[0] = pywbem.CIMProperty(p[2], None, type=p[1], is_array=True, 
            array_size=p[3])

def p_propertyDeclaration_4(p):
    """propertyDeclaration_4 : dataType propertyName array defaultValue ';'"""
    p[0] = pywbem.CIMProperty(p[2], p[4], type=p[1], is_array=True, 
            array_size=p[3])

def p_propertyDeclaration_5(p):
    """propertyDeclaration_5 : qualifierList dataType propertyName ';'"""
    quals = dict([(x.name, x) for x in p[1]])
    p[0] = pywbem.CIMProperty(p[3], None, type=p[2], qualifiers=quals)

def p_propertyDeclaration_6(p):
    """propertyDeclaration_6 : qualifierList dataType propertyName defaultValue ';'"""
    quals = dict([(x.name, x) for x in p[1]])
    p[0] = pywbem.CIMProperty(p[3], p[4], type=p[2], qualifiers=quals)

def p_propertyDeclaration_7(p):
    """propertyDeclaration_7 : qualifierList dataType propertyName array ';'"""
    quals = dict([(x.name, x) for x in p[1]])
    p[0] = pywbem.CIMProperty(p[3], None, type=p[2], qualifiers=quals,
            is_array=True, array_size=p[4])

def p_propertyDeclaration_8(p):
    """propertyDeclaration_8 : qualifierList dataType propertyName array defaultValue ';'"""
    quals = dict([(x.name, x) for x in p[1]])
    p[0] = pywbem.CIMProperty(p[3], p[5], type=p[2], qualifiers=quals,
            is_array=True, array_size=p[4])

def p_referenceDeclaration(p):
    """referenceDeclaration : objectRef referenceName ';'
                            | objectRef referenceName defaultValue ';'
                            | qualifierList objectRef referenceName ';'
                            | qualifierList objectRef referenceName defaultValue ';'
                            """
    quals = []
    dv = None
    if isinstance(p[1], list): # qualifiers
        quals = p[1]
        cname = p[2]
        pname = p[3]
        if len(p) == 6:
            dv = p[4]
    else:
        cname = p[1]
        pname = p[2]
        if len(p) == 5:
            dv = p[3]
    quals = dict([(x.name, x) for x in quals])
    p[0] = pywbem.CIMProperty(pname, dv, type='ref', reference_class=cname, 
            qualifiers=quals)

def p_methodDeclaration(p):
    """methodDeclaration : dataType methodName '(' ')' ';'
                         | dataType methodName '(' parameterList ')' ';'
                         | qualifierList dataType methodName '(' ')' ';'
                         | qualifierList dataType methodName '(' parameterList ')' ';'
                         """
    paramlist = []
    quals = []
    if isinstance(p[1], basestring): # no quals
        dt = p[1]
        mname = p[2]
        if p[4] != ')':
            paramlist = p[4]
    else: # quals present
        quals = p[1]
        dt = p[2]
        mname = p[3]
        if p[5] != ')':
            paramlist = p[5]
    params = dict([(param.name, param) for param in paramlist])
    quals = dict([(q.name, q) for q in quals])
    p[0] = pywbem.CIMMethod(mname, return_type=dt, parameters=params, 
            qualifiers=quals)
    # note: class_origin is set when adding method to class. 
    # TODO what to do with propagated? 

def p_propertyName(p):
    """propertyName : identifier"""
    p[0] = p[1]

def p_referenceName(p):
    """referenceName : identifier"""
    p[0] = p[1]

def p_methodName(p):
    """methodName : identifier"""
    p[0] = p[1]

def p_dataType(p):
    """dataType : DT_UINT8
                | DT_SINT8
                | DT_UINT16
                | DT_SINT16
                | DT_UINT32
                | DT_SINT32
                | DT_UINT64
                | DT_SINT64
                | DT_REAL32
                | DT_REAL64
                | DT_CHAR16
                | DT_STR
                | DT_BOOL
                | DT_DATETIME
                """
    p[0] = p[1].lower()

def p_objectRef(p):
    """objectRef : className REF"""
    p[0] = p[1]

def p_parameterList(p):
    """parameterList : parameter
                     | parameterList ',' parameter
                     """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]

def p_parameter(p):
    """parameter : parameter_1
                 | parameter_2
                 | parameter_3
                 | parameter_4
                 """
    p[0] = p[1]

def p_parameter_1(p):
    """parameter_1 : dataType parameterName
                   | dataType parameterName array
                   """
    args = {}
    if len(p) == 4:
        args['is_array'] = True
        args['array_size'] = p[3]
    p[0] = pywbem.CIMParameter(p[2], p[1], **args)

def p_parameter_2(p):
    """parameter_2 : qualifierList dataType parameterName
                   | qualifierList dataType parameterName array
                   """
    args = {}
    if len(p) == 5:
        args['is_array'] = True
        args['array_size'] = p[4]
    quals = dict([(x.name, x) for x in p[1]])
    p[0] = pywbem.CIMParameter(p[3], p[2], qualifiers=quals, **args)

def p_parameter_3(p):
    """parameter_3 : objectRef parameterName
                   | objectRef parameterName array
                   """
    args = {}
    if len(p) == 4:
        args['is_array'] = True
        args['array_size'] = p[3]
    p[0] = pywbem.CIMParameter(p[2], 'ref', reference_class=p[1], **args)

def p_parameter_4(p):
    """parameter_4 : qualifierList objectRef parameterName
                   | qualifierList objectRef parameterName array
                   """
    args = {}
    if len(p) == 5:
        args['is_array'] = True
        args['array_size'] = p[4]
    quals = dict([(x.name, x) for x in p[1]])
    p[0] = pywbem.CIMParameter(p[3], 'ref', qualifiers=quals, 
                reference_class=p[1], **args)

def p_parameterName(p):
    """parameterName : identifier"""
    p[0] = p[1]

def p_array(p):
    """array : '[' ']'
             | '[' integerValue ']'
             """
    if len(p) == 3:
        p[0] = None
    else:
        p[0] = p[2]

def p_defaultValue(p):
    """defaultValue : '=' initializer"""
    p[0] = p[2]

def p_initializer(p):
    """initializer : constantValue
                   | arrayInitializer
                   | referenceInitializer
                   """
    p[0] = p[1]

def p_arrayInitializer(p):
    """arrayInitializer : '{' constantValueList '}'
                        | '{' '}'
                        """
    if len(p) == 3:
        p[0] = []
    else:
        p[0] = p[2]

def p_constantValueList(p):
    """constantValueList : constantValue
                         | constantValueList ',' constantValue
                         """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]

def p_stringValueList(p):
    """stringValueList : stringValue
                       | stringValueList stringValue
                       """
    if len(p) == 2:
        p[0] = p[1][1:-1]
    else:
        p[0] = p[1] + p[2][1:-1]


def p_constantValue(p):
    """constantValue : integerValue
                     | floatValue
                     | charValue
                     | stringValueList
                     | booleanValue
                     | nullValue
                     """
    p[0] = p[1]

def p_integerValue(p):
    """integerValue : binaryValue
                    | octalValue
                    | decimalValue
                    | hexValue
                    """
    p[0] = int(p[1])
    # TODO deal with non-decimal values. 

def p_referenceInitializer(p):
    """referenceInitializer : objectHandle
                            | aliasIdentifier
                            """
    p[0] = p[1]

def p_objectHandle(p):
    """objectHandle : identifier"""
    p[0] = p[1]

def p_qualifierDeclaration(p):
    """qualifierDeclaration : QUALIFIER qualifierName qualifierType scope ';'
                            | QUALIFIER qualifierName qualifierType scope defaultFlavor ';'
                            """
    qualtype = p[3]
    dt, is_array, array_size, value = qualtype
    qualname = p[2]
    scopes = p[4]
    if len(p) == 5:
        flavors = {}
    else:
        flavors = p[5]
    p[0] = pywbem.CIMQualifierDeclaration(qualname, dt, value=value, 
                    is_array=is_array, array_size=array_size, 
                    scopes=scopes, flavors=flavors)


def p_qualifierName(p):
    """qualifierName : identifier
                     | ASSOCIATION
                     | INDICATION
                     """
    p[0] = p[1]

def p_qualifierType(p):
    """qualifierType : qualifierType_1
                     | qualifierType_2
                     """
    p[0] = p[1]

def p_qualifierType_1(p):
    """qualifierType_1 : ':' dataType array
                       | ':' dataType array defaultValue
                       """
    dv = None
    if len(p) == 5:
        dv = p[4]
    p[0] = (p[2], True, p[3], dv)

def p_qualifierType_2(p):
    """qualifierType_2 : ':' dataType 
                       | ':' dataType defaultValue
                       """
    dv = None
    if len(p) == 4:
        dv = p[3]
    p[0] = (p[2], False, None, dv)

def p_scope(p):
    """scope : ',' SCOPE '(' metaElementList ')'"""
    slist = p[4]
    scopes = {}
    for i in ('SCHEMA',
              'CLASS',
              'ASSOCIATION',
              'INDICATION',
              'QUALIFIER',
              'PROPERTY',
              'REFERENCE',
              'METHOD',
              'PARAMETER',
              'ANY'):
        scopes[i] = i in slist
    p[0] = scopes

def p_metaElementList(p):
    """metaElementList : metaElement
                       | metaElementList ',' metaElement
                       """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]

def p_metaElement(p):
    """metaElement : SCHEMA
                   | CLASS
                   | ASSOCIATION
                   | INDICATION
                   | QUALIFIER
                   | PROPERTY
                   | REFERENCE
                   | METHOD
                   | PARAMETER
                   | ANY
                   """
    p[0] = p[1].upper()

def p_defaultFlavor(p):
    """defaultFlavor : ',' FLAVOR '(' flavorListWithComma ')'"""
    flist = p[4]
    flavors = {'ENABLEOVERRIDE':True,
               'TOSUBCLASS':True,
               'DISABLEOVERRIDE':False,
               'RESTRICTED':False,
               'TRANSLATABLE':False}
    for i in flist:
        flavors[i] = True
    p[0] = flavors


def p_flavorListWithComma(p):
    """flavorListWithComma : flavor
                           | flavorListWithComma ',' flavor
                           """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]

def p_instanceDeclaration(p):
    """instanceDeclaration : INSTANCE OF className '{' valueInitializerList '}' ';'
                           | INSTANCE OF className alias '{' valueInitializerList '}' ';'
                           | qualifierList INSTANCE OF className '{' valueInitializerList '}' ';'
                           | qualifierList INSTANCE OF className alias '{' valueInitializerList '}' ';'
                           """
    alias = None
    quals = {}
    if isinstance(p[1], basestring): # no qualifiers
        cname = p[3]
        if p[4] == '{':
            props = p[5]
        else:
            props = p[6]
            alias = p[4]
    else:
        cname = p[4]
        #quals = p[1] # qualifiers on instances are deprecated -- rightly so. 
        if p[5] == '{':
            props = p[6]
        else:
            props = p[7]
            alias = p[5]

    cc = cimdb.GetClass(cname, p.parser.ns, LocalOnly=False, 
            IncludeQualifiers=False, IncludeClassOrigin=False)
    path = pywbem.CIMInstanceName(cname, namespace=p.parser.ns)
    inst = pywbem.CIMInstance(cname, properties=cc.properties, 
            qualifiers=quals, path=path)
    for prop in props: 
        cprop = inst.properties[prop.name]
        cprop.value = prop.value
        cprop.reference_class = prop.reference_class

    # TODO store alias
    p[0] = inst 

def p_valueInitializerList(p):
    """valueInitializerList : valueInitializer
                            | valueInitializerList valueInitializer
                            """
    if len(p) == 2:
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[2]]
    

def p_valueInitializer(p):
    """valueInitializer : identifier defaultValue ';'
                        | qualifierList identifier defaultValue ';'
                        """
    if len(p) == 4:
        id = p[1]
        val = p[2]
        quals = []
    else:
        quals = p[1]
        id = p[2]
        quals = p[3]
    p[0] = (quals, id, val)

def p_booleanValue(p):
    """booleanValue : FALSE
                    | TRUE
                    """
    p[0] = p[1].lower() == 'true'

def p_nullValue(p):
    """nullValue : NULL"""
    p[0] = None

def p_identifier(p):
    """identifier : IDENTIFIER
                  | ANY
                  | AS
                  | CLASS
                  | DISABLEOVERRIDE
                  | dataType 
                  | ENABLEOVERRIDE
                  | FLAVOR
                  | INSTANCE
                  | METHOD
                  | OF
                  | PARAMETER
                  | PRAGMA
                  | PROPERTY
                  | QUALIFIER
                  | REFERENCE
                  | RESTRICTED
                  | SCHEMA
                  | SCOPE
                  | TOSUBCLASS
                  | TRANSLATABLE
                  """
                  #| ASSOCIATION
                  #| INDICATION
    p[0] = p[1]

def p_empty(p):
    'empty :'
    pass

def p_error(p):
    print 'Syntax Error in input!'
    print p
    print 'column: ', find_column(p.lexer.parser.mof, p)

def find_column(input, token):
    i = token.lexpos
    while i > 0:
        if input[i] == '\n':
            break
        i-= 1
    column = (token.lexpos - i)+1
    return column

def _get_qualifier_decl(ns, qname):
    return cimdb.GetQualifier(qname, ns)

if __name__ == '__main__':
    #lex.runmain()
    #sys.exit(0)
    global mof
    lexer = lex.lex()
    parser = yacc.yacc()
    fname = sys.argv[1]
    f = open(fname, 'r')
    parser.file = fname
    lexer.parser = parser
    parser.mof = f.read() 
    f.close()
    parser.ns = 'mofcomp'
    nss = [x for x in cimdb.Namespaces()] 
    if parser.ns not in nss:
        cimdb.CreateNamespace(parser.ns)
    parser.parse(parser.mof, lexer=lexer)
    sys.exit(0)

    for w in os.walk('/usr/share/mof'):
        for f in w[2]:
            if not f.endswith('.mof'):
                continue
            file = '%s/%s' % (w[0], f)
            print 'Parsing', file
            f = open(file, 'r')
            mof = f.read()
            f.close()
            parser.parse(mof, lexer=lexer)


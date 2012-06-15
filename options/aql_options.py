import operator
import itertools
import weakref

from aql_utils import toSequence
from aql_option_types import OptionType, ListOptionType
from aql_option_value import OptionValue, AddValue, SubValue, SetValue, Operation, ConditionalValue, Condition
from aql_errors import InvalidOptions, InvalidOptionValueType

#//===========================================================================//

def   _evalValue( other, options, context = None ):
  if isinstance( other, OptionValueProxy ):
    if other.options is not options:
      return other.value()
    
    return other.value( context )
  
  elif isinstance( other, OptionValue ):
    return options.value( other, context )
  
  return other

#//===========================================================================//

class OptionValueProxy (object):
  
  __slots__ = (
    'option_value',
    'options',
  )
  
  def   __init__( self, option_value, options ):
    self.option_value = option_value
    self.options = options
  
  #//-------------------------------------------------------//
  
  def   value( self, context = None ):
    return self.options.value( self.option_value, context )
  
  #//-------------------------------------------------------//
  
  def   __iadd__( self, other ):
    self.options._appendValue( self.option_value, other, AddValue )
    return self
  
  #//-------------------------------------------------------//
  
  def   __isub__( self, other ):
    self.options._appendValue( self.option_value, other, SubValue )
    return self
  
  #//-------------------------------------------------------//
  
  def   set( self, value, operation_type = SetValue, condition = None ):
    self.options._appendValue( self.option_value, value, operation_type, condition )
  
  #//-------------------------------------------------------//
  
  def   cmp( self, cmp_operator, other, context = None ):
    value = self.value( context )
    other = _evalValue( other, self.options, context )
    
    return cmp_operator( value, other )
  
  #//-------------------------------------------------------//
  
  def   __eq__( self, other ):
    return self.cmp( operator.eq, other )
  def   __ne__( self, other ):
    return self.cmp( operator.ne, other )
  def   __lt__( self, other ):
    return self.cmp( operator.lt, other )
  def   __le__( self, other ):
    return self.cmp( operator.le, other )
  def   __gt__( self, other ):
    return self.cmp( operator.gt, other )
  def   __ge__( self, other ):
    return self.cmp( operator.ge, other )
  
  #//-------------------------------------------------------//
  
  def   has( self, other, context = None ):
    return self.cmp( operator.contains, other )
  
  #//-------------------------------------------------------//
  
  def   optionType( self ):
    return self.option_value.option_type
  
#//===========================================================================//

class ConditionGeneratorHelper( object ):
  
  def     __init__( self, name, options, condition  ):
    self.name  = name
    self.options  = options
    self.condition  = condition
  
  #//-------------------------------------------------------//
  
  @staticmethod
  def   __hasAny( seq, values ):
    for value in toSequence( values ):
      if value in seq:
        return True
    return False
  
  #//-------------------------------------------------------//
  
  @staticmethod
  def   __hasAll( seq, values ):
    for value in toSequence( values ):
      if value not in seq:
        return False
    return True
  
  #//-------------------------------------------------------//
  
  @staticmethod
  def   __oneOf( value, values ):
    for v in values:
      if value == v:
        return True
    return False
  
  #//-------------------------------------------------------//
  
  @staticmethod
  def   __cmpValue( options, context, cmp_operator, option_value_proxy, other ):
    return option_value_proxy.cmp( cmp_operator, other, context )
  
  #//-------------------------------------------------------//
  
  @staticmethod
  def __makeCmpCondition( condition, cmp_operator, option_value_proxy, other ):
    return Condition( condition, ConditionGeneratorHelper.__cmpValue, cmp_operator, option_value_proxy, other )
  
  #//-------------------------------------------------------//
  
  def   cmp( self, cmp_operator, other ):
    option_value_proxy = self.options[ self.name ]
    condition = self.__makeCmpCondition( self.condition, cmp_operator, option_value_proxy, other )
    return ConditionGenerator( self.options, condition )
  
  def   __getitem__( self, other ):
    return self.cmp( operator.eq, other )
  def   eq( self, other ):
    return self.cmp( operator.eq, other )
  def   ne( self, other ):
    return self.cmp( operator.ne, other )
  def   gt( self, other ):
    return self.cmp( operator.gt, other )
  def   ge( self, other ):
    return self.cmp( operator.ge, other )
  def   lt( self, other ):
    return self.cmp( operator.lt, other )
  def   le( self, other ):
    return self.cmp( operator.le, other )
  def   has( self, value ):
    return self.cmp( operator.contains, value )
  def   hasAny( self, values ):
    return self.cmp( self.__hasAny, values )
  def   hasAll( self, values ):
    return self.cmp( self.__hasAll, values )
  def   oneOf( self, values ):
    return self.cmp( self.__oneOf, values )
  
  #//-------------------------------------------------------//
  
  def   __iadd__( self, value ):
    return self.options._makeCondValue( value, AddValue, self.condition )
  
  #//-------------------------------------------------------//
  
  def   __isub__( self, value ):
    return self.options._makeCondValue( value, SubValue, self.condition )

#//===========================================================================//

class ConditionGenerator( object ):
  
  def     __init__( self, options, condition = None ):
    self.__dict__['__options']  = options
    self.__dict__['__condition']  = condition
  
  #//-------------------------------------------------------//
  
  def   __getattr__( self, name ):
    return ConditionGeneratorHelper( name, self.__dict__['__options'], self.__dict__['__condition'])
  
  #//-------------------------------------------------------//
  
  def     __setattr__(self, name, value):
    self.__dict__['__options'].appendValue( name, value, SetValue, self.__dict__['__condition'] )
  
#//===========================================================================//

class Options (object):
  
  def     __init__( self, parent = None ):
    self.__dict__['__parent']       = parent
    self.__dict__['__cache']        = {}
    self.__dict__['__opt_values']   = {}
    self.__dict__['__children']     = []
    
    if parent is not None:
      parent.__dict__['__children'].append( weakref.proxy( self ) )
  
  #//-------------------------------------------------------//
  
  def   _makeCondValue( self, value, operation_type = None, condition = None ):
    if isinstance( value, Operation ):
      return ConditionalValue( value, condition )
    
    elif isinstance( value, ConditionalValue ):
      return value
    
    if operation_type is None:
      raise InvalidOptionValueType( value )
    
    if isinstance( value, OptionValue ):
      raise InvalidOptionValueType( value )
    
    if isinstance( value, OptionValueProxy ):
      if value.options is not self:
        raise InvalidOptionValueType( value )
      
      value = value.option_value
    
    return ConditionalValue( operation_type( value ), condition )
  
  #//-------------------------------------------------------//
  
  def   __set_value( self, name, value, operation_type = SetValue ):
    
    opt_value, from_parent = self._get_value( name )
    
    if isinstance( value, OptionType ):
      if opt_value is None:
        self.__dict__['__opt_values'][ name ] = OptionValue( value )
        return
      else:
        raise InvalidOptionValueType( value )
      
    if isinstance( value, OptionValueProxy ):
      if value.options is not self:
        raise InvalidOptionValueType( value )
      
      if opt_value is value.option_value:
        return
      
      if opt_value is None:
        self.__dict__['__opt_values'][ name ] = value.option_value
        return
      
      value = ConditionalValue( operation_type( value.option_value ) )
    
    else:
      if opt_value is None:
        raise InvalidOptionValueType( value )
      
      value = self._makeCondValue( value, operation_type )
    
    if from_parent:
      opt_value = opt_value.copy()
      self.__dict__['__opt_values'][ name ] = opt_value
    
    opt_value.appendValue( value )
  
  #//-------------------------------------------------------//
  
  def   __setattr__( self, name, value ):
    self.__set_value( name, value )
    self.clearCache()
  
  #//-------------------------------------------------------//
  
  def   __setitem__( self, name, value ):
    self.__setattr__( name, value )
  
  #//-------------------------------------------------------//
  
  def   _get_value( self, name ):
    try:
      return (self.__dict__['__opt_values'][ name ], False)
    except KeyError as e:
      try:
        return ( self.__dict__['__parent']._get_value( name )[0], True )
      except AttributeError:
        return (None, False)
  
  #//-------------------------------------------------------//
  
  def   __getattr__( self, name ):
    opt_value = self._get_value( name )[0]
    if opt_value is None:
      raise AttributeError( name )
    
    return OptionValueProxy( opt_value, self )
  
  #//-------------------------------------------------------//
  
  def   __getitem__( self, name ):
    return self.__getattr__( name )
  
  #//-------------------------------------------------------//
  
  def   __contains__( self, name ):
    return self._get_value( name )[0] is None
  
  #//-------------------------------------------------------//
  
  def   __iter__( self ):
    return iter(self.keys())
  
  #//-------------------------------------------------------//
  
  def   keys( self ):
    names = set( self.__dict__['__opt_values'] )
    parent = self.__dict__['__parent']
    if parent:
      names.update( parent.keys() )
    
    return names
  
  #//-------------------------------------------------------//
  
  def   items( self ):
    for name in self.keys():
      yield ( name, self._get_value( name )[0] )
  
  #//-------------------------------------------------------//
  
  def   __nonzero__( self ):
    return bool(self.__dict__['__opt_values']) or bool(self.__dict__['__parent'])
  
  def   __bool__( self ):
    return bool(self.__dict__['__opt_values']) or bool(self.__dict__['__parent'])
  
  #//-------------------------------------------------------//

  def     update( self, other ):
    if not other:
      return
    
    self.clearCache()
    
    for name, value in other.items():
      try:
        self.__set_value( name, value, UpdateValue )
      except KeyError:
        pass
  
  #//-------------------------------------------------------//
  
  def     __iadd__(self, other ):
    self.update( other )
    return self

  #//-------------------------------------------------------//

  def     override( self ):
    return Options( self )
  
  #//-------------------------------------------------------//
  
  def     copy( self ):
    
    val_names = {}
    for name, opt_value in self.items():
      val_names.setdefault( opt_value, [] ).append( name )
    
    other = Options()
    
    for opt_value, names in val_names.items():
      new_opt_value = OptionValueProxy( opt_value.copy(), other )
      for name in names:
        setattr( other, name, new_opt_value )
    
    return other
  
  #//-------------------------------------------------------//
  
  def   value( self, option_value, context = None ):
    try:
      value = self.__dict__['__cache'][ id(option_value) ]
    except KeyError:
      value = option_value.value( self, context )
      self.__dict__['__cache'][ id(option_value) ] = value
    
    return value
  
  #//-------------------------------------------------------//
  
  def   appendValue( self, name, value, operation_type = None, condition = None ):
    option_value = getattr( self, name ).option_value
    self._appendValue( option_value, value, operation_type, condition )
  
  #//-------------------------------------------------------//
  
  def   _appendValue( self, option_value, value, operation_type = None, condition = None ):
    value = self._makeCondValue( value, operation_type, condition )
    self.clearCache()
    option_value.appendValue( value )
  
  #//-------------------------------------------------------//
  
  def   clearCache( self ):
    self.__dict__['__cache'].clear()
    
    for child in self.__dict__['__children']:
      try:
        child.clearCache()
      except ReferenceError:
        pass
  
  #//-------------------------------------------------------//
  
  def   If( self ):
    return ConditionGenerator( self )

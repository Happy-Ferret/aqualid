import hashlib

from aql_value import Value, NoContent
from aql_depends_value import DependsValue
from aql_logging import logError
from aql_utils import toSequence

class Node (object):
  
  __slots__ = \
  (
    'builder',
    'source_nodes',
    'source_values',
    'dep_nodes',
    'dep_values',
    
    'idep_values',
    'target_values',
    'itarget_values',
    
    'name',
    'long_name',
    'targets_name',
    'itargets_name',
    'deps_name',
    'ideps_name',
    
    'sources_value',
    'deps_value',
  )
  
  #//-------------------------------------------------------//
  
  def   __init__( self, builder, sources ):
    
    self.builder = builder
    self.source_nodes, self.source_values = self.__getSourceNodes( sources )
    self.dep_values = []
    self.dep_nodes = set()
  
  #//=======================================================//
  
  def   __getSourceNodes( self, sources ):
    
    source_nodes = set()
    source_values = []
    
    source_nodes_append = source_nodes.add
    source_values_append = source_values.append
    
    for source in toSequence( sources ):
      if isinstance(source, Node):
        source_nodes_append( source )
      elif isinstance(source, Value):
        source_values_append( source )
      else:
        raise Exception( "Unknown source type: %s" % type(source) )
    
    return source_nodes, source_values
    
  #//=======================================================//
  
  def   __getLongName( self ):
    names = []
    names_append = names.append
    names_append( self.builder.long_name )
    
    for source in self.source_nodes:
      names += source.long_name
    
    for source in self.source_values:
      names_append( source.name )
    
    names.sort()
    
    return names

  #//=======================================================//
  
  def   __getNames( self ):
     chcksum = hashlib.md5()
     
     for name in self.long_name:
       chcksum.update( name.encode() )
     
     name = chcksum.digest()
     chcksum.update( b'target_values' )
     targets_name = chcksum.digest()
     
     chcksum.update( b'itarget_values' )
     itargets_name = chcksum.digest()
     
     chcksum.update( b'dep_values' )
     deps_name = chcksum.digest()
     
     chcksum.update( b'idep_values' )
     ideps_name = chcksum.digest()
     
     return name, targets_name, itargets_name, deps_name, ideps_name
  
  #//=======================================================//
  
  def   __sourcesValue( self ):
    source_values = list(self.source_values)
    
    for node in self.source_nodes:
      source_values += node.target_values
    
    return DependsValue( self.name, source_values )
  
  #//=======================================================//
  
  def   __depsValue( self ):
    dep_values = list(self.dep_values)
    
    for node in self.dep_nodes:
      dep_values += node.target_values
    
    dep_values += self.builder.values()
    
    return DependsValue( self.deps_name, dep_values )
  
  #//=======================================================//
  
  def   __getattr__( self, attr ):
    if attr in ('name', 'targets_name', 'itargets_name', 'deps_name', 'ideps_name'):
      self.name, self.targets_name, self.itargets_name, self.deps_name, self.ideps_name = self.__getNames()
      return getattr(self, attr)
    
    elif attr == 'long_name':
      long_name = self.__getLongName()
      self.long_name = long_name
      return long_name
    
    elif attr == 'sources_value':
      self.sources_value = self.__sourcesValue()
      return self.sources_value
    
    elif attr == 'deps_value':
      self.deps_value = self.__depsValue()
      return self.deps_value
    
    raise AttributeError("Unknown attribute: '%s'" % str(attr) )
  
  #//=======================================================//
  
  def   __save( self, vfile ):
    
    values = []
    values += self.source_values
    values += self.dep_values
    values += self.builder.values()
    values += self.idep_values
    values += self.target_values
    values += self.itarget_values
    
    values.append( self.sources_value )
    values.append( self.deps_value )
    values.append( DependsValue( self.ideps_name,     self.idep_values )    )
    values.append( DependsValue( self.targets_name,   self.target_values )  )
    values.append( DependsValue( self.itargets_name,  self.itarget_values ) )
    
    vfile.addValues( values )
  
  #//=======================================================//
  
  def   build( self, vfile ):
    
    self.target_values, self.itarget_values, self.idep_values = self.builder.build( self )
    
    self.__save( vfile )
  
  #//=======================================================//
  
  def   actual( self, vfile ):
    sources_value = self.sources_value
    deps_value    = self.deps_value
    
    targets_value   = DependsValue( self.targets_name   )
    itargets_value  = DependsValue( self.itargets_name  )
    ideps_value     = DependsValue( self.ideps_name     )
    
    values = [ sources_value, deps_value, targets_value, itargets_value, ideps_value ]
    values = vfile.findValues( values )
    
    if sources_value != values.pop(0):
      return False
    
    if deps_value != values.pop(0):
      return False
    
    for value in values:
      if not value.actual():
        return False
    
    targets_value, itargets_value, ideps_value = values
    
    self.target_values  = targets_value.content
    self.itarget_values = itargets_value.content
    self.idep_values    = ideps_value.content
    
    return True
  
  #//=======================================================//
  
  def   sources(self):
    return self.sources_value.content
  
  #//=======================================================//
  
  @staticmethod
  def   __removeValues( values ):
    for value in values:
      value.remove()
  
  #//=======================================================//
  
  def   clear( self, vfile ):
    
    values = [ DependsValue( self.targets_name  ), DependsValue( self.itargets_name  ) ]
    
    targets_value, itargets_value = vfile.findValues( values )
    target_values = targets_value.content
    itarget_values = itargets_value.content
    
    if itarget_values or target_values:
      if isinstance( target_values, NoContent ):
        target_values = None
      
      if isinstance( itarget_values, NoContent ):
        itarget_values = None
      
      self.builder.clear( self, target_values, itarget_values )
  
  #//=======================================================//
  
  def   targets( self, vfile ):
    try:
      return self.target_values
    except AttributeError:
      targets_value   = DependsValue( self.targets_name  )
      
      target_values = vfile.findValues( [ targets_value ] )[0].content
      if isinstance( target_values, NoContent ):
        return None
      
      return target_values
  
  #//=======================================================//
  
  def   sideEffects( self, vfile ):
    try:
      return self.itarget_values
    except AttributeError:
      itargets_value = DependsValue( self.itargets_name )
      
      value = vfile.findValues( [ itargets_value ] )[0]
      return value.content
  
  #//=======================================================//
  
  def   addDeps( self, deps ):
    
    append_node = self.dep_nodes.add
    append_value = self.dep_values.append
    
    for dep in toSequence( deps ):
      if isinstance(dep, Node):
        append_node( dep )
      elif isinstance(dep, Value):
        append_value( dep )
      else:
        raise Exception( "Unknown dependency type: %s" % type(dep) )
  
  #//-------------------------------------------------------//
  
  def   __str__(self):
    return str( self.long_name )
  
  #//-------------------------------------------------------//
  
  def   __repr__(self):
    return str( self.long_name )

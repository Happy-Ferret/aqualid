
# Copyright (c) 2011-2015 The developers of Aqualid project
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
# associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute,
# sublicense, and/or sell copies of the Software, and to permit persons to whom
# the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or
# substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE
# AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

__all__ = (
  'Node', 'BatchNode',
  'NodeFilter', 'NodeDirNameFilter', 'NodeBaseNameFilter',
)

import os
import operator

from aql.utils import simpleObjectSignature, dumpSimpleObject, newHash, Chdir, eventStatus, logDebug, logInfo
from aql.util_types import toSequence, isString, FilePath, AqlException

from aql.entity import EntityBase, FileEntityBase, SimpleEntity, pickleable

#//===========================================================================//

class   ErrorNodeDependencyInvalid( AqlException ):
  def   __init__( self, dep ):
    msg = "Invalid node dependency: %s" % (dep,)
    super(ErrorNodeDependencyInvalid, self).__init__( msg )

class   ErrorNodeSplitUnknownSource( AqlException ):
  def   __init__( self, node, entity ):
    msg = "Node '%s' can't be split to unknown source entity: %s" % (node.getBuildStr( brief = False ), entity )
    super(ErrorNodeSplitUnknownSource, self).__init__( msg )
    
class   ErrorNoTargets( AttributeError ):
  def   __init__( self, node ):
    msg = "Node targets are not built or set yet: %s" % (node,)
    super(ErrorNoTargets, self).__init__( msg )

class   ErrorNoSrcTargets( AqlException ):
  def   __init__( self, node, src_entity ):
    msg = "Source '%s' targets are not built or set yet: %s" % (src_entity.get(), node)
    super(ErrorNoSrcTargets, self).__init__( msg )

class   ErrorUnactualEntity( AqlException ):
  def   __init__( self, entity ):
    msg = "Target entity is not actual: %s (%s)" % (entity.name, type(entity))
    super(ErrorUnactualEntity, self).__init__( msg )

class   ErrorNodeUnknownSource( AqlException ):
  def   __init__( self, src_entity ):
    msg = "Unknown source entity: %s (%s)" % (src_entity, type(src_entity))
    super(ErrorNodeUnknownSource, self).__init__( msg )

#//===========================================================================//

@eventStatus
def   eventNodeStaleReason( brief, reason ):
  msg = reason.getDescription( brief )
  logDebug( msg )

#//===========================================================================//

class NodeStaleReason (object):
  __slots__ = (
      'code',
      'entity',
      'builder',
      'sources',
      'targets',
  )
  
  ACTUAL, \
  NO_SIGNATURE, \
  NEW, \
  SIGNATURE_CHANGED, \
  IMPLICIT_DEP_CHANGED, \
  NO_TARGETS, \
  TARGET_CHANGED, \
  FORCE_REBUILD, \
    = range(8)
  
  #//-------------------------------------------------------//
  
  def   __init__( self, builder, sources, targets ):
    self.builder = builder
    self.sources = sources
    self.targets = targets
    self.code = self.ACTUAL
    self.entity = None
  
  #//-------------------------------------------------------//
  
  def   _set(self, code, entity = None ):
    self.code = code
    self.entity = entity
    
    eventNodeStaleReason( self )
  
  #//-------------------------------------------------------//
  
  def   setNoSignature( self, NO_SIGNATURE = NO_SIGNATURE ):
    self._set( NO_SIGNATURE )
  
  def   setNew( self, NEW = NEW ):
    self._set( NEW )
      
  def   setSignatureChanged( self, SIGNATURE_CHANGED = SIGNATURE_CHANGED ):
    self._set( SIGNATURE_CHANGED )
  
  def   setImplicitDepChanged( self, entity = None, IMPLICIT_DEP_CHANGED = IMPLICIT_DEP_CHANGED ):
    self._set( IMPLICIT_DEP_CHANGED, entity )
  
  def   setNoTargets( self, NO_TARGETS = NO_TARGETS):
    self._set( NO_TARGETS )
  
  def   setTargetChanged( self, entity, TARGET_CHANGED = TARGET_CHANGED ):
    self._set( TARGET_CHANGED, entity )
  
  def   setForceRebuild( self, FORCE_REBUILD = FORCE_REBUILD ):
    self._set( FORCE_REBUILD )
  
  #//-------------------------------------------------------//
  
  def   getNodeName( self, brief ):
    name = self.builder.getTraceName( brief )
    return _getBuildStr( [ name, self.sources, self.targets ], brief )
  
  #//-------------------------------------------------------//
  
  def   getDescription( self, brief = True ):
    
    node_name = self.getNodeName( brief )
    code = self.code
    
    if code == NodeStaleReason.NO_SIGNATURE:
      msg = "Node`s is marked to rebuild always, rebuilding the node: %s" % node_name
    
    elif code == NodeStaleReason.SIGNATURE_CHANGED:
      msg = "Node`s signature has been changed (sources, builder parameters or dependencies were changed), rebuilding the node: %s" % node_name
    
    elif code == NodeStaleReason.NEW:
      msg = "Node's previous state has not been found, building the new node: %s" % node_name
      # msg += "\nbuilder sig: %s" % (self.builder.signature)
      # msg += "\nsources sig: %s" % ([ src.signature for src in self.sources], )
    
    elif code == NodeStaleReason.IMPLICIT_DEP_CHANGED:
      dep = "'%s'" % self.entity if self.entity else ""
      msg = "Node's implicit dependency %s has changed, rebuilding the node: %s" % (dep, node_name)
    
    elif code == NodeStaleReason.NO_TARGETS:
      msg = "Node's targets were not previously stored, rebuilding the node: %s" % (node_name,)
    
    elif code == NodeStaleReason.TARGET_CHANGED:
      msg = "Node's target '%s' has changed, rebuilding the node: %s" % (self.entity, node_name)
    
    elif code == NodeStaleReason.FORCE_REBUILD:
      msg = "Forced rebuild, rebuilding the node: %s" % (node_name,)
    
    else:
      msg = "Node's state is outdated, rebuilding the node: %s" % node_name
    
    return msg
      
#//===========================================================================//

def   _getTraceArg( entity, brief ):
  if isinstance( entity, FileEntityBase ):
    value = entity.get()
    if brief:
      value = os.path.basename( value )
  else:
    if isinstance( entity, EntityBase ):
      value = entity.get()

    elif isinstance( entity, FilePath ):
      if brief:
        value = os.path.basename( entity )

    elif isString( entity ):
      value = entity.strip()

      npos = value.find('\n')
      if npos != -1:
        value = value[:npos]

      max_len = 64 if brief else 256
      src_len = len(value)
      if src_len > max_len:
        value = "%s...%s" % (value[:max_len//2], value[src_len - (max_len//2):])

    else:
      value = None
  
  return value

#//===========================================================================//

def   _joinArgs( entities, brief ):
  
  args = []
  
  for arg in toSequence(entities):
    arg = _getTraceArg(arg, brief )
    if arg and isString( arg ):
      args.append( arg )
  
  if not brief or (len(args) < 3):
    return ' '.join( args )
  
  wish_size = 128
  
  args_str = [ args.pop(0) ]
  last = args.pop()
  
  size = len(args_str[0]) + len(last)
  
  for arg in args:
    size += len(arg)
    
    if size > wish_size:
      args_str.append('...')
      break
    
    args_str.append( arg )
    
  args_str.append( last )
  
  return ' '.join( args_str )

#//===========================================================================//

def   _getBuildStr( args, brief ):
    
    args = iter(args)
    
    name    = next(args, None)
    sources = next(args, None)
    targets = next(args, None)
    
    name    = _joinArgs( name,    brief )
    sources = _joinArgs( sources, brief )
    targets = _joinArgs( targets, brief )
    
    build_str  = name
    if sources:
      build_str += " << " + sources
    if targets:
      build_str += " >> " + targets
    
    return build_str
  
#//===========================================================================//
  
def   _getClearStr( args, brief = True ):
  
  args    = iter(args)
  next(args, None ) # name
  next(args, None ) # sources
  targets = next(args, None )
  
  return _joinArgs( targets, brief )

#//===========================================================================//

@pickleable
class   NodeEntity (EntityBase):
  
  __slots__ = (
    'name',
    'signature',
    
    'builder',
    'source_entities',
    'dep_entities',
    
    'target_entities',
    'itarget_entities',
    'idep_entities',
    'idep_keys',
  )
  
  #//-------------------------------------------------------//
  
  def   __new__( cls, name = NotImplemented, signature = NotImplemented, targets = None, itargets = None, idep_keys = None,
                 builder = None, source_entities = None, dep_entities = None ):
    
    self = super(NodeEntity,cls).__new__( cls, name, signature )
    
    if targets is not None:
      self.target_entities    = targets
      self.itarget_entities   = itargets
      self.idep_keys          = idep_keys
    else:
      self.builder          = builder
      self.source_entities  = source_entities
      self.dep_entities     = dep_entities
    
    return self
  
  #//-------------------------------------------------------//
  
  def   get( self ):
    return self.name
  
  #//-------------------------------------------------------//
  
  def   __getnewargs__( self ):
    return self.name, self.signature, self.targets, self.itargets, self.idep_keys
  
  #//-------------------------------------------------------//
  
  def   getTargets( self ):
    builder = self.builder
    return builder.makeEntities( builder.getTargetEntities( self.source_entities ) )
  
  #//-------------------------------------------------------//
  
  def   getName( self ):
    
    hash = newHash( self.builder.name )
    
    name_entities = self.target_entities
    if not name_entities:
      name_entities = self.source_entities
    
    names = sorted( entity.id for entity in name_entities )
    for name in names:
      hash.update( name )
    
    return hash.digest()
  
  #//-------------------------------------------------------//
  
  def   getSignature( self ):
    
    builder_signature = self.builder.signature
    if builder_signature is None:
      return None
    
    hash = newHash( builder_signature )
    
    for entity in self.dep_entities:
      ent_sign = entity.signature
      if not ent_sign:
        return None
      
      hash.update( entity.id )
      hash.update( ent_sign )
    
    for entity in self.source_entities:
      entity_signature = entity.signature
      if entity_signature is None:
        return None
      
      hash.update( entity_signature )
    
    return hash.digest()
  
  #//-------------------------------------------------------//
  
  def   __getattr__(self, attr):
    if attr == 'target_entities':
      self.target_entities = targets = self.getTargets() 
      return targets
    
    return super(NodeEntity, self).__getattr__( attr )

  #//-------------------------------------------------------//
  
  _ACTUAL_IDEPS_CACHE = {}
  
  @staticmethod
  def   _checkIdeps( vfile, idep_keys, idep_entities, reason, _actual_ideps_cache = _ACTUAL_IDEPS_CACHE ):
    for key in idep_keys:
      entity = vfile.getEntityByKey( key )
      
      if entity is None:
        if reason is not None:
          reason.setImplicitDepChanged()
        return False
      
      entity_id = entity.id
      
      if entity_id not in _actual_ideps_cache:
        actual_entity = entity.getActual()
        if entity is actual_entity:
          _actual_ideps_cache[ entity_id ] = key, entity
        else:
          new_key = vfile.replaceEntity( key, actual_entity )
          _actual_ideps_cache[ entity_id ] = new_key, actual_entity
          
          if reason is not None:
            reason.setImplicitDepChanged( entity )
          return False
            
      idep_entities.append( entity )
    
    return True
  
  #//-------------------------------------------------------//
  
  def   _saveIdeps( self, vfile, _actual_ideps_cache = _ACTUAL_IDEPS_CACHE ):
    
    keys = []
    entities = []
    new_entities = []
    for entity in toSequence(self.idep_entities):
      entity_id = entity.id
      pair = _actual_ideps_cache.get( entity_id, None )
      if pair is None:
        if entity.signature is None:
          raise ErrorUnactualEntity( entity )
        
        new_entities.append( entity )
      else:
        key, entity = pair
        keys.append( key )
      
      entities.append( entity )
    
    keys[0:1] = vfile.addEntities( new_entities ) 
    
    self.idep_entities  = entities
    self.idep_keys      = keys
  
  #//-------------------------------------------------------//
  
  @staticmethod
  def   _checkTargets( entities, reason ):
    if entities is None:
      if reason is not None:
        reason.setNoTargets()
      return False
    
    for entity in entities:
      if not entity.isActual():
        if reason is not None:
          reason.setTargetChanged( entity )
        return False
        
    return True
  
  #//-------------------------------------------------------//
  
  def   checkActual( self, vfile, built_node_names = None, explain = False ):
    
    reason = NodeStaleReason( self.builder, self.source_entities, self.target_entities ) if explain else None
    
    self.target_entities = []
    self.itarget_entities = []
    self.idep_entities = []
    
    if (built_node_names is not None) and (self.name not in built_node_names):
      if reason is not None:
        reason.setForceRebuild()
      return False
    
    other = vfile.findEntity( self )
    
    if other is None:
      if reason is not None:
        reason.setNew()
      return False
    
    if not self.signature:
      if reason is not None:
        reason.setNoSignature()
      return False
    
    if self.signature != other.signature:
      if reason is not None:
        reason.setSignatureChanged()
      return False
    
    ideps = []
    if not self._checkIdeps( vfile, other.idep_keys, ideps, reason ):
      return False
    
    if not self._checkTargets( other.target_entities, reason ):
      return False
    
    self.target_entities = other.target_entities
    self.itarget_entities = other.itarget_entities
    self.idep_entities = ideps
    
    return True

  #//-------------------------------------------------------//
  
  def   save( self, vfile ):
    
    for entity in self.target_entities:
      if entity.signature is None:
        raise ErrorUnactualEntity( entity )
    
    self._saveIdeps( vfile )
    
    vfile.addEntity( self )
  
  #//-------------------------------------------------------//
  
  def   addTargets( self, entities, tags = None ):
    self.target_entities.extend( self.builder.makeEntities( toSequence(entities), tags ) )
  
  def   addTargetFiles( self, entities, tags = None ):
    self.target_entities.extend( self.builder.makeFileEntities( toSequence(entities), tags ) )
  
  add = addTargets
  addFiles = addTargetFiles
  
  #//-------------------------------------------------------//
  
  def   addSideEffects( self, entities, tags = None ):
    self.itarget_entities.extend( self.builder.makeEntities( toSequence(entities), tags ) )
  
  def   addSideEffectFiles( self, entities, tags = None ):
    self.itarget_entities.extend( self.builder.makeFileEntities( toSequence(entities), tags ) )
  
  #//-------------------------------------------------------//
  
  def   addDependencies( self, entities, tags = None ):
    self.idep_entities.extend( self.builder.makeEntities( toSequence(entities), tags ) )
  
  def   addDependencyFiles( self, entities, tags = None ):
    self.idep_entities.extend( self.builder.makeFileEntities( toSequence(entities), tags ) )

#//===========================================================================//

class _NodeBatchTargets ( object ):
  
  def   __init__( self, node_entities_map ):
    self.node_entities_map = node_entities_map
    
  #//-------------------------------------------------------//
  
  def   __getitem__( self, source ):
    try:
      return self.node_entities_map[ source ]
    except KeyError:
      raise ErrorNodeUnknownSource( source )

#//===========================================================================//

class NodeFilter (object):
  
  __slots__ = (
    'node',
    'node_attribute',
  )
  
  def   __init__( self, node, node_attribute = 'target_entities' ):
    self.node = node
    self.node_attribute = node_attribute
  
  #//-------------------------------------------------------//
  
  def   getNode(self):
    node = self.node
    
    while isinstance( node, NodeFilter ):
      node = node.node
    
    return node
  
  #//-------------------------------------------------------//
  
  def   __iter__(self):
    raise TypeError()
  
  def   __getitem__(self, item ):
    return NodeIndexFilter( self, item )
  
  #//-------------------------------------------------------//
  
  def   get(self):
    
    entities = self.getEntities()
    if len(entities) == 1:
      return entities[0]
    
    return entities
 
  #//-------------------------------------------------------//
  
  def   getEntities(self):
    node = self.node
    if isinstance( node, NodeFilter ):
      entities = node.getEntities()
    else:
      entities = getattr( node, self.node_attribute )
    
    return entities
  
#//===========================================================================//

class NodeTagsFilter( NodeFilter ):
  __slots__ = (
      'tags',
    )
  
  def   __init__( self, node, tags, node_attribute = 'target_entities' ):
    super(NodeTagsFilter, self).__init__( node, node_attribute )
    self.tags = frozenset( toSequence( tags ) )
  
  def   getEntities(self):
    entities = super(NodeTagsFilter, self).getEntities()
  
    tags = self.tags
    return tuple( entity for entity in entities if entity.tags and (entity.tags & tags) )

#//===========================================================================//

class NodeIndexFilter( NodeFilter ):
  __slots__ = (
      'index',
    )
  
  def   __init__( self, node, index, node_attribute = 'target_entities' ):
    super(NodeIndexFilter, self).__init__( node, node_attribute )
    self.index = index
  
  def   getEntities(self):
    entities = super(NodeIndexFilter, self).getEntities()
    
    try:
      return toSequence( entities[ self.index ] )
    except IndexError:
      return tuple()
    

#//===========================================================================//

class NodeDirNameFilter( NodeFilter ):
  def   getEntities(self):
    entities = super(NodeDirNameFilter, self).getEntities()
    return tuple( SimpleEntity( os.path.dirname( entity.get() ) ) for entity in entities )

#//===========================================================================//

class NodeBaseNameFilter( NodeFilter ):
  def   getEntities(self):
    entities = super(NodeBaseNameFilter, self).getEntities()
    return tuple( SimpleEntity( os.path.basename( entity.get() ) ) for entity in entities )

#//===========================================================================//

#noinspection PyAttributeOutsideInit
class Node (object):
  
  __slots__ = (
    'builder',
    'options',
    'cwd',
    
    'initiated',
    'depends_called',
    'replace_called',
    'split_called',
    'is_actual',
    
    'node_entities',
    'node_entities_map',
    
    'sources',
    'source_entities',
    
    'dep_nodes',
    'dep_entities',
    
    'target_entities',
    'itarget_entities',
    'idep_entities',
  )
  
  #//-------------------------------------------------------//

  def   __init__( self, builder, sources, cwd = None ):

    self.builder = builder
    self.options = getattr( builder, 'options', None )
    
    if cwd is None:
      self.cwd = os.path.abspath( os.getcwd() )
    else:
      self.cwd = cwd
    
    self.initiated      = False
    self.depends_called = False
    self.replace_called = False
    self.split_called   = False
    self.is_actual      = False
    
    self.sources = tuple(toSequence( sources ))
    self.dep_nodes = set()
    self.dep_entities = []
  
  #//=======================================================//
  
  def   shrink(self):
    self.cwd = None
    self.dep_nodes = None
    self.sources = None
    self.node_entities = None
    self.node_entities_map = None
    
    self.builder = None
    self.options = None
  
  #//=======================================================//
  
  def   depends( self, dependencies ):
    
    dep_nodes = self.dep_nodes
    dep_entities = self.dep_entities
    
    for entity in toSequence( dependencies ):
      if isinstance( entity, Node ):
        dep_nodes.add( entity )
      
      elif isinstance( entity, NodeFilter ):
        dep_nodes.add( entity.getNode() )
      
      elif isinstance( entity, EntityBase ):
        dep_entities.append( entity )
      
      else:
        raise ErrorNodeDependencyInvalid( entity )
  
  #//=======================================================//
  
  def   __getattr__(self, attr):
    if attr in [ 'target_entities', 'itarget_entities', 'idep_entities' ]:
      raise ErrorNoTargets( self )

    raise AttributeError( "Node has not attribute '%s'" % (attr,) )
  
  #//=======================================================//
  
  def   _setSourceEntities(self):
    entities = []
    
    makeEntity = self.builder.makeEntity
    
    for src in self.sources:
      
      if isinstance( src, Node ):
        entities += src.target_entities
      
      elif isinstance( src, NodeFilter ):
        entities += src.getEntities()
      
      elif isinstance( src, EntityBase ):
        entities.append( src )
      
      else:
        entity = makeEntity( src )
        entities.append( entity )
    
    self.sources = None
    self.source_entities = tuple(entities)
  
  #//=======================================================//
  
  def   _updateDepEntities(self):
    dep_nodes = self.dep_nodes
    
    if not dep_nodes:
      return
    
    dep_entities = self.dep_entities
    
    for node in dep_nodes:
      target_entities = node.target_entities
      if target_entities:
        dep_entities.extend( target_entities )
    
    dep_nodes.clear()
    
    dep_entities.sort( key = operator.attrgetter('id') )
  
  #//=======================================================//
  
  def   initiate(self):
    if self.initiated:
      if self.sources:            # reinitialize the replaced source entities
        self._setSourceEntities()
    else:
      with Chdir(self.cwd):
        self.builder = self.builder.initiate()
        self._setSourceEntities()
        self._updateDepEntities()
        
      self.initiated = True
    
  
  #//=======================================================//
  
  def   buildDepends( self ):
    if self.depends_called:
      return None
      
    nodes = self.builder.depends( self.source_entities )
    self.depends_called = True
    return nodes
  
  #//=======================================================//
  
  def   buildReplace( self ):
    
    if self.replace_called:
      return False
    
    sources = self.builder.replace( self.source_entities )
    if sources is None:
      return False
    
    self.sources = tuple( toSequence( sources ) )   # source_entities will be reinitialized later
    
    return True
  
  #//=======================================================//
  
  def   _splitBatch( self, vfile, built_node_names, explain ):
    builder = self.builder
    dep_entities = self.dep_entities
    node_entities = []
    not_actual_nodes = {}
    not_actual_sources = []
    for src in self.source_entities:
      node_entity = NodeEntity( builder = builder, source_entities = (src,), dep_entities = dep_entities )
      if not node_entity.checkActual( vfile, built_node_names, explain ):
        not_actual_nodes[ src ] = node_entity
        not_actual_sources.append( src )
      
      node_entities.append( node_entity )
    
    self.node_entities  = node_entities
    self.is_actual      = True       # we don't need to check actual status anymore
    
    if not not_actual_nodes:
      return None
    
    groups = builder.split( not_actual_sources )
    if not groups:
      groups = not_actual_sources   # this should never happen, looks like a bug in the builder
    
    split_nodes = []
    
    for group in groups:
      group = tuple(toSequence( group ))
      
      node_entities = tuple( not_actual_nodes[src] for src in group )
      node = self._split( group, node_entities )
      node.node_entities_map = not_actual_nodes
      
      split_nodes.append( node )
    
    return split_nodes
  
  #//=======================================================//
  
  def   buildSplit( self, vfile, built_node_names = None, explain = False ):
    if self.split_called:
      return None
    
    self.split_called = True
    
    builder = self.builder
    dep_entities = self.dep_entities
    
    if builder.isBatch():
      return self._splitBatch( vfile, built_node_names, explain )
    
    #//-------------------------------------------------------//
    sources = self.source_entities
    
    groups = self.builder.split( sources )
    
    if (not groups) or (len(groups) < 2):                 # No source groups, just build the sources
      node_entity = NodeEntity( builder = builder,
                                source_entities = sources,
                                dep_entities = dep_entities )
      
      self.is_actual = node_entity.checkActual( vfile, built_node_names, explain )
      self.node_entities = (node_entity,)
      return None
    
    #//-------------------------------------------------------//
    # create split Nodes
    
    node_entities = []
    split_nodes = []
    for group in groups:
      
      group = toSequence( group )
      
      node_entity = NodeEntity( builder = builder,
                                source_entities = group,
                                dep_entities = dep_entities )
      
      if not node_entity.checkActual( vfile, built_node_names, explain ):
        node = self._split( group, (node_entity,) )
        split_nodes.append( node_entity )
      
      node_entities.append( node_entity )
    
    self.node_entities = node_entities
    self.is_actual = True       # we don't need to check actual status anymore
    
    return split_nodes
  
  #//=======================================================//
  
  def   _split( self, source_entities, node_entities ):
    
    other = object.__new__( self.__class__ )
    
    other.builder         = self.builder
    other.source_entities = source_entities
    other.node_entities   = node_entities
    other.initiated       = True
    other.depends_called  = True
    other.replace_called  = True
    other.split_called    = True
    other.is_actual       = False
    
    return other
  
  #//=======================================================//
  
  def   _populateTargets( self ):
    
    node_entities = self.node_entities
    
    if len(node_entities) == 1:
      node_entity = node_entities[0]
      
      self.target_entities  = node_entity.targets
      self.itarget_entities = node_entity.itargets
      self.idep_entities    = node_entity.ideps
    
    else:
      
      targets   = []
      itargets  = []
      ideps  = []
      
      for node_entity in self.node_entities:
        targets   += node_entity.target_entities
        itargets  += node_entity.itarget_entities
        ideps     += node_entity.idep_entities
        
      self.target_entities = targets
      self.itarget_entities = itargets
      self.idep_entities = ideps
  
  #//=======================================================//
  
  def   isActual( self ):
    
    if not self.is_actual:
      return False
    
    self._populateTargets()
    return True
  
  #//=======================================================//
  
  def   build( self ):
    
    targets = self.node_entities
    if len(targets) == 1:
      output = self.builder.build( self.source_entities, targets )
    else:
      targets = _NodeBatchTargets( self.node_entities_map )
      output = self.builder.buildBatch( self.source_entities, targets )
    
    self._populateTargets()
    
    return output

  #//=======================================================//
  
  def   save( self, vfile ):
    for node_entity in self.node_entities:
      node_entity.save( vfile )
  
  #//=======================================================//
  
  def   clear( self, vfile ):
    """
    Clear produced entities
    """
    
    self.idep_entities = tuple()
    
    node_keys = []
    node_entity = NodeEntity( name = self.name )
    
    node_key = vfile.findEntityKey( node_entity )
    if node_key is None:
      if self.target_entities is None:
        self.target_entities = tuple()
      
      self.itarget_entities = tuple()
      
    else:
      node_entity = vfile.getEntityByKey( node_key )
      
      targets = node_entity.targets
      itargets = node_entity.itargets
      
      if targets is not None:
        self.target_entities  = targets
        self.itarget_entities = itargets
      else:
        self.target_entities  = tuple()
        self.itarget_entities = tuple()
      
      node_keys.append( node_key )
      
    try:
      self.builder.clear( self )
    except Exception:
      pass
    
    return node_keys
  
  #//=======================================================//
  
  def   getWeight( self ):
    return self.builder.getWeight( self )
  
  #//=======================================================//
  
  def   getNames(self):
    return (entity.name for entity in self.node_entities)
  
  def   getNamesAndSignatures(self):
    return ((entity.name, entity.signature) for entity in self.node_entities)
  
  #//=======================================================//
  
  def   getDepNodes(self):
    return self.dep_nodes
  
  #//=======================================================//
  
  def   getSources(self):
    return tuple( src.get() for src in self.getSourceEntities() )
  
  #//=======================================================//
  
  def   getSourceEntities(self):
    return self.source_entities
  
  #//=======================================================//
  
  def   getSourceNodes(self):
    nodes = []
    
    for src in self.sources:
      if isinstance(src, Node):
        nodes.append( src )
      
      elif isinstance(src, NodeFilter):
        nodes.append( src.getNode() )
        
    return nodes
  
  #//=======================================================//
  
  def   isBuilt(self):
    return self.builder is None
  
  #//=======================================================//
  
  def   at(self, tags ):
    return NodeTagsFilter( self, tags )
  
  #//=======================================================//
  
  def   __iter__(self):
    raise TypeError()
  
  def   __getitem__(self, item ):
    return NodeIndexFilter( self, item )
  
  #//=======================================================//
  
  def   __filter( self, node_attribute, tags ):
    if tags is None:
      return NodeFilter( self, node_attribute )
    
    return NodeTagsFilter( self, tags, node_attribute )
  
  #//=======================================================//
  
  def   filterSources( self, tags = None ):
    return self.__filter( 'source_entities', tags )
  
  def   filterSideEffects( self, tags = None ):
    return self.__filter( 'itarget_entities', tags )
  
  def   filterImplicitDependencies( self, tags = None ):
    return self.__filter( 'idep_entities', tags )
  
  def   filterDependencies( self, tags = None ):
    return self.__filter( 'dep_entities', tags )
  
  #//=======================================================//
  
  def   get(self):
    targets = self.getTargetEntities()
    if len(targets) == 1:
      return targets[0].get()
    
    return tuple( target.get() for target in targets )
  
  #//=======================================================//
  
  def   getTargetEntities(self):
    return self.target_entities
  
  #//=======================================================//
  
  def   getBuildStr( self, brief = True ):
    try:
      targets = getattr( self, 'target_entities', None )
      
      args = self.builder.getTraceArgs( self.source_entities, targets, brief )
      
      return _getBuildStr( args, brief )
    
    except Exception as ex:
      if 'BuilderInitiator' not in str(ex):
        print("getBuildStr: ex: %s, %s" % (ex,ex.args))
        raise
    
    return str(self)  # TODO: return raw data
    
  #//=======================================================//
  
  def   printSources(self):
    result = []
    sources = self.sources
    if not sources:
      sources = self.source_entities
    
    for src in sources:
      if isinstance(src, EntityBase):
        result.append( src.get() )
      
      elif isinstance( src, Node ):
        targets = getattr(src, 'target_entities', None)
        if targets is not None:
          result += ( target.get() for target in targets )
        else:
          result.append( src ) 
      
      elif isinstance( src, NodeFilter ):
        try:
          targets = src.getEntities()
        except AttributeError:
          continue
        
        if targets is not None:
          result += ( target.get() for target in targets )
        else:
          result.append( src ) 
      
      else:
        result.append( src )
    
    sources_str = ', '.join( map( str, result ) )
    
    logInfo("node '%s' sources: %s" % (self, sources_str))
  
  #//=======================================================//
  
  def   printTargets(self):
    targets = [ t.get() for t in getattr(self, 'target_entities', []) ]
    logInfo("node '%s' targets: %s" % (self, targets))

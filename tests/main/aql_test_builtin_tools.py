import os
import sys

sys.path.insert( 0, os.path.normpath(os.path.join( os.path.dirname( __file__ ), '..') ))

from aql_tests import AqlTestCase, runLocalTests

from aql.utils import Tempdir, whereProgram, \
    removeUserHandler, addUserHandler, disableDefaultHandlers, enableDefaultHandlers
from aql.util_types import FilePath
from aql.nodes import Node, BuildManager
from aql.options import builtinOptions

from aql.main import Project, ProjectConfig, ErrorToolNotFound
from aql.main.aql_builtin_tools import ExecuteCommand, CopyFilesBuilder, CopyFileAsBuilder

#//===========================================================================//

class TestBuiltinTools( AqlTestCase ):
  
  #//-------------------------------------------------------//

  # noinspection PyUnusedLocal
  def   eventNodeBuilding( self, settings, node ):
    self.building_started += 1
  
  #//-------------------------------------------------------//
  
  # noinspection PyUnusedLocal
  def   eventNodeBuildingFinished( self, settings, node, builder_output, progress ):
    self.building_finished += 1
    self.built_nodes += 1
  
  #//-------------------------------------------------------//
  
  def   setUp( self ):
    super(TestBuiltinTools,self).setUp()
    # disableDefaultHandlers()
    
    self.building_started = 0
    addUserHandler( self.eventNodeBuilding )
    
    self.building_finished = 0
    self.built_nodes = 0
    addUserHandler( self.eventNodeBuildingFinished )
  
  #//-------------------------------------------------------//
  
  def   tearDown( self ):
    removeUserHandler( self.eventNodeBuilding )
    removeUserHandler( self.eventNodeBuildingFinished )

    enableDefaultHandlers()
  
  #//-------------------------------------------------------//

  def   _build(self, bm, **kw ):
    is_ok = bm.build( **kw )
    if not is_ok:
      bm.printFails()

    self.assertTrue( is_ok )

  #//-------------------------------------------------------//

  def test_exec(self):
    
    with Tempdir() as tmp_dir:
      
      build_dir = FilePath(tmp_dir).join('build')
      
      options = builtinOptions()

      cmd = [ whereProgram( "python" ), '-c', 'print("TEST EXEC")']

      options.build_dir = build_dir
      
      exec_cmd = ExecuteCommand( options )
      
      bm = BuildManager()
      try:
        
        result = Node( exec_cmd, cmd )

        bm.add( result )
        
        self._build( bm, jobs = 1, keep_going = False )
        
        self.assertEqual( self.building_started, 1 )
        self.assertEqual( self.building_started, self.building_finished )
        
        bm.close()
        
        result = Node( exec_cmd, cmd )

        bm = BuildManager()
        bm.add( result )
        
        self.building_started = 0
        self._build( bm, jobs = 1, keep_going = False )
        
        self.assertEqual( self.building_started, 0 )
        
      finally:
        bm.close()
  
  #//-------------------------------------------------------//

  def test_copy_files(self):
    
    with Tempdir() as tmp_install_dir:
      with Tempdir() as tmp_dir:
        # tmp_install_dir = Tempdir()
        # tmp_dir = Tempdir()
        
        build_dir = os.path.join( tmp_dir, 'output' )
        
        num_sources = 3
        sources = self.generateSourceFiles( tmp_dir, num_sources, 200 )
        
        cfg = ProjectConfig( args = [ "build_dir=%s" % build_dir] )
        
        prj = Project( cfg )
        
        node = prj.tools.CopyFiles( sources, target = tmp_install_dir )
        
        node.options.batch_groups = 1
        
        self.buildPrj( prj, 1 )
        
        prj.tools.CopyFiles( sources, target = tmp_install_dir )
        
        self.buildPrj( prj, 0 )
  
  #//-------------------------------------------------------//

  def   test_copy_file_as(self):
    
    with Tempdir() as tmp_install_dir:
      with Tempdir() as tmp_dir:
        # tmp_install_dir = Tempdir()
        # tmp_dir = Tempdir()
        
        build_dir = os.path.join( tmp_dir, 'output' )
        
        source = self.generateFile( tmp_dir, 0, 200 )
        target = os.path.join( tmp_install_dir, 'copy_as_source.dat' )
        
        cfg = ProjectConfig( args = [ "build_dir=%s" % build_dir] )
        
        prj = Project( cfg )
        
        prj.tools.CopyFileAs( source, target = target )
        
        self.buildPrj( prj, 1 )
        
        prj.tools.CopyFileAs( source, target = target )
        
        self.buildPrj( prj, 0 )
  
  #//-------------------------------------------------------//

#//===========================================================================//

if __name__ == "__main__":
  runLocalTests()

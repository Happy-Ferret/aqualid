﻿import io
import sys
import pickle
import os.path

sys.path.insert( 0, os.path.normpath(os.path.join( os.path.dirname( __file__ ), '..') ))

from aql_tests import testcase, skip, runTests
from aql_value import Value, IgnoreCaseStringContent

#//===========================================================================//

@testcase
def test_str_value(self):
  
  value1 = Value('results_link', 'http://buildsrv.com/results.out')
  value2 = Value('results_link', 'http://buildsrv.com/results.out')
  
  self.assertEqual( value1, value1 )
  self.assertEqual( value1, value2 )
  
  value2 = Value( value1 )
  self.assertEqual( value1, value2 )
  
  value2.content = value2.content.upper()
  self.assertNotEqual( value1.content, value2.content )
  
  value2.content = IgnoreCaseStringContent( value2.content )
  self.assertNotEqual( value1.content, value2.content )
  
  value1.content = IgnoreCaseStringContent( value1.content )
  self.assertEqual( value1.content, value2.content )

#//===========================================================================//

@testcase
def test_str_value_save_load(self):
  
  value1 = Value('results_link', 'http://buildsrv.com/results.out')
  value2 = Value('results_link', IgnoreCaseStringContent(value1.content))
  
  self.testSaveLoad( value1 )
  self.testSaveLoad( value2 )

#//===========================================================================//

@testcase
def test_str_empty_value_save_load(self):
  
  value1 = Value('results_link')
  value2 = Value( value1 )
  
  self.testSaveLoad( value1 )
  self.testSaveLoad( value2 )

#//=======================================================//

if __name__ == "__main__":
  runTests()
"""
Created on Nov 14, 2013

@author: alfoa
"""
#for future compatibility with Python 3--------------------------------------------------------------
from __future__ import division, print_function, unicode_literals, absolute_import
import warnings
warnings.simplefilter('default',DeprecationWarning)
if not 'xrange' in dir(__builtins__):
  xrange = range
#End compatibility block for Python 3----------------------------------------------------------------

#External Modules------------------------------------------------------------------------------------
import numpy as np
from BaseClasses import BaseType
import ast
from scipy.interpolate import Rbf,griddata
import numpy.ma as ma
import importlib                #it is used in exec code so it might be detected as unused
import platform
import os
#External Modules End--------------------------------------------------------------------------------

#Internal Modules------------------------------------------------------------------------------------
import Datas
from utils import returnPrintTag, returnPrintPostTag, interpolateFunction
from cached_ndarray import c1darray
#Internal Modules End--------------------------------------------------------------------------------

# set a global variable for backend default setting
if platform.system() == 'Windows': disAvail = True
else:
  if os.getenv('DISPLAY'): disAvail = True
  else:                    disAvail = False


#def removeNanEntries(X):
#  return X[~np.isnan(X).any(1)]

class OutStreamManager(BaseType):
  """
  ********************************************************************
  *                          OUTSTREAM CLASS                         *
  ********************************************************************
  *  This class is a general base class for outstream action classes *
  *  For example, a matplotlib interface class or Print class, etc.  *
  ********************************************************************
  """
  def __init__(self):
    """
      Init of Base class
    """
    BaseType.__init__(self)
    # outstreaming options
    self.options = {}
    #counter
    self.counter = 0
    #overwrite outstream?
    self.overwrite = True
    # outstream types available
    self.availableOutStreamType = []
    # number of agregated outstreams
    self.numberAggregatedOS = 1
    self.printTag = returnPrintTag('OUTSTREAM MANAGER')

  def _readMoreXML(self,xmlNode):
    """
    Function to read the portion of the xml input that belongs to this specialized class
    and initialize some stuff based on the got inputs
    @ In, xmlNode    : Xml element node
    @ Out, None
    """
    #BaseType._readMoreXML(self,xmlNode)
    #if self.globalAttributes:
    #  if 'online' in self.globalAttributes.keys():
    #    if self.globalAttributes['online'].lower() in ['t','true','on']: self.online = True
    #    else: self.online = False
    if 'overwrite' in xmlNode.attrib.keys():
      if xmlNode.attrib['overwrite'].lower() in ['t','true','on']: self.overwrite = True
      else: self.overwrite = False
    self.localReadXML(xmlNode)

  def addInitParams(self,tempDict):
    """
    Function adds the initial parameter in a temporary dictionary
    @ In, tempDict
    @ Out, tempDict
    """
    tempDict[                     'Global Class Type                 '] = 'OutStreamManager'
    tempDict[                     'Specialized Class Type            '] = self.type
    if self.overwrite:   tempDict['Overwrite output everytime called '] = 'True'
    else:                tempDict['Overwrite output everytime called '] = 'False'
    for index in range(len((self.availableOutStreamType))) : tempDict['OutStream Available #'+str(index+1)+'   :'] = self.availableOutStreamType[index]
    self.localAddInitParams(tempDict)
    return tempDict

  def addOutput(self):
    """
    Function to add a new output source (for example a CSV file or a HDF5 object)
    @ In, toLoadFrom, source object
    @ Out, None
    """
    raise NotImplementedError(self.printTag+': ERROR -> method addOutput must be implemented by derived classes!!!!')

  def initialize(self,inDict):
    """
    Function to initialize the OutStream. It basically looks for the "data" object and link it to the system
    @ In, inDict, dictionary, It contains all the Object are going to be used in the current step. The sources are searched into this.
    @ Out, None
    """
    self.sourceData   = []
    for agrosindex in range(self.numberAggregatedOS):
      foundData = False
      for output in inDict['Output']:
        if output.name.strip()==self.sourceName[agrosindex] and output.type in Datas.knownTypes():
          self.sourceData.append(output)
          foundData = True
      if not foundData:
        for inp in inDict['Input']:
          if not type(inp) == type(""):
            if inp.name.strip()==self.sourceName[agrosindex] and inp.type in Datas.knownTypes():
              self.sourceData.append(inp)
              foundData = True
      if not foundData and 'TargetEvaluation' in inDict.keys():
        if inDict['TargetEvaluation'].name.strip() == self.sourceName[agrosindex] and inDict['TargetEvaluation'].type in Datas.knownTypes():
          self.sourceData.append(inDict['TargetEvaluation'])
          foundData = True
      if not foundData and 'SolutionExport' in inDict.keys():
        if inDict['SolutionExport'].name.strip() == self.sourceName[agrosindex] and inDict['SolutionExport'].type in Datas.knownTypes():
          self.sourceData.append(inDict['SolutionExport'])
          foundData = True
      if not foundData: raise IOError(self.printTag+': ERROR -> the Data named ' + self.sourceName[agrosindex] + ' has not been found!!!!')
#
#
#
class OutStreamPlot(OutStreamManager):
  def __init__(self):
    OutStreamManager.__init__(self)
    self.type         = 'OutStreamPlot'
    self.printTag     = returnPrintTag('OUTSTREAM PLOT')
    # available 2D and 3D plot types
    self.availableOutStreamTypes = {2:['scatter','line','histogram','stem','step','pseudocolor'],
                                    3:['scatter','line','stem','surface','wireframe','tri-surface',
                                       'contour','filledContour','contour3D','filledContour3D','histogram']}
    # default plot is 2D
    self.dim          = 2
    # list of source names
    self.sourceName   = []
    # source of data
    self.sourceData   = None
    # dictionary of x,y,z coordinates
    self.xCoordinates  = None
    self.yCoordinates  = None
    self.zCoordinates  = None
    # dictionary of x,y,z values
    self.xValues = None
    self.yValues = None
    self.zValues = None
    # color map
    self.colorMapCoordinates = {}
    self.colorMapValues      = {}
    # list of the outstream types
    self.outStreamTypes = []
    # interpolate functions available
    self.interpAvail = ['nearest','linear','cubic','multiquadric','inverse','gaussian','Rbflinear','Rbfcubic','quintic','thin_plate']
    # actual plot
    self.actPlot = None
    self.actcm = None
  #####################
  #  PRIVATE METHODS  #
  #####################

  def __splitVariableNames(self,what,where):
    """
      Function to split the variable names
      @ In, what => x,y,z or colorMap
      @ In, where, tuple => pos 0 = plotIndex, pos 1 = variable Index
    """
    if   what == 'x'                : var = self.xCoordinates [where[0]][where[1]]
    elif what == 'y'                : var = self.yCoordinates [where[0]][where[1]]
    elif what == 'z'                : var = self.zCoordinates [where[0]][where[1]]
    elif what == 'colorMap'         : var = self.colorMapCoordinates[where[0]][where[1]]
    # the variable can contain brackets (when the symbol "|" is present in the variable name),
    # for example DataName|Input|(RavenAuxiliary|variableName|initial_value)
    # or it can look like DataName|Input|variableName
    if var:
      if '(' in var and ')' in var:
        if var.count('(') > 1: raise IOError(self.printTag+': ERROR -> In Plot ' +self.name +'.Only a couple of () is allowed in variable names!!!!!!')
        result = var.split('|(')[0].split('|')
        result.append(var.split('(')[1].replace(")", ""))
      else:  result = var.split('|')
    else: result = None
    if len(result) != 3: raise IOError(self.printTag+': ERROR -> In Plot ' +self.name +'.Only three level variables are accepted !!!!!')
    return result

  def __readPlotActions(self,snode):
    """
      Function to read, from the xml input, the actions that are required to be performed on the Plot
      @ In, snode => xml node
    """
    for node in snode:
      self.options[node.tag] = {}
      if len(node):
        for subnode in node:
          if subnode.tag != 'kwargs':
            self.options[node.tag][subnode.tag] = subnode.text
            if not subnode.text: raise IOError(self.printTag+': ERROR -> In Plot ' +self.name +'. Problem in sub-tag ' + subnode.tag + ' in '+node.tag+' block. Please check!')
          else:
            self.options[node.tag]['attributes'] = {}
            for subsub in subnode:
              try   : self.options[node.tag]['attributes'][subsub.tag] = ast.literal_eval(subsub.text)
              except: self.options[node.tag]['attributes'][subsub.tag] = subsub.text
              if not subnode.text: raise IOError(self.printTag+': ERROR -> In Plot ' +self.name +'. Problem in sub-tag ' + subnode.tag + ' in '+node.tag+' block. Please check!')
      elif node.text:
        if node.text.strip(): self.options[node.tag][node.tag] = node.text
    if 'how' not in self.options.keys(): self.options['how']={'how':'screen'}

  def __fillCoordinatesFromSource(self):
    """
      Function to retrieve the pointers of the data values (x,y,z)
      @ In, None
      @ Out, boolean, true if the data are filled, false otherwise
    """
    self.xValues = []
    if self.yCoordinates : self.yValues = []
    if self.zCoordinates : self.zValues = []
    #if self.colorMapCoordinates[pltindex] != None: self.colorMapValues = []
    for pltindex in range(len(self.outStreamTypes)):
      self.xValues.append(None)
      if self.yCoordinates : self.yValues.append(None)
      if self.zCoordinates : self.zValues.append(None)
      if self.colorMapCoordinates[pltindex] != None: self.colorMapValues[pltindex] = None
    for pltindex in range(len(self.outStreamTypes)):
      if self.sourceData[pltindex].isItEmpty(): return False
      if self.sourceData[pltindex].type.strip() not in 'Histories':
        self.xValues[pltindex] = {1:[]}
        if self.yCoordinates : self.yValues[pltindex] = {1:[]}
        if self.zCoordinates : self.zValues[pltindex] = {1:[]}
        if self.colorMapCoordinates[pltindex] != None: self.colorMapValues[pltindex] = {1:[]}
        for i in range(len(self.xCoordinates [pltindex])):
          xsplit = self.__splitVariableNames('x', (pltindex,i))
          parame = self.sourceData[pltindex].getParam(xsplit[1],xsplit[2],nodeid='ending')
          if type(parame) in [np.ndarray,c1darray]: self.xValues[pltindex][1].append(np.asarray(parame))
          else:
            conarr = np.zeros(len(parame.keys()))
            index = 0
            for item in parame.values(): conarr[index] = item[0]; index += 1
            self.xValues[pltindex][1].append(np.asarray(conarr))
        if self.yCoordinates :
          for i in range(len(self.yCoordinates [pltindex])):
            ysplit = self.__splitVariableNames('y', (pltindex,i))
            parame = self.sourceData[pltindex].getParam(ysplit[1],ysplit[2],nodeid='ending')
            if type(parame) in [np.ndarray,c1darray]: self.yValues[pltindex][1].append(np.asarray(parame))
            else:
              conarr = np.zeros(len(parame.keys()))
              index = 0
              for item in parame.values(): conarr[index] = item[0]; index += 1
              self.yValues[pltindex][1].append(np.asarray(conarr))
        if self.zCoordinates  and self.dim>2:
          for i in range(len(self.zCoordinates [pltindex])):
            zsplit = self.__splitVariableNames('z', (pltindex,i))
            parame = self.sourceData[pltindex].getParam(zsplit[1],zsplit[2],nodeid='ending')
            if type(parame) in [np.ndarray,c1darray]: self.zValues[pltindex][1].append(np.asarray(parame))
            else:
              conarr = np.zeros(len(parame.keys()))
              for index in range(len(parame.values())): conarr[index] = parame.values()[index][0]
              self.zValues[pltindex][1].append(np.asarray(conarr))
        if self.colorMapCoordinates[pltindex] != None:
          for i in range(len(self.colorMapCoordinates[pltindex])):
            zsplit = self.__splitVariableNames('colorMap', (pltindex,i))
            parame = self.sourceData[pltindex].getParam(zsplit[1],zsplit[2])
            if type(parame) in [np.ndarray,c1darray]: self.colorMapValues[pltindex][1].append(np.asarray(parame))
            else:
              conarr = np.zeros(len(parame.keys()))
              for index in range(len(parame.values())): conarr[index] = parame.values()[index][0]
              self.colorMapValues[pltindex][1].append(np.asarray(conarr))
      else:
        #Histories
        self.xValues[pltindex] = {}
        if self.yCoordinates : self.yValues[pltindex] = {}
        if self.zCoordinates   and self.dim>2: self.zValues[pltindex] = {}
        if self.colorMapCoordinates[pltindex] != None: self.colorMapValues[pltindex] = {}
        for cnt,key in enumerate(self.sourceData[pltindex].getInpParametersValues(nodeid='RecontructEnding').keys()):
          #the key is the actual history number (ie 1, 2 , 3 etc)
          self.xValues[pltindex][cnt] = []
          if self.yCoordinates : self.yValues[pltindex][cnt] = []
          if self.zCoordinates : self.zValues[pltindex][cnt] = []
          if self.colorMapCoordinates[pltindex] != None: self.colorMapValues[pltindex][cnt] = []
          for i in range(len(self.xCoordinates [pltindex])):
            xsplit = self.__splitVariableNames('x', (pltindex,i))
            self.xValues[pltindex][cnt].append(np.asarray(self.sourceData[pltindex].getParam(xsplit[1],cnt+1,nodeid='RecontructEnding')[xsplit[2]]))
          if self.yCoordinates :
            for i in range(len(self.yCoordinates [pltindex])):
              ysplit = self.__splitVariableNames('y', (pltindex,i))
              self.yValues[pltindex][cnt].append(np.asarray(self.sourceData[pltindex].getParam(ysplit[1],cnt+1,nodeid='RecontructEnding')[ysplit[2]]))
          if self.zCoordinates  and self.dim>2:
            for i in range(len(self.zCoordinates [pltindex])):
              zsplit = self.__splitVariableNames('z', (pltindex,i))
              self.zValues[pltindex][cnt].append(np.asarray(self.sourceData[pltindex].getParam(zsplit[1],cnt+1,nodeid='RecontructEnding')[zsplit[2]]))
          if self.colorMapCoordinates[pltindex] != None:
            for i in range(len(self.colorMapCoordinates[pltindex])):
              zsplit = self.__splitVariableNames('colorMap', (pltindex,i))
              self.colorMapValues[pltindex][cnt].append(np.asarray(self.sourceData[pltindex].getParam(zsplit[1],cnt+1,nodeid='RecontructEnding')[zsplit[2]]))
      #check if something has been got or not
      if len(self.xValues[pltindex].keys()) == 0: return False
      else:
        for key in self.xValues[pltindex].keys():
          if len(self.xValues[pltindex][key]) == 0: return False
          else:
            for i in range(len(self.xValues[pltindex][key])):
              if self.xValues[pltindex][key][i].size == 0: return False
      if self.yCoordinates :
        if len(self.yValues[pltindex].keys()) == 0: return False
        else:
          for key in self.yValues[pltindex].keys():
            if len(self.yValues[pltindex][key]) == 0: return False
            else:
              for i in range(len(self.yValues[pltindex][key])):
                if self.yValues[pltindex][key][i].size == 0: return False
      if self.zCoordinates  and self.dim>2:
        if len(self.zValues[pltindex].keys()) == 0: return False
        else:
          for key in self.zValues[pltindex].keys():
            if len(self.zValues[pltindex][key]) == 0: return False
            else:
              for i in range(len(self.zValues[pltindex][key])):
                if self.zValues[pltindex][key][i].size == 0: return False
      if self.colorMapCoordinates[pltindex] != None:
        if len(self.colorMapValues[pltindex].keys()) == 0: return False
        else:
          for key in self.colorMapValues[pltindex].keys():
            if len(self.colorMapValues[pltindex][key]) == 0: return False
            else:
              for i in range(len(self.colorMapValues[pltindex][key])):
                if self.colorMapValues[pltindex][key][i].size == 0: return False
    return True

  def __executeActions(self):
    """
      Function to execute the actions must be performed on the Plot(for example, set the x,y,z axis ranges, etc)
      @ In, None
    """
    if 'labelFormat' not in self.options.keys():
      if self.dim == 2:
        self.plt.gca().yaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
        self.plt.gca().xaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
        self.plt.ticklabel_format(**{'style':'sci','scilimits':(0,0),'useOffset':False,'axis':'both'})
        if self.dim == 3:
          self.plt.figure().gca(projection='3d').yaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
          self.plt.figure().gca(projection='3d').xaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
          self.plt.figure().gca(projection='3d').zaxis.set_major_formatter(self.mpl.ticker.ScalarFormatter())
          self.plt3D.ticklabel_format(**{'style':'sci','scilimits':(0,0),'useOffset':False,'axis':'both'})
    if 'title'        not in self.options.keys():
      if self.dim == 2: self.plt.title(self.name,fontdict={'verticalalignment':'baseline','horizontalalignment':'center'})
      if self.dim == 3: self.plt3D.set_title(self.name,fontdict={'verticalalignment':'baseline','horizontalalignment':'center'})
    for key in self.options.keys():
      if   key in ['how','plotSettings','figureProperties']: pass
      elif key == 'range':
        if self.dim == 2:
          if 'ymin' in self.options[key].keys(): self.plt.ylim(ymin = ast.literal_eval(self.options[key]['ymin']))
          if 'ymax' in self.options[key].keys(): self.plt.ylim(ymax = ast.literal_eval(self.options[key]['ymax']))
          if 'xmin' in self.options[key].keys(): self.plt.xlim(xmin = ast.literal_eval(self.options[key]['xmin']))
          if 'xmax' in self.options[key].keys(): self.plt.xlim(xmax = ast.literal_eval(self.options[key]['xmax']))
        elif self.dim == 3:
          if 'xmin' in self.options[key].keys(): self.plt3D.set_xlim3d(xmin = ast.literal_eval(self.options[key]['xmin']))
          if 'xmax' in self.options[key].keys(): self.plt3D.set_xlim3d(xmax = ast.literal_eval(self.options[key]['xmax']))
          if 'ymin' in self.options[key].keys(): self.plt3D.set_ylim3d(ymin = ast.literal_eval(self.options[key]['ymin']))
          if 'ymax' in self.options[key].keys(): self.plt3D.set_ylim3d(ymax = ast.literal_eval(self.options[key]['ymax']))
          if 'zmin' in self.options[key].keys():
            if 'zmax' not in self.options[key].keys(): print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> zmin inputted but not zmax. zmin ignored! ')
            else:self.plt3D.set_zlim(ast.literal_eval(self.options[key]['zmin']),ast.literal_eval(self.options[key]['zmax']))
          if 'zmax' in self.options[key].keys():
            if 'zmin' not in self.options[key].keys(): print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> zmax inputted but not zmin. zmax ignored! ')
            else:self.plt3D.set_zlim(ast.literal_eval(self.options[key]['zmin']),ast.literal_eval(self.options[key]['zmax']))
      elif key == 'labelFormat':
        if 'style' not in self.options[key].keys(): self.options[key]['style'        ]   = 'sci'
        if 'limits' not in self.options[key].keys(): self.options[key]['limits'      ] = '(0,0)'
        if 'useOffset' not in self.options[key].keys(): self.options[key]['useOffset'] = 'False'
        if 'axis' not in self.options[key].keys(): self.options[key]['axis'          ] = 'both'
        if self.dim == 2:  self.plt.ticklabel_format(**{'style':self.options[key]['style'],'scilimits':ast.literal_eval(self.options[key]['limits']),'useOffset':ast.literal_eval(self.options[key]['useOffset']),'axis':self.options[key]['axis']})
        elif self.dim == 3:self.plt3D.ticklabel_format(**{'style':self.options[key]['style'],'scilimits':ast.literal_eval(self.options[key]['limits']),'useOffset':ast.literal_eval(self.options[key]['useOffset']),'axis':self.options[key]['axis']})
      elif key == 'camera':
        if self.dim == 2: print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> 2D plots have not a camera attribute... They are 2D!!!!')
        elif self.dim == 3:
          if 'elevation' in self.options[key].keys() and 'azimuth' in self.options[key].keys():       self.plt3D.view_init(elev = float(self.options[key]['elevation']),azim = float(self.options[key]['azimuth']))
          elif 'elevation' in self.options[key].keys() and 'azimuth' not in self.options[key].keys(): self.plt3D.view_init(elev = float(self.options[key]['elevation']),azim = None)
          elif 'elevation' not in self.options[key].keys() and 'azimuth' in self.options[key].keys(): self.plt3D.view_init(elev = None,azim = float(self.options[key]['azimuth']))
      elif key == 'title':
        if self.dim == 2:
          self.plt.title(self.options[key]['text'],**self.options[key].get('attributes',{}))
        elif self.dim == 3:
          self.plt3D.set_title(self.options[key]['text'],**self.options[key].get('attributes',{}))
      elif key== 'scale':
        if self.dim == 2:
          if 'xscale' in self.options[key].keys(): self.plt.xscale(self.options[key]['xscale'],nonposy='clip')
          if 'yscale' in self.options[key].keys(): self.plt.yscale(self.options[key]['yscale'],nonposy='clip')
        elif self.dim == 3:
          if 'xscale' in self.options[key].keys(): self.plt3D.set_xscale(self.options[key]['xscale'],nonposy='clip')
          if 'yscale' in self.options[key].keys(): self.plt3D.set_yscale(self.options[key]['yscale'],nonposy='clip')
          if 'zscale' in self.options[key].keys(): self.plt3D.set_zscale(self.options[key]['zscale'],nonposy='clip')
      elif key == 'addText':
        if 'position' not in self.options[key].keys():
          if self.dim == 2 :self.options[key]['position'] = '0.0,0.0'
          else:self.options[key]['position'] = '0.0,0.0,0.0'
        if 'withdash' not in self.options[key].keys(): self.options[key]['withdash'] = 'False'
        if 'fontdict' not in self.options[key].keys(): self.options[key]['fontdict'] = 'None'
        else:
          try:
            self.options[key]['fontdict'] = ast.literal_eval(self.options[key]['fontdict'])
            self.options[key]['fontdict'] = str(self.options[key]['fontdict'])
          except AttributeError: raise Exception(self.printTag+': ERROR -> In ' + key +' tag: can not convert the string "' + self.options[key]['fontdict'] + '" to a dictionary! Check syntax for python function ast.literal_eval')
        if self.dim == 2 :
          self.plt.text(float(self.options[key]['position'].split(',')[0]),float(self.options[key]['position'].split(',')[1]),self.options[key]['text'],fontdict=ast.literal_eval(self.options[key]['fontdict']),**self.options[key].get('attributes',{}))
        elif self.dim ==3:
          self.plt3D.text(float(self.options[key]['position'].split(',')[0]),float(self.options[key]['position'].split(',')[1]),float(self.options[key]['position'].split(',')[2]),self.options[key]['text'],fontdict=ast.literal_eval(self.options[key]['fontdict']),withdash=ast.literal_eval(self.options[key]['withdash']),**self.options[key].get('attributes',{}))
      elif key == 'autoscale':
          if 'enable' not in self.options[key].keys(): self.options[key]['enable'] = 'True'
          elif self.options[key]['enable'].lower() in ['t','true']: self.options[key]['enable'] = 'True'
          elif self.options[key]['enable'].lower() in ['f','false']: self.options[key]['enable'] = 'False'
          if 'axis' not in self.options[key].keys()  : self.options[key]['axis'] = 'both'
          if 'tight' not in self.options[key].keys() : self.options[key]['tight'] = 'None'
          if self.dim == 2  : self.plt.autoscale(enable = ast.literal_eval(self.options[key]['enable']), axis = self.options[key]['axis'], tight = ast.literal_eval(self.options[key]['tight']))
          elif self.dim == 3: self.plt3D.autoscale(enable = ast.literal_eval(self.options[key]['enable']), axis = self.options[key]['axis'], tight = ast.literal_eval(self.options[key]['tight']))
      elif key == 'horizontalLine':
        if self.dim == 3: print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> horizontal_line not available in 3-D plots!!')
        elif self.dim == 2:
          if 'y' not in self.options[key].keys(): self.options[key]['y'] = '0'
          if 'xmin' not in self.options[key].keys()  : self.options[key]['xmin'] = '0'
          if 'xmax' not in self.options[key].keys() : self.options[key]['xmax'] = '1'
          if 'hold' not in self.options[key].keys() : self.options[key]['hold'] = 'None'
          self.plt.axhline(y=ast.literal_eval(self.options[key]['y']), xmin=ast.literal_eval(self.options[key]['xmin']), xmax=ast.literal_eval(self.options[key]['xmax']), hold=ast.literal_eval(self.options[key]['hold']),**self.options[key].get('attributes',{}))
      elif key == 'verticalLine':
        if self.dim == 3: print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> vertical_line not available in 3-D plots!!')
        elif self.dim == 2:
          if 'x' not in self.options[key].keys(): self.options[key]['x'] = '0'
          if 'ymin' not in self.options[key].keys()  : self.options[key]['ymin'] = '0'
          if 'ymax' not in self.options[key].keys() : self.options[key]['ymax'] = '1'
          if 'hold' not in self.options[key].keys() : self.options[key]['hold'] = 'None'
          self.plt.axvline(x=ast.literal_eval(self.options[key]['x']), ymin=ast.literal_eval(self.options[key]['ymin']), ymax=ast.literal_eval(self.options[key]['ymax']), hold=ast.literal_eval(self.options[key]['hold']),**self.options[key].get('attributes',{}))
      elif key == 'horizontalRectangle':
        if self.dim == 3: print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> horizontal_rectangle not available in 3-D plots!!')
        elif self.dim == 2:
          if 'ymin' not in self.options[key].keys(): raise Exception(self.printTag+': ERROR -> ymin parameter is needed for function horizontal_rectangle!!')
          if 'ymax' not in self.options[key].keys(): raise Exception(self.printTag+': ERROR -> ymax parameter is needed for function horizontal_rectangle!!')
          if 'xmin' not in self.options[key].keys()  : self.options[key]['xmin'] = '0'
          if 'xmax' not in self.options[key].keys() : self.options[key]['xmax'] = '1'
          self.plt.axhspan(ast.literal_eval(self.options[key]['ymin']),ast.literal_eval(self.options[key]['ymax']), xmin=ast.literal_eval(self.options[key]['xmin']), xmax=ast.literal_eval(self.options[key]['xmax']),**self.options[key].get('attributes',{}))
      elif key == 'verticalRectangle':
        if self.dim == 3: print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> vertical_rectangle not available in 3-D plots!!')
        elif self.dim == 2:
          if 'xmin' not in self.options[key].keys(): raise Exception(self.printTag+': ERROR -> xmin parameter is needed for function vertical_rectangle!!')
          if 'xmax' not in self.options[key].keys(): raise Exception(self.printTag+': ERROR -> xmax parameter is needed for function vertical_rectangle!!')
          if 'ymin' not in self.options[key].keys()  : self.options[key]['ymin'] = '0'
          if 'ymax' not in self.options[key].keys() : self.options[key]['ymax'] = '1'
          self.plt.axvspan(ast.literal_eval(self.options[key]['xmin']),ast.literal_eval(self.options[key]['xmax']), ymin=ast.literal_eval(self.options[key]['ymin']), ymax=ast.literal_eval(self.options[key]['ymax']),**self.options[key].get('attributes',{}))
      elif key == 'axesBox':
        if   self.dim == 3: print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> axes_box not available in 3-D plots!!')
        elif self.dim == 2: self.plt.box(self.options[key][key])
      elif key == 'grid':
        if 'b' not in self.options[key].keys()  : self.options[key]['b'] = 'off'
        if self.options[key]['b'].lower() in ['on','t','true']: self.options[key]['b'] = 'on'
        elif self.options[key]['b'].lower() in ['off','f','false']: self.options[key]['b'] = 'off'
        if 'which' not in self.options[key].keys() : self.options[key]['which'] = 'major'
        if 'axis' not in self.options[key].keys() : self.options[key]['axis'] = 'both'
        if self.dim == 2:
          self.plt.grid(b =self.options[key]['b'],which = self.options[key]['which'], axis=self.options[key]['axis'],**self.options[key].get('attributes',{}))
        elif self.dim == 3:
          self.plt3D.grid(b=self.options[key]['b'],**self.options[key].get('attributes',{}))
      else:
        print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> Try to perform not-predifined action ' + key +'. If it does not work check manual and/or relavite matplotlib method specification.')
        command_args = ' '
        import CustomCommandExecuter as execcommand
        for kk in self.options[key]:
          if kk != 'attributes' and kk != key:
            if command_args != ' ': prefix = ','
            else: prefix = ''
            try: command_args = command_args +prefix+ kk + '=' + str(ast.literal_eval(self.options[key][kk]))
            except:command_args = command_args +prefix+ kk + '="' + str(self.options[key][kk])+'"'
        try:
          if self.dim == 2:  execcommand.execCommand('self.plt.' + key + '(' + command_args + ')',self)
          elif self.dim == 3:execcommand.execCommand('self.plt.' + key + '(' + command_args + ')',self)
          #if self.dim == 2:  exec('self.plt.' + key + '(' + command_args + ')')
          #elif self.dim == 3:exec('self.plt3D.' + key + '(' + command_args + ')')
        except ValueError as ae:
          raise Exception(self.printTag+': ERROR -> <'+str(ae)+'> -> in execution custom action "' + key + '" in Plot ' + self.name + '.\n ' + self.printTag+': ERROR -> command has been called in the following way: ' + 'self.plt.' + key + '(' + command_args + ')')

  ####################
  #  PUBLIC METHODS  #
  ####################
  def localAddInitParams(self,tempDict):
    """
      This method is called from the base function. It adds the initial characteristic intial params that need to be seen by the whole enviroment
      @ In, tempDict
      @ Out, tempDict
    """
    tempDict['Plot is '] = str(self.dim)+'D'
    for index in range(len(self.sourceName)): tempDict['Source Name '+str(index)+' :'] = self.sourceName[index]

  def endInstructions(self,instructionString):
    if instructionString == 'interactive' and 'screen' in self.options['how']['how'].split(',') and disAvail:
      self.plt.figure(self.name)
      self.fig.ginput(n=-1, timeout=-1, show_clicks=False)

  def initialize(self,inDict):
    """
    Function called to initialize the OutStream, linking it to the proper Data
    @ In, inDict -> Dictionary that contains all the instantiaced classes needed for the actual step
                    In this dictionary the data are looked for
    """
    self.xCoordinates  = []
    self.sourceName    = []
    if 'figureProperties' in self.options.keys():
      key = 'figureProperties'
      if 'figsize' not in self.options[key].keys():   self.options[key]['figsize'  ] = 'None'
      if 'dpi' not in self.options[key].keys():       self.options[key]['dpi'      ] = 'None'
      if 'facecolor' not in self.options[key].keys(): self.options[key]['facecolor'] = 'None'
      if 'edgecolor' not in self.options[key].keys(): self.options[key]['edgecolor'] = 'None'
      if 'frameon' not in self.options[key].keys():   self.options[key]['frameon'  ] = 'True'
      elif self.options[key]['frameon'].lower() in ['t','true']: self.options[key]['frameon'] = 'True'
      elif self.options[key]['frameon'].lower() in ['f','false']: self.options[key]['frameon'] = 'False'
      self.fig = self.plt.figure(self.name, figsize=ast.literal_eval(self.options[key]['figsize']), dpi=ast.literal_eval(self.options[key]['dpi']), facecolor=self.options[key]['facecolor'],edgecolor=self.options[key]['edgecolor'],frameon=ast.literal_eval(self.options[key]['frameon']),**self.options[key].get('attributes',{}))
    else: self.fig = self.plt.figure(self.name)
    if self.dim == 3: self.plt3D = self.fig.add_subplot(111, projection='3d')
    for pltindex in range(len(self.options['plotSettings']['plot'])):
      self.colorMapCoordinates[pltindex] = None
      if 'y' in self.options['plotSettings']['plot'][pltindex].keys(): self.yCoordinates  = []
      if 'z' in self.options['plotSettings']['plot'][pltindex].keys(): self.zCoordinates  = []
      #if 'colorMap' in self.options['plotSettings']['plot'][pltindex].keys(): self.colorMapCoordinates = {}
    for pltindex in range(len(self.options['plotSettings']['plot'])):
      self.xCoordinates .append(self.options['plotSettings']['plot'][pltindex]['x'].split(','))
      self.sourceName.append(self.xCoordinates [pltindex][0].split('|')[0].strip())
      if 'y' in self.options['plotSettings']['plot'][pltindex].keys():
        self.yCoordinates .append(self.options['plotSettings']['plot'][pltindex]['y'].split(','))
        if self.yCoordinates [pltindex][0].split('|')[0] != self.sourceName[pltindex]: raise IOError(self.printTag+': ERROR -> Every plot can be linked to one Data only. x_cord source is ' + self.sourceName[pltindex] + '. Got y_cord source is' + self.yCoordinates [pltindex][0].split('|')[0])
      if 'z' in self.options['plotSettings']['plot'][pltindex].keys():
        self.zCoordinates .append(self.options['plotSettings']['plot'][pltindex]['z'].split(','))
        if self.zCoordinates [pltindex][0].split('|')[0] != self.sourceName[pltindex]: raise IOError(self.printTag+': ERROR -> Every plot can be linked to one Data only. x_cord source is ' + self.sourceName[pltindex] + '. Got z_cord source is' + self.zCoordinates [pltindex][0].split('|')[0])
      if 'colorMap' in self.options['plotSettings']['plot'][pltindex].keys():
        self.colorMapCoordinates[pltindex]=self.options['plotSettings']['plot'][pltindex]['colorMap'].split(',')
        #self.colorMapCoordinates.append(self.options['plotSettings']['plot'][pltindex]['colorMap'].split(','))
        if self.colorMapCoordinates[pltindex][0].split('|')[0] != self.sourceName[pltindex]: raise IOError(self.printTag+': ERROR -> Every plot can be linked to one Data only. x_cord source is ' + self.sourceName[pltindex] + '. Got colorMap_coordinates source is' + self.colorMapCoordinates[pltindex][0].split('|')[0])
      for pltindex in range(len(self.options['plotSettings']['plot'])):
        if 'interpPointsY' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['interpPointsY'] = '20'
        if 'interpPointsX' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['interpPointsX'] = '20'
        if 'interpolationType' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['interpolationType'] = 'linear'
        elif self.options['plotSettings']['plot'][pltindex]['interpolationType'] not in self.interpAvail: raise IOError(self.printTag+': ERROR -> surface interpolation unknown. Available are :' + str(self.interpAvail))
        if 'epsilon' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['epsilon'] = '2'
        if 'smooth' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['smooth'] = '0.0'
        if 'cmap' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['cmap'] = 'None'
#            else:             self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
        elif self.options['plotSettings']['plot'][pltindex]['cmap'] is not 'None' and self.options['plotSettings']['plot'][pltindex]['cmap'] not in self.mpl.cm.datad.keys(): raise('ERROR. The colorMap you specified does not exist... Available are ' + str(self.mpl.cm.datad.keys()))
        if 'interpolationTypeBackUp' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['interpolationTypeBackUp'] = 'nearest'
        elif self.options['plotSettings']['plot'][pltindex]['interpolationTypeBackUp'] not in self.interpAvail: raise IOError(self.printTag+': ERROR -> surface interpolation (BackUp) unknown. Available are :' + str(self.interpAvail))
    self.numberAggregatedOS = len(self.options['plotSettings']['plot'])
    # initialize here the base class
    OutStreamManager.initialize(self,inDict)
    #execute actions (we execute the actions here also because we can perform a check at runtime!!
    self.__executeActions()

  def localReadXML(self,xmlNode):
    """
      This Function is called from the base class, It reads the parameters that belong to a plot block
      @ In, xmlNode
      @ Out, filled data structure (self)
    """
    if not 'dim' in xmlNode.attrib.keys(): self.dim = 2
    else:                                  self.dim = int(xmlNode.attrib['dim'])
    if self.dim not in [2,3]: raise IOError(self.printTag+': ERROR -> Wrong dimension... 2D or 3D only!!! Got '+ str(self.dim)+'D')
    foundPlot = False
    for subnode in xmlNode:
      # if actions, read actions block
      if subnode.tag in ['actions']: self.__readPlotActions(subnode)
      if subnode.tag in ['plotSettings']:
        self.options[subnode.tag] = {}
        self.options[subnode.tag]['plot'] = []
        for subsub in subnode:
          if subsub.tag == 'plot':
            tempDict = {}
            foundPlot = True
            for subsubsub in subsub:
              if subsubsub.tag != 'kwargs': tempDict[subsubsub.tag] = subsubsub.text.strip()
              else:
                tempDict['attributes'] = {}
                for sss in subsubsub: tempDict['attributes'][sss.tag] = sss.text.strip()
            self.options[subnode.tag][subsub.tag].append(tempDict)
          else: self.options[subnode.tag][subsub.tag] = subsub.text.strip()
      if subnode.tag in 'title':
        self.options[subnode.tag] = {}
        for subsub in subnode: self.options[subnode.tag][subsub.tag] = subsub.text.strip()
        if 'text'     not in self.options[subnode.tag].keys(): self.options[subnode.tag]['text'    ] = xmlNode.attrib['name']
        if 'location' not in self.options[subnode.tag].keys(): self.options[subnode.tag]['location'] = 'center'
      if subnode.tag == 'figure_properties':
        self.options[subnode.tag] = {}
        for subsub in subnode: self.options[subnode.tag][subsub.tag] = subsub.text.strip()
    self.type = 'OutStreamPlot'
    if not 'plotSettings' in self.options.keys(): raise IOError(self.printTag+': ERROR -> For plot named ' + self.name + ' the plotSettings block IS REQUIRED!!')
    if not foundPlot: raise IOError(self.printTag+': ERROR -> For plot named'+ self.name + ', No plot section has been found in the plotSettings block!')
    self.outStreamTypes = []
    for pltindex in range(len(self.options['plotSettings']['plot'])):
      if not 'type' in self.options['plotSettings']['plot'][pltindex].keys(): raise IOError(self.printTag+': ERROR -> For plot named'+ self.name + ', No plot type keyword has been found in the plotSettings/plot block!')
      else:
        if self.availableOutStreamTypes[self.dim].count(self.options['plotSettings']['plot'][pltindex]['type']) == 0: print(self.printTag+': ERROR -> For plot named'+ self.name + ', type '+self.options['plotSettings']['plot'][pltindex]['type']+' is not among pre-defined plots! \n The OutstreamSystem will try to construct a call on the fly!!!')
        self.outStreamTypes.append(self.options['plotSettings']['plot'][pltindex]['type'])
    self.mpl = importlib.import_module("matplotlib")
    #exec('self.mpl =  importlib.import_module("matplotlib")')
    if self.debug: print(self.printTag+': ' +returnPrintPostTag('Message') + '-> matplotlib version is ' + str(self.mpl.__version__))
    if self.dim not in [2,3]: raise(self.printTag+': ERROR -> This Plot interface is able to handle 2D-3D plot only')
    if not disAvail: self.mpl.use('Agg')
    self.plt = importlib.import_module("matplotlib.pyplot")
    if self.dim == 3: from mpl_toolkits.mplot3d import Axes3D

  def addOutput(self):
    """
    Function to show and/or save a plot
    @ In,  None
    @ Out, None (Plot on the screen or on file/s)
    """
    # reactivate the figure
    self.fig = self.plt.figure(self.name)
    # fill the x_values,y_values,z_values dictionaries
    if not self.__fillCoordinatesFromSource():
      print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> Nothing to Plot Yet... Returning!!!!')
      return
    self.counter += 1
    if self.counter > 1:
      if self.dim == 2: self.fig.clear()
      else:
        if self.actPlot: self.plt3D.cla()
    # execute the actions again (we just cleared the figure)
    self.__executeActions()
    # start plotting.... we are here fort that...aren't we?
    # loop over the plots that need to be included in this figure
    for pltindex in range(len(self.outStreamTypes)):
      # If the number of plots to be shown in this figure > 1, hold the old ones (They are going to be shown together... because unity is much better than separation)
      if len(self.outStreamTypes) > 1: self.plt.hold(True)
      if 'xlabel' not in self.options['plotSettings'].keys():
        if self.dim == 2  : self.plt.xlabel('x')
        elif self.dim == 3: self.plt3D.set_xlabel('x')
      else:
        if self.dim == 2  : self.plt.xlabel(self.options['plotSettings']['xlabel'])
        elif self.dim == 3: self.plt3D.set_xlabel(self.options['plotSettings']['xlabel'])
      if 'ylabel' not in self.options['plotSettings'].keys():
        if self.dim == 2  : self.plt.ylabel('y')
        elif self.dim == 3: self.plt3D.set_ylabel('y')
      else:
        if self.dim == 2  : self.plt.ylabel(self.options['plotSettings']['ylabel'])
        elif self.dim == 3: self.plt3D.set_ylabel(self.options['plotSettings']['ylabel'])
      if 'zlabel' in self.options['plotSettings'].keys():
        if self.dim == 2  : print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> zlabel keyword does not make sense in 2-D Plots!')
        elif self.dim == 3 and self.zCoordinates : self.plt3D.set_zlabel(self.options['plotSettings']['zlabel'])
      elif self.dim == 3 and self.zCoordinates : self.plt3D.set_zlabel('z')
      # Let's start plotting
      #################
      #  SCATTER PLOT #
      #################
      if self.debug: print(self.printTag+': ' +returnPrintPostTag('Message') + '-> creating plot'+ self.name)
      if self.outStreamTypes[pltindex] == 'scatter':
        if 's' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['s'] = '20'
        if 'c' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['c'] = 'b'
        if 'marker' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['marker'] = 'o'
        if 'alpha' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['alpha']='None'
        if 'linewidths' not in self.options['plotSettings']['plot'][pltindex].keys():  self.options['plotSettings']['plot'][pltindex]['linewidths'] = 'None'
        for key in self.xValues[pltindex].keys():
          for x_index in range(len(self.xValues[pltindex][key])):
            for y_index in range(len(self.yValues[pltindex][key])):
              if self.dim == 2:
                if self.colorMapCoordinates[pltindex] != None:
                  if self.actcm: first = False
                  else         : first = True
                  self.actPlot = self.plt.scatter(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],s=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['s']),c=self.colorMapValues[pltindex][key],marker=(self.options['plotSettings']['plot'][pltindex]['marker']),alpha=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['alpha']),linewidths=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidths']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                  if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      if first:
                          m = self.mpl.cm.ScalarMappable(norm=self.actPlot.norm)
                          m.set_array(self.colorMapValues[pltindex][key])
                          self.actcm = self.fig.colorbar(m)
                          self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                      else:
                          self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                          self.actcm.draw_all()
                  else:
                      if first:
                          self.actPlot.cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap'])
                          m = self.mpl.cm.ScalarMappable(cmap=self.actPlot.cmap, norm=self.actPlot.norm)
                          m.set_array(self.colorMapValues[pltindex][key])
                          self.actcm = self.fig.colorbar(m)
                          self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                      else:
                          self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                          self.actcm.draw_all()
                else:
                  self.actPlot = self.plt.scatter(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],s=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['s']),c=(self.options['plotSettings']['plot'][pltindex]['c']),marker=(self.options['plotSettings']['plot'][pltindex]['marker']),alpha=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['alpha']),linewidths=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidths']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
              elif self.dim == 3:
                for z_index in range(len(self.zValues[pltindex][key])):
                  if self.colorMapCoordinates[pltindex] != None:
                    if self.actcm: first = False
                    else         : first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                        self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.zValues[pltindex][key][z_index],rasterized= True,s=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['s']),c=self.colorMapValues[pltindex][key],marker=(self.options['plotSettings']['plot'][pltindex]['marker']),alpha=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['alpha']),linewidths=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidths']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                        if first:
                            m = self.mpl.cm.ScalarMappable(norm=self.actPlot.norm)
                            m.set_array(self.colorMapValues[pltindex][key])
                            self.actcm = self.fig.colorbar(m)
                            self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                        else:
                            self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                            self.actcm.draw_all()
                    else:
                        self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.zValues[pltindex][key][z_index],rasterized= True,s=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['s']),c=self.colorMapValues[pltindex][key],marker=(self.options['plotSettings']['plot'][pltindex]['marker']),alpha=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['alpha']),linewidths=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidths']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                        if first:
                            self.actPlot.cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap'])
                            m = self.mpl.cm.ScalarMappable(cmap=self.actPlot.cmap, norm=self.actPlot.norm)
                            m.set_array(self.colorMapValues[pltindex][key])
                            self.actcm = self.fig.colorbar(m)
                            self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                        else:
                            self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                            self.actcm.draw_all()
                  else:
                    self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.zValues[pltindex][key][z_index],rasterized= True,s=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['s']),c=(self.options['plotSettings']['plot'][pltindex]['c']),marker=(self.options['plotSettings']['plot'][pltindex]['marker']),alpha=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['alpha']),linewidths=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidths']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
      #################
      #   LINE PLOT   #
      #################
      elif self.outStreamTypes[pltindex] == 'line':
        for key in self.xValues[pltindex].keys():
          for x_index in range(len(self.xValues[pltindex][key])):
            if self.colorMapCoordinates[pltindex] != None: self.options['plotSettings']['plot'][pltindex]['interpPointsX'] = str(max(200,len(self.xValues[pltindex][key][x_index])))
            for y_index in range(len(self.yValues[pltindex][key])):
              if self.dim == 2:
                if self.yValues[pltindex][key][y_index].size < 2: return
                xi,yi = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex],returnCoordinate=True)
                if self.colorMapCoordinates[pltindex] != None:
                  # if a color map has been added, we use a scattered plot instead...
                  if self.actcm: first = False
                  else         : first = True
                  self.actPlot = self.plt.scatter(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],c=self.colorMapValues[pltindex][key],**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                  if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      if first:
                          m = self.mpl.cm.ScalarMappable(norm=self.actPlot.norm)
                          m.set_array(self.colorMapValues[pltindex][key])
                          self.actcm = self.fig.colorbar(m)
                          self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                      else:
                          self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                          self.actcm.draw_all()
                  else:
                      if first:
                          self.actPlot.cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap'])
                          m = self.mpl.cm.ScalarMappable(cmap=self.actPlot.cmap, norm=self.actPlot.norm)
                          m.set_array(self.colorMapValues[pltindex][key])
                          self.actcm = self.fig.colorbar(m)
                          self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                      else:
                          self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                          self.actcm.draw_all()
                else: self.actPlot = self.plt.plot(xi,yi,**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
              elif self.dim == 3:
                for z_index in range(len(self.zValues[pltindex][key])):
                  if self.zValues[pltindex][key][z_index].size <= 3: return
                  if self.colorMapCoordinates[pltindex] != None:
                    # if a color map has been added, we use a scattered plot instead...
                    if self.actcm: first = False
                    else         : first = True
                    self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.zValues[pltindex][key][z_index],c=self.colorMapValues[pltindex][key],marker='_')
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                        if first:
                            m = self.mpl.cm.ScalarMappable(norm=self.actPlot.norm)
                            m.set_array(self.colorMapValues[pltindex][key])
                            self.actcm = self.fig.colorbar(m)
                            self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                        else:
                            self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                            self.actcm.draw_all()
                    else:
                        self.actPlot = self.plt3D.scatter(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.zValues[pltindex][key][z_index],c=self.colorMapValues[pltindex][key],cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']),marker='_')
                        if first:
                        #self.actPlot.cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap'])
                            m = self.mpl.cm.ScalarMappable(cmap=self.actPlot.cmap, norm=self.actPlot.norm)
                            m.set_array(self.colorMapValues[pltindex][key])
                            self.actcm = self.fig.colorbar(m)
                            self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                        else:
                            self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                            self.actcm.draw_all()
                  else: self.actPlot = self.plt3D.plot(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.zValues[pltindex][key][z_index],**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
      ##################
      # HISTOGRAM PLOT #
      ##################
      elif self.outStreamTypes[pltindex] == 'histogram':
        if 'bins' not in self.options['plotSettings']['plot'][pltindex].keys():
          if self.dim == 2: self.options['plotSettings']['plot'][pltindex]['bins'] = '10'
          else            : self.options['plotSettings']['plot'][pltindex]['bins'] = '4'
        if 'normed' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['normed'] = 'False'
        if 'weights' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['weights'] = 'None'
        if 'cumulative' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['cumulative'] = 'False'
        if 'histtype' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['histtype'] = 'bar'
        if 'align' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['align'] = 'mid'
        if 'orientation' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['orientation'] = 'vertical'
        if 'rwidth' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['rwidth'] = 'None'
        if 'log' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['log'] = 'None'
        if 'color' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['color'] = 'b'
        if 'stacked' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['stacked'] = 'None'
        for key in self.xValues[pltindex].keys():
          for x_index in range(len(self.xValues[pltindex][key])):
            try: colorss = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['color'])
            except: colorss = self.options['plotSettings']['plot'][pltindex]['color']
            if self.dim == 2:
              self.plt.hist(self.xValues[pltindex][key][x_index], bins=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['bins']), normed=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['normed']), weights=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['weights']),
                            cumulative=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cumulative']), histtype=self.options['plotSettings']['plot'][pltindex]['histtype'], align=self.options['plotSettings']['plot'][pltindex]['align'],
                            orientation=self.options['plotSettings']['plot'][pltindex]['orientation'], rwidth=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rwidth']), log=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['log']),
                            color=colorss, stacked=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['stacked']), **self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
            elif self.dim == 3:
              for y_index in range(len(self.yValues[pltindex][key])):
                hist, xedges, yedges = np.histogram2d(self.xValues[pltindex][key][x_index], self.yValues[pltindex][key][y_index], bins=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['bins']))
                elements = (len(xedges) - 1) * (len(yedges) - 1)
                if 'x_offset' in self.options['plotSettings']['plot'][pltindex].keys(): xoffset = float(self.options['plotSettings']['plot'][pltindex]['x_offset'])
                else: xoffset = 0.25
                if 'y_offset' in self.options['plotSettings']['plot'][pltindex].keys(): yoffset = float(self.options['plotSettings']['plot'][pltindex]['y_offset'])
                else: yoffset = 0.25
                if 'dx' in self.options['plotSettings']['plot'][pltindex].keys(): dxs = float(self.options['plotSettings']['plot'][pltindex]['dx'])
                else: dxs = (self.xValues[pltindex][key][x_index].max() - self.xValues[pltindex][key][x_index].min())/float(self.options['plotSettings']['plot'][pltindex]['bins'])
                if 'dy' in self.options['plotSettings']['plot'][pltindex].keys(): dys = float(self.options['plotSettings']['plot'][pltindex]['dy'])
                else: dys = (self.yValues[pltindex][key][y_index].max() - self.yValues[pltindex][key][y_index].min())/float(self.options['plotSettings']['plot'][pltindex]['bins'])
                xpos, ypos = np.meshgrid(xedges[:-1]+xoffset, yedges[:-1]+yoffset)
                self.actPlot = self.plt3D.bar3d(xpos.flatten(), ypos.flatten(), np.zeros(elements), dxs * np.ones_like(elements), dys * np.ones_like(elements), hist.flatten(), color=colorss, zsort='average', **self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
      ##################
      #    STEM PLOT   #
      ##################
      elif self.outStreamTypes[pltindex] == 'stem':
          if 'linefmt' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['linefmt'] = 'b-'
          if 'markerfmt' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['markerfmt'] = 'bo'
          if 'basefmt' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['basefmt'] = 'r-'
          for key in self.xValues[pltindex].keys():
            for x_index in range(len(self.xValues[pltindex][key])):
              for y_index in range(len(self.yValues[pltindex][key])):
                if self.dim == 2:
                  self.actPlot = self.plt.stem(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],linefmt=self.options['plotSettings']['plot'][pltindex]['linefmt'], markerfmt=self.options['plotSettings']['plot'][pltindex]['markerfmt'], basefmt=self.options['plotSettings']['plot'][pltindex]['linefmt'],**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                elif self.dim == 3:
                  #it is a basic stem plot constructed using a standard line plot. For now we do not use the previous defined keywords...
                  for z_index in range(len(self.zValues[pltindex][key])):
                    for xx,yy,zz in zip(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.zValues[pltindex][key][z_index]): self.plt3D.plot([xx,xx],[yy,yy],[0,zz], '-')
      ##################
      #    STEP PLOT   #
      ##################
      elif self.outStreamTypes[pltindex] == 'step':
        if self.dim == 2:
          if 'where' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['where'] = 'mid'
          for key in self.xValues[pltindex].keys():
            for x_index in range(len(self.xValues[pltindex][key])):
              if self.xValues[pltindex][key][x_index].size < 2: xi = self.xValues[pltindex][key][x_index]
              else: xi = np.linspace(self.xValues[pltindex][key][x_index].min(),self.xValues[pltindex][key][x_index].max(),ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['interpPointsX']))
              for y_index in range(len(self.yValues[pltindex][key])):
                if self.yValues[pltindex][key][y_index].size  <= 3: return
                yi = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex])
                self.actPlot = self.plt.step(xi,yi,where=self.options['plotSettings']['plot'][pltindex]['where'],**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
        elif self.dim == 3:
          print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> step Plot not available in 3D')
          return
      ########################
      #    PSEUDOCOLOR PLOT  #
      ########################
      elif self.outStreamTypes[pltindex] == 'pseudocolor':
        if self.dim == 2:
          for key in self.xValues[pltindex].keys():
            for x_index in range(len(self.xValues[pltindex][key])):
              for y_index in range(len(self.yValues[pltindex][key])):
                if not self.colorMapCoordinates:
                  print('STREAM MANAGER: pseudocolor Plot needs coordinates for color map... Returning without plotting')
                  return
                for z_index in range(len(self.colorMapValues[pltindex][key])):
                  if self.colorMapValues[pltindex][key][z_index].size <= 3: return
                  xig, yig, Ci = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex],z = self.colorMapValues[pltindex][key][z_index],returnCoordinate=True)
                  if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      self.actPlot = self.plt.pcolormesh(xig,yig,ma.masked_where(np.isnan(Ci),Ci), **self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                      m = self.mpl.cm.ScalarMappable(norm=self.actPlot.norm)
                  else:
                      self.actPlot = self.plt.pcolormesh(xig,yig,ma.masked_where(np.isnan(Ci),Ci),cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']), **self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                      m = self.mpl.cm.ScalarMappable(cmap=self.actPlot.cmap, norm=self.actPlot.norm)
                  m.set_array(ma.masked_where(np.isnan(Ci),Ci))
                  actcm = self.fig.colorbar(m)
                  actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
        elif self.dim == 3:
          print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> pseudocolor Plot is considered a 2D plot, not a 3D!')
          return
      ########################
      #     SURFACE PLOT     #
      ########################
      elif self.outStreamTypes[pltindex] == 'surface':
        if self.dim == 2:
          print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> surface Plot is NOT available for 2D plots, IT IS A 3D!')
          return
        elif self.dim == 3:
          if 'rstride' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['rstride'] = '1'
          if 'cstride' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['cstride'] = '1'
          if 'antialiased' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['antialiased']='False'
          if 'linewidth' not in self.options['plotSettings']['plot'][pltindex].keys():  self.options['plotSettings']['plot'][pltindex]['linewidth'] = '0'
          for key in self.xValues[pltindex].keys():
            for x_index in range(len(self.xValues[pltindex][key])):
              for y_index in range(len(self.yValues[pltindex][key])):
                for z_index in range(len(self.zValues[pltindex][key])):
                  if self.zValues[pltindex][key][z_index].size <= 3: return
                  if self.colorMapCoordinates[pltindex] != None: xig, yig, Ci = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex],z = self.colorMapValues[pltindex][key][z_index],returnCoordinate=True)
                  xig, yig, zi = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex],z = self.zValues[pltindex][key][z_index],returnCoordinate=True)
                  if self.colorMapCoordinates[pltindex] != None:
                    if self.actcm: first = False
                    else         : first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None': self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                    self.actPlot = self.plt3D.plot_surface(xig,yig,ma.masked_where(np.isnan(zi),zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']),facecolors=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap'])(ma.masked_where(np.isnan(Ci),Ci)),cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']),linewidth= ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidth']),antialiased=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['antialiased']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                    if first:
                        self.actPlot.cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap'])
                        m = self.mpl.cm.ScalarMappable(cmap=self.actPlot.cmap, norm=self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                    else:
                        self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                  else:
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                        self.actPlot = self.plt3D.plot_surface(xig,yig,ma.masked_where(np.isnan(zi),zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']),linewidth= ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidth']),antialiased=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['antialiased']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                        if 'color' in self.options['plotSettings']['plot'][pltindex].get('attributes',{}).keys():
                            self.actPlot.set_color = self.options['plotSettings']['plot'][pltindex].get('attributes',{})['color']
                        else:
                            self.actPlot.set_color = 'blue'
                    else:
                        self.actPlot = self.plt3D.plot_surface(xig,yig,ma.masked_where(np.isnan(zi),zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']),cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']),linewidth= ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['linewidth']),antialiased=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['antialiased']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
      ########################
      #   TRI-SURFACE PLOT   #
      ########################
      elif self.outStreamTypes[pltindex] == 'tri-surface':
        if self.dim == 2:
          print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> TRI-surface Plot is NOT available for 2D plots, IT IS A 3D!')
          return
        elif self.dim == 3:
          if 'color' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['color'] = 'b'
          if 'shade' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['shade']='False'
          for key in self.xValues[pltindex].keys():
            for x_index in range(len(self.xValues[pltindex][key])):
              for y_index in range(len(self.yValues[pltindex][key])):
                for z_index in range(len(self.zValues[pltindex][key])):
                  metric = (self.xValues[pltindex][key][x_index]**2+self.yValues[pltindex][key][y_index]**2)**0.5
                  metricIndeces = np.argsort(metric)
                  xs = np.zeros(self.xValues[pltindex][key][x_index].shape)
                  ys = np.zeros(self.yValues[pltindex][key][y_index].shape)
                  zs = np.zeros(self.zValues[pltindex][key][z_index].shape)
                  for sindex in range(len(metricIndeces)):
                    xs[sindex]=self.xValues[pltindex][key][x_index][metricIndeces[sindex]]
                    ys[sindex]=self.yValues[pltindex][key][y_index][metricIndeces[sindex]]
                    zs[sindex]=self.zValues[pltindex][key][z_index][metricIndeces[sindex]]
                  if self.zValues[pltindex][key][z_index].size <= 3: return
                  if self.colorMapCoordinates[pltindex] != None:
                    if self.actcm: first = False
                    else         : first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None': self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                    self.actPlot = self.plt3D.plot_trisurf(xs,ys,zs, color = self.options['plotSettings']['plot'][pltindex]['color'],cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']),shade= ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['shade']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                    if first:
                        self.actPlot.cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap'])
                        m = self.mpl.cm.ScalarMappable(cmap=self.actPlot.cmap, norm=self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                    else:
                        self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                  else:
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                      self.actPlot = self.plt3D.plot_trisurf(xs,ys,zs, color = self.options['plotSettings']['plot'][pltindex]['color'],shade= ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['shade']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                    else:
                      self.actPlot = self.plt3D.plot_trisurf(xs,ys,zs, color = self.options['plotSettings']['plot'][pltindex]['color'],cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']),shade= ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['shade']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
      ########################
      #    WIREFRAME  PLOT   #
      ########################
      elif self.outStreamTypes[pltindex] == 'wireframe':
        if self.dim == 2:
          print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> wireframe Plot is NOT available for 2D plots, IT IS A 3D!')
          return
        elif self.dim == 3:
          if 'rstride' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['rstride'] = '1'
          if 'cstride' not in self.options['plotSettings']['plot'][pltindex].keys(): self.options['plotSettings']['plot'][pltindex]['cstride'] = '1'
          for key in self.xValues[pltindex].keys():
            for x_index in range(len(self.xValues[pltindex][key])):
              for y_index in range(len(self.yValues[pltindex][key])):
                for z_index in range(len(self.zValues[pltindex][key])):
                  if self.zValues[pltindex][key][z_index].size <= 3: return
                  if self.colorMapCoordinates[pltindex] != None: xig, yig, Ci = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex],z = self.colorMapValues[pltindex][key][z_index],returnCoordinate=True)
                  xig, yig, zi = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex],z = self.zValues[pltindex][key][z_index],returnCoordinate=True)
                  if self.colorMapCoordinates[pltindex] != None:
                    print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> Currently, ax.plot_wireframe() in MatPlotLib version: '+self.mpl.__version__+' does not support a colormap! Wireframe plotted on a surface plot...')
                    if self.actcm: first = False
                    else         : first = True
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None': self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                    self.actPlot = self.plt3D.plot_wireframe(xig,yig,ma.masked_where(np.isnan(zi),zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']), cstride=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                    self.actPlot = self.plt3D.plot_surface(xig,yig,ma.masked_where(np.isnan(zi),zi),alpha=0.4, rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']), cstride=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                    if first:
                        m = self.mpl.cm.ScalarMappable(cmap=self.actPlot.cmap, norm=self.actPlot.norm)
                        m.set_array(self.colorMapValues[pltindex][key])
                        self.actcm = self.fig.colorbar(m)
                        self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                    else:
                        self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                        self.actcm.draw_all()
                  else:
                    if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                        self.actPlot = self.plt3D.plot_wireframe(xig,yig,ma.masked_where(np.isnan(zi),zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                        if 'color' in self.options['plotSettings']['plot'][pltindex].get('attributes',{}).keys():
                            self.actPlot.set_color = self.options['plotSettings']['plot'][pltindex].get('attributes',{})['color']
                        else:
                            self.actPlot.set_color = 'blue'
                    else:
                        self.actPlot = self.plt3D.plot_wireframe(xig,yig,ma.masked_where(np.isnan(zi),zi), rstride = ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['rstride']), cstride=ast.literal_eval(self.options['plotSettings']['plot'][pltindex]['cstride']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))

      ########################
      #     CONTOUR   PLOT   #
      ########################
      elif self.outStreamTypes[pltindex] == 'contour' or self.outStreamTypes[pltindex] == 'filledContour':
        if self.dim == 2:
          if 'number_bins' in self.options['plotSettings']['plot'][pltindex].keys(): nbins = int(self.options['plotSettings']['plot'][pltindex]['number_bins'])
          else: nbins = 5
          for key in self.xValues[pltindex].keys():
            if not self.colorMapCoordinates:
              print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> ' +self.outStreamTypes[pltindex]+' Plot needs coordinates for color map... Returning without plotting')
              return
            for x_index in range(len(self.xValues[pltindex][key])):
              for y_index in range(len(self.yValues[pltindex][key])):
                for z_index in range(len(self.colorMapValues[pltindex][key])):
                  if self.actcm: first = False
                  else         : first = True
                  xig, yig, Ci = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex],z = self.colorMapValues[pltindex][key][z_index],returnCoordinate=True)
                  if self.outStreamTypes[pltindex] == 'contour':
                      if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                          if 'color' in self.options['plotSettings']['plot'][pltindex].get('attributes',{}).keys():
                              color = self.options['plotSettings']['plot'][pltindex].get('attributes',{})['color']
                          else:
                              color = 'blue'
                          self.actPlot = self.plt.contour(xig,yig,ma.masked_where(np.isnan(Ci),Ci),nbins,colors=color,**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                      else:
                          self.actPlot = self.plt.contour(xig,yig,ma.masked_where(np.isnan(Ci),Ci),nbins,**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                  else:
                      if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None': self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                      self.actPlot = self.plt.contourf(xig,yig,ma.masked_where(np.isnan(Ci),Ci),nbins,**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                  self.plt.clabel(self.actPlot,inline=1, fontsize=10)
                  if first:
                      self.actcm = self.plt.colorbar(self.actPlot, shrink=0.8, extend='both')
                      self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                  else:
                      self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                      self.actcm.draw_all()
        elif self.dim == 3:
          print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> contour/filledContour is a 2-D plot, where x,y are the surface coordinates and colorMap vector is the array to visualize!\n               contour3D/filledContour3D are 3-D! ')
          return
      elif self.outStreamTypes[pltindex] == 'contour3D' or self.outStreamTypes[pltindex] == 'filledContour3D':
        if self.dim == 2:
          print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> contour3D/filledContour3D Plot is NOT available for 2D plots, IT IS A 2D! Check "contour/filledContour"!')
          return
        elif self.dim == 3:
          if 'number_bins' in self.options['plotSettings']['plot'][pltindex].keys(): nbins = int(self.options['plotSettings']['plot'][pltindex]['number_bins'])
          else: nbins = 5
          if 'extend3D' in self.options['plotSettings']['plot'][pltindex].keys(): ext3D = bool(self.options['plotSettings']['plot'][pltindex]['extend3D'])
          else: ext3D = False
          for key in self.xValues[pltindex].keys():
            for x_index in range(len(self.xValues[pltindex][key])):
              for y_index in range(len(self.yValues[pltindex][key])):
                for z_index in range(len(self.colorMapValues[pltindex][key])):
                  if self.actcm: first = False
                  else         : first = True
                  xig, yig, Ci = interpolateFunction(self.xValues[pltindex][key][x_index],self.yValues[pltindex][key][y_index],self.options['plotSettings']['plot'][pltindex],z = self.colorMapValues[pltindex][key][z_index],returnCoordinate=True)
                  if self.outStreamTypes[pltindex] == 'contour3D':
                      if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None':
                          if 'color' in self.options['plotSettings']['plot'][pltindex].get('attributes',{}).keys():
                              color = self.options['plotSettings']['plot'][pltindex].get('attributes',{})['color']
                          else:
                              color = 'blue'
                          self.actPlot = self.plt3D.contour3D(xig,yig,ma.masked_where(np.isnan(Ci),Ci), nbins,colors=color,extend3d=ext3D,**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                      else:
                          self.actPlot = self.plt3D.contour3D(xig,yig,ma.masked_where(np.isnan(Ci),Ci),nbins,extend3d=ext3D, cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                  else:
                      if self.options['plotSettings']['plot'][pltindex]['cmap'] == 'None': self.options['plotSettings']['plot'][pltindex]['cmap'] = 'jet'
                      self.actPlot = self.plt3D.contourf3D(xig,yig,ma.masked_where(np.isnan(Ci),Ci),nbins,extend3d=ext3D, cmap=self.mpl.cm.get_cmap(name=self.options['plotSettings']['plot'][pltindex]['cmap']),**self.options['plotSettings']['plot'][pltindex].get('attributes',{}))
                  self.plt.clabel(self.actPlot, inline=1, fontsize=10)
                  if first:
                      self.actcm = self.plt.colorbar(self.actPlot, shrink=0.8, extend='both')
                      self.actcm.set_label(self.colorMapCoordinates[pltindex][0].split('|')[-1].replace(')',''))
                  else:
                      self.actcm.set_clim(vmin=min(self.colorMapValues[pltindex][key][-1]),vmax=max(self.colorMapValues[pltindex][key][-1]))
                      self.actcm.draw_all()
      else:
        # Let's try to "write" the code for the plot on the fly
        print(self.printTag+': ' +returnPrintPostTag('Warning') + '-> Try to create a not-predifined plot of type ' + self.outStreamTypes[pltindex] +'. If it does not work check manual and/or relavite matplotlib method specification.')
        command_args = ' '
        import CustomCommandExecuter as execcommand
        for kk in self.options['plotSettings']['plot'][pltindex]:
          if kk != 'attributes' and kk != self.outStreamTypes[pltindex]:
            if command_args != ' ': prefix = ','
            else: prefix = ''
            try: command_args = command_args + prefix + kk + '=' + str(ast.literal_eval(self.options['plotSettings']['plot'][pltindex][kk]))
            except:command_args = command_args + prefix + kk + '="' + str(self.options['plotSettings']['plot'][pltindex][kk])+'"'
        try:
          if self.dim == 2:  execcommand.execCommand('self.actPlot = self.plt3D.' + self.outStreamTypes[pltindex] + '(' + command_args + ')',self)
          elif self.dim == 3:execcommand.execCommand('self.actPlot = self.plt3D.' + self.outStreamTypes[pltindex] + '(' + command_args + ')',self)
        except ValueError as ae:
          raise Exception(self.printTag+': ERROR -> <'+str(ae)+'> -> in execution custom plot "' + self.outStreamTypes[pltindex] + '" in Plot ' + self.name + '.\nSTREAM MANAGER: ERROR -> command has been called in the following way: ' + 'self.plt.' + self.outStreamTypes[pltindex] + '(' + command_args + ')')
    # SHOW THE PICTURE
    self.plt.draw()
    #self.plt3D.draw(self.fig.canvas.renderer)
    if 'screen' in self.options['how']['how'].split(',') and disAvail:
      def handle_close(event):
        self.fig.canvas.stop_event_loop()
        print('Closed Figure')
      self.fig.canvas.mpl_connect('close_event',handle_close)
      self.fig.show()
      #if blockFigure: self.fig.ginput(n=-1, timeout=-1, show_clicks=False)
    for i in range(len(self.options['how']['how'].split(','))):
      if self.options['how']['how'].split(',')[i].lower() != 'screen':
        if not self.overwrite: prefix = str(self.counter) + '-'
        else: prefix = ''
        self.plt.savefig(prefix + self.name+'_' + str(self.outStreamTypes).replace("'", "").replace("[", "").replace("]", "").replace(",", "-").replace(" ", "") +'.'+self.options['how']['how'].split(',')[i], format=self.options['how']['how'].split(',')[i])

class OutStreamPrint(OutStreamManager):
  def __init__(self):
    OutStreamManager.__init__(self)
    self.type = 'OutStreamPrint'
    self.printTag = returnPrintTag('OUTSTREAM PRINT')
    self.availableOutStreamTypes = ['csv']
    OutStreamManager.__init__(self)
    self.sourceName   = []
    self.sourceData   = None
    self.variables    = None

  def localAddInitParams(self,tempDict):
    for index in range(len(self.sourceName)): tempDict['Source Name '+str(index)+' :'] = self.sourceName[index]
    if self.variables:
      for index in range(len(self.variables)): tempDict['Variable Name '+str(index)+' :'] = self.variables[index]

  def initialize(self,inDict):
    # the linking to the source is performed in the base class initialize method
    OutStreamManager.initialize(self,inDict)

  def localReadXML(self,xmlNode):
    self.type = 'OutStreamPrint'
    for subnode in xmlNode:
      if subnode.tag == 'source': self.sourceName = subnode.text.split(',')
      else:self.options[subnode.tag] = subnode.text
    if 'type' not in self.options.keys(): raise(self.printTag+': ERROR -> type tag not present in Print block called '+ self.name)
    if self.options['type'] not in self.availableOutStreamTypes : raise(self.printTag+': ERROR -> Print type ' + self.options['type'] + ' not available yet. ')
    if 'variables' in self.options.keys(): self.variables = self.options['variables']

  def addOutput(self):
    if self.variables: dictOptions = {'filenameroot':self.name,'variables':self.variables}
    else             : dictOptions = {'filenameroot':self.name}
    for index in range(len(self.sourceName)):
      if not self.sourceData[index].isItEmpty(): self.sourceData[index].printCSV(dictOptions)

"""
 Interface Dictionary (factory) (private)
"""
__base                     = 'OutStreamManager'
__interFaceDict            = {}
__interFaceDict['Plot'   ] = OutStreamPlot
__interFaceDict['Print'  ] = OutStreamPrint
__knownTypes              = __interFaceDict.keys()

def knownTypes():
  return __knownTypes

def returnInstance(Type):
  """
  function used to generate a OutStream class
  @ In, Type : OutStream type
  @ Out,Instance of the Specialized OutStream class
  """
  try: return __interFaceDict[Type]()
  except KeyError: raise NameError('not known '+__base+' type '+Type)

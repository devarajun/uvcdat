#!/usr/bin/env python
# Adapted for numpy/ma/cdms2 by convertcdms.py
#
# The VCS Canvas API controls -  canvas module
#
###############################################################################
#                                                                             #
# Module:       canvas module                                                 #
#                                                                             #
# Copyright:    "See file Legal.htm for copyright information."               #
#                                                                             #
# Authors:      PCMDI Software Team                                           #
#               Lawrence Livermore National Laboratory:                       #
#               support@pcmdi.llnl.gov                                        #
#                                                                             #
# Description:  PCMDI's VCS Canvas is used to display plots and to create and #
#               run animations.  It is always visible on the screen in a      #
#               landscape (width exceeding height), portrait (height exceeding#
#               width), or full-screen mode.                                  #
#                                                                             #
# Version:      4.0                                                           #
#                                                                             #
###############################################################################

"""Canvas: the class representing a vcs drawing window
Normally, created by vcs.init()
Contains the method plot.
"""
import __main__
import warnings
#import Tkinter
from pauser import pause
import thread
import numpy.ma, MV2
import numpy, cdutil
from queries import *
import boxfill, isofill, isoline, outfill, outline, taylor, meshfill, projection
import vector, continents, line, marker, fillarea
import texttable, textorientation, textcombined, template, colormap
import unified1D
#import colormapgui as _colormapgui
#import canvasgui as _canvasgui
import displayplot
import vtk
from VTKPlots import VTKVCSBackend
from weakref import WeakSet, WeakKeyDictionary
import time

#import animationgui as _animationgui
#import graphicsmethodgui as _graphicsmethodgui
#import templateeditorgui as _templateeditorgui
#import gui_template_editor as _gui_template_editor
#import pagegui as _pagegui
#import projectiongui as _projectiongui
from error import vcsError
import cdms2
import copy
import cdtime,vcs
import os
import sys
import random
import genutil
from cdms2.grid import AbstractRectGrid
import shutil, inspect
import VCS_validation_functions
import AutoAPI
from xmldocs import plot_keywords_doc,graphics_method_core,axesconvert,xaxisconvert,yaxisconvert, plot_1D_input, plot_2D_input, plot_output, plot_2_1D_input, create_GM_input, get_GM_input, boxfill_output, isofill_output, isoline_output, yxvsx_output, xyvsy_output, xvsy_output, scatter_output, outfill_output, outline_output, plot_2_1D_options
# Flag to set if the initial attributes file has aready been read in
called_initial_attributes_flg = 0
gui_canvas_closed = 0
canvas_closed = 0
#import Pmw
import vcsaddons
import vcs.manageElements
import configurator
from projection import round_projections

class SIGNAL(object):

    def __init__( self, name = None ):
        self._functions = WeakSet()
        self._methods = WeakKeyDictionary()
        self._name = name

    def __call__(self, *args, **kargs):
        # Call handler functions
        for func in self._functions:
            func(*args, **kargs)

        # Call handler methods
        for obj, funcs in self._methods.items():
            for func in funcs:
                func(obj, *args, **kargs)

    def connect(self, slot):
        if inspect.ismethod(slot):
            if slot.__self__ not in self._methods:
                self._methods[slot.__self__] = set()

            self._methods[slot.__self__].add(slot.__func__)

        else:
            self._functions.add(slot)

    def disconnect(self, slot):
        if inspect.ismethod(slot):
            if slot.__self__ in self._methods:
                self._methods[slot.__self__].remove(slot.__func__)
        else:
            if slot in self._functions:
                self._functions.remove(slot)

    def clear(self):
        self._functions.clear()
        self._methods.clear()

def dictionarytovcslist(dictionary,name):
    for k in dictionary.keys():
        if not isinstance(k,(float,int,long)):
            raise Exception,'Error, vcs list must have numbers only as keys'
    _vcs.dictionarytovcslist(dictionary,name)
    return None

def _determine_arg_list(g_name, actual_args):
    "Determine what is in the argument list for plotting graphics methods"

    itemplate_name = 2
    igraphics_method = 3
    igraphics_option = 4


    # Note: Set default graphics method to 'default', which is invalid.
    # If it is not modified in this routine, it will be filled in later
    # in _reconstruct_tv after the grid type is established.
    #
    ## Xtrargs - {} - added by C.Doutriaux, needed for projection object passed
    ## Need to be passed as keyword later
    arglist = [None, None, 'default', 'default', 'default',{}]
    arghold = []
    argstring=[]
    args = actual_args
    found_slabs = 0
    for i in range(len(args)):
      if isinstance(args[i],str):
          argstring.append(args[i])
      else:
          try:
             possible_slab = cdms2.asVariable (args[i], 0)
             if hasattr( possible_slab, 'iscontiguous' ):
                 if not possible_slab.iscontiguous():
                     #this seems to loose the id...
                     saved_id = possible_slab.id
                     possible_slab = possible_slab.ascontiguousarray()
                     possible_slab.id = saved_id
             arglist[found_slabs] = possible_slab
             if found_slabs == 2:
                 raise vcsError, "Too many slab arguments."
             found_slabs = found_slabs + 1
          except cdms2.CDMSError:
              arghold.append(args[i])

    #
    # Now find the template
    #
    args = arghold
    arghold = []
    found_template = 0
    for i in range(len(args)):
       if (istemplate(args[i])):
          if found_template:
             raise vcsError, 'You can only specify one template object.'
          arglist[itemplate_name] = args[i].name
          found_template = found_template + 1
       else:
          arghold.append(args[i])
    #
    # Now find the graphics method
    #
    args = arghold
    arghold = []
    found_graphics_method = 0
    for i in range(len(args)):
        if (isgraphicsmethod(args[i])):
            if found_graphics_method:
                raise vcsError,'You can only specify one graphics method.'
            arglist[igraphics_method] = graphicsmethodtype(args[i])
            arglist[igraphics_option] = args[i].name
            found_graphics_method = found_graphics_method + 1
        elif (isline(args[i])):
            if found_graphics_method:
                raise vcsError,'You can only specify one graphics method.'
            arglist[igraphics_method] = 'line'
            arglist[igraphics_option] = args[i].name
            found_graphics_method = found_graphics_method + 1
        elif (ismarker(args[i])):
            if found_graphics_method:
                raise vcsError,'You can only specify one graphics method.'
            arglist[igraphics_method] = 'marker'
            arglist[igraphics_option] = args[i].name
            found_graphics_method = found_graphics_method + 1
        elif (isfillarea(args[i])):
            if found_graphics_method:
                raise vcsError,'You can only specify one graphics method.'
            arglist[igraphics_method] = 'fillarea'
            arglist[igraphics_option] = args[i].name
            found_graphics_method = found_graphics_method + 1
        elif (istext(args[i])):
            if found_graphics_method:
                raise vcsError,'You can only specify one graphics method.'
            arglist[igraphics_method] = 'text'
            arglist[igraphics_option] = args[i].Tt_name + ':::' + args[i].To_name
            found_graphics_method = found_graphics_method + 1
        elif (isprojection(args[i])):
            arglist[5]['projection']=args[i].name
        elif isinstance(args[i],vcsaddons.core.VCSaddon):
            if found_graphics_method:
                raise vcsError,'You can only specify one graphics method.'
            arglist[igraphics_method] = graphicsmethodtype(args[i])
            arglist[igraphics_option] = args[i].name
            found_graphics_method = found_graphics_method + 1
        else:
            raise vcsError, "Unknown type %s of argument to plotting command." %\
                                        type(args[i])
    if g_name is not None:
        arglist[igraphics_method] = g_name

# Now install the string arguments, left to right.
    if found_template == 0:
        if len(argstring) > 0:
           arglist[itemplate_name] = argstring[0]
           del argstring[0]
    if found_graphics_method == 0 and g_name is None:
        if len(argstring) > 0 :
           arglist[igraphics_method] = argstring[0]
           del argstring[0]

# Check for various errors
    if len(argstring) >= 1:
        arglist[igraphics_option] = argstring[0]
        del argstring[0]

    if len(argstring) > 0:
        if g_name is None:
            raise vcsError, "Error in argument list for vcs plot command."
        else:
            raise vcsError, "Error in argument list for vcs %s  command." % g_name

    if isinstance(arglist[igraphics_method],vcsaddons.core.VCSaddon):
        if found_slabs!=arglist[igraphics_method].g_nslabs:
            raise vcsError, "%s requires %i slab(s)" % (arglist[igraphics_method].g_name,arglist[igraphics_method].g_nslabs)
    else:
        if arglist[igraphics_method].lower() in ( 'scatter', 'vector', 'xvsy', 'stream', 'glyph', '3d_vector', '3d_dual_scalar' ):
            if found_slabs != 2:
                raise vcsError, "Graphics method %s requires 2 slabs." % arglist[igraphics_method]
        elif arglist[igraphics_method].lower() == 'meshfill':
            if found_slabs == 0:
                raise vcsError, "Graphics method requires at least 1 slab."
            elif found_slabs == 1:
                g=arglist[0].getGrid()
                if not isinstance(g, (cdms2.gengrid.AbstractGenericGrid,cdms2.hgrid.AbstractCurveGrid,cdms2.grid.TransientRectGrid)):
                    raise vcsError, "Meshfill requires 2 slab if first slab doesn't have a Rectilinear, Curvilinear or Generic Grid type"
        elif ((arglist[igraphics_method] == 'continents') or
              (arglist[igraphics_method] == 'line') or
              (arglist[igraphics_method] == 'marker') or
              (arglist[igraphics_method] == 'fillarea') or
              (arglist[igraphics_method] == 'text')):
            if found_slabs != 0:
                raise vcsError, "Continents or low-level primative methods requires 0 slabs."
        elif arglist[igraphics_method].lower()=='default':
            pass                            # Check later
        else:
            if found_slabs != 1 and not(found_slabs == 2 and arglist[igraphics_method].lower()=="1d"):
                raise vcsError, "Graphics method %s requires 1 slab." % arglist[igraphics_method]
    if isinstance(arglist[3],str): arglist[3]=arglist[3].lower()
    return arglist

def _process_keyword(obj, target, source, keyargs, default=None):
    """ Set obj.target from:
    - keyargs[source]
    - default
    - obj.source
    in that order."""
    arg = keyargs.get(source)
    if arg is not None:
        setattr(obj, target, arg)
    elif default is not None:
        setattr(obj, target, default)
    elif hasattr(obj, source):
        setattr(obj, target, getattr(obj, source))
    return arg

def finish_queued_X_server_requests( self ):
    """ Wait for the X server to execute all pending events.

        If working with C routines, then use BLOCK_X_SERVER
        found in the VCS module routine to stop the X server
        from continuing. Thus, eliminating the asynchronous
        errors.
    """
    x_num = self.canvas.xpending()
    count = 0
    while x_num != 0:
        x_num = self.canvas.xpending()
        count += 1
        # Move on already! The X sever must be completed by this point!
        # If count of 1000 is reached, then discard all events from
        # this point on in the queue.
        if count > 1000:
           self.canvas.xsync_discard()
           break

class Canvas(object,AutoAPI.AutoAPI):
    """
 Function: Canvas                     # Construct a VCS Canvas class Object

 Description of Function:
    Construct the VCS Canas object. There can only be at most 8 VCS
    Canvases open at any given time.

 Example of Use:
    a=vcs.Canvas()                    # This examples constructs a VCS Canvas
"""
    #############################################################################
    #                                                                           #
    # Set attributes for VCS Canvas Class (i.e., set VCS Canvas Mode).          #
    #                                                                           #
    #############################################################################
    __slots__ = [
        '_mode',
        '_pause_time',
        '_viewport',
        '_worldcoordinate',
        '_winfo_id',
        '_varglist',
	'_canvas_gui',
        '_animate_info',
        '_canvas_template_editor',
        '_isplottinggridded',
        '_user_actions_names',
        '_user_actions',
        '_animate',
        '_canvas',
        'mode',
        'pause_time',
        'viewport',
        'worldcoordinate',
        'winfo_id',
        'varglist',
        'canvas_gui'
        'animate_info',
        'canvas_template_editor',
        'isplottinggridded',
        'ratio',
        'canvas',
        'animate',
        'user_actions_names',
        'user_actions',
        'size',
        'canvas_guianimate_info',
        ]

#     def applicationFocusChanged(self, old, current ):
#         self.backend.applicationFocusChanged()

    def _set_user_actions_names(self,value):
        value=VCS_validation_functions.checkListElements(self,'user_actions_names',value,VCS_validation_functions.checkString)
        self._user_actions_names = value
        while len(self._user_actions)<len(self._user_actions_names):
            self._user_actions.append(self._user_actions[-1])
    def _get_user_actions_names(self):
        return self._user_actions_names
    user_actions_names = property(_get_user_actions_names,_set_user_actions_names)

    def _set_user_actions(self,value):
        value=VCS_validation_functions.checkListElements(self,'user_actions_names',value,VCS_validation_functions.checkCallable)
        self._user_actions = value
        while len(self._user_actions)<len(self._user_actions_names):
            self._user_actions.append(self._user_actions[-1])
    def _get_user_actions(self):
        return self._user_actions
    user_actions = property(_get_user_actions,_set_user_actions)

    def _setmode(self,value):
        value=VCS_validation_functions.checkInt(self,'mode',value,minvalue=0,maxvalue=1)
        self._mode=value
    def _getmode(self):
        return self._mode
    mode = property(_getmode,_setmode)

    def _setwinfo_id(self,value):
        value=VCS_validation_functions.checkInt(self,'winfo_id',value)
        self._winfo_id=value
    def _getwinfo_id(self):
        return self._winfo_id
    winfo_id = property(_getwinfo_id,_setwinfo_id)

    def _setvarglist(self,value):
        value=VCS_validation_functions.checkListElements(self,'varglist',value,VCS_validation_functions.checkCallable)
        self._varglist = value
    def _getvarglist(self):
        return self._varglist
    varglist = property(_getvarglist,_setvarglist)

    def _setcanvas_gui(self,value):
        self._canvas_gui = value
    def _getcanvas_gui(self):
        return self._canvas_gui
    canvas_gui = property(_getcanvas_gui,_setcanvas_gui)

    def _setcanvas(self,value):
        raise vcsError, "Error, canvas is not an attribute you can set"
    def _getcanvas(self):
        return self._canvas
    canvas = property(_getcanvas,_setcanvas)

    def _setanimate(self,value):
        raise vcsError, "Error, animate is not an attribute you can set"
    def _getanimate(self):
        return self._animate
    animate = property(_getanimate,_setanimate)

    def _setpausetime(self,value):
        value=VCS_validation_functions.checkInt(self,'pause_time',value)
        self._pause_time = value
    def _getpausetime(self):
        return self._pause_time
    pause_time = property(_getpausetime,_setpausetime)

    def _setviewport(self,value):
        if not isinstance(value,list) and not len(value)==4:
            raise vcsError,  "viewport must be of type list and have four values ranging between [0,1]."
        for v in range(4):
            if not 0.<=value[v]<=1.:
                raise vcsError,  "viewport must be of type list and have four values ranging between [0,1]."
        self._viewport=value
    def _getviewport(self):
        return self._viewport
    viewport = property(_getviewport,_setviewport)

    def _setworldcoordinate(self,value):
        if not isinstance(value,list) and not len(value)==4:
            raise vcsError,  "worldcoordinate must be of type list and have four values ranging between [0,1]."
        self._worldcoordinate=value
    def _getworldcoordinate(self):
        return self._worldcoordinate
    worldcoordinate = property(_getworldcoordinate,_setworldcoordinate)

    def _setcanvas_template_editor(self,value):
        self._canvas_template_editor=value # No check on this!
    def _getcanvas_template_editor(self):
        return self._canvas_template_editor
    canvas_template_editor =property(_getcanvas_template_editor,_setcanvas_template_editor)

    def _setisplottinggridded(self,value):
        if not isinstance(value,bool):
            raise vcsError,  "isplottinggridded must be boolean"
        self._isplottinggridded=value # No check on this!
    def _getisplottinggridded(self):
        return self._isplottinggridded
    isplottinggridded =property(_getisplottinggridded,_setisplottinggridded)

    def _setanimate_info(self,value):
        self._animate_info=value # No check on this!
    def _getanimate_info(self):
        return self._animate_info
    animate_info =property(_getanimate_info,_setanimate_info)

    def start(self,*args,**kargs):
        self.interact(*args,**kargs)

    def interact(self,*args,**kargs):
      self.configure()
      self.backend.interact(*args,**kargs)

    def _datawc_tv(self, tv, arglist):
        """The graphics method's data world coordinates (i.e., datawc_x1, datawc_x2,
        datawc_y1, and datawc_y2) will override the incoming variable's coordinates.
        tv equals arglist[0] and assumed to be the first Variable. arglist[1] is
        assumed to be the second variable."""

        # Determine the type of graphics method
        nvar = 1
        if arglist[3]   == 'boxfill':
           gm=self.getboxfill( arglist[4] )
        elif arglist[3] == 'isofill':
           gm=self.getisofill( arglist[4] )
        elif arglist[3] == 'isoline':
           gm=self.getisoline( arglist[4] )
        elif arglist[3] == 'outfill':
           gm=self.getoutfill( arglist[4] )
        elif arglist[3] == 'outline':
           gm=self.getoutline( arglist[4] )
        elif arglist[3] == 'continents':
           gm=self.getcontinents( arglist[4] )
        elif arglist[3] == 'scatter':
           nvar = 2
           gm=self.getscatter( arglist[4] )
        elif arglist[3] == 'vector':
           nvar = 2
           gm=self.getvector( arglist[4] )
        elif arglist[3] == 'xvsy':
           nvar = 2
           gm=self.getxvsy( arglist[4] )
        elif arglist[3] == 'xyvsy':
           gm=self.getxyvsy( arglist[4] )
        elif arglist[3] == 'yxvsx':
           gm=self.getyxvsx( arglist[4] )
        elif arglist[3] == 'taylor':
           gm=self.gettaylor( arglist[4] )
        elif arglist[3] == 'meshfill':
           gm=self.getmeshfill( arglist[4] )
        else:
	   return tv

        # Determine if the graphics method needs clipping
        f32 = numpy.array((1.e20),numpy.float32)
        set_new_x = 0
        set_new_y = 0
        if (gm.datawc_x1 != f32) and (gm.datawc_x2 != f32): set_new_x = 1
        if (gm.datawc_y1 != f32) and (gm.datawc_y2 != f32): set_new_y = 1

        try:
           if ((set_new_x == 1) and (set_new_y == 0)) or (arglist[3] == 'yxvsx'):
              tv = tv( longitude=(gm.datawc_x1, gm.datawc_x2) )
              if nvar == 2:
                 arglist[1] = arglist[1]( longitude=(gm.datawc_x1, gm.datawc_x2) )
           elif ((set_new_x == 0) and (set_new_y == 1)) or (arglist[3] == 'xyvsy'):
              tv = tv( latitude=(gm.datawc_y1, gm.datawc_y2) )
              if nvar == 2:
                 arglist[1] = arglist[1]( latitude=(gm.datawc_y1, gm.datawc_y2) )
           elif (set_new_x == 1) and (set_new_y == 1):
              tv = tv( latitude=(gm.datawc_y1, gm.datawc_y2), longitude=(gm.datawc_x1,gm.datawc_x2) )
              if nvar == 2:
                 arglist[1] = arglist[1]( latitude=(gm.datawc_y1, gm.datawc_y2), longitude=(gm.datawc_x1,gm.datawc_x2) )
        except:
           pass

        return tv

    def savecontinentstype(self,value):
      self._savedcontinentstype = value

    def onClosing( self, cell  ):
        if self.configurator:
            self.endconfigure()
        self.backend.onClosing( cell )

    def _reconstruct_tv(self, arglist, keyargs):
        """Reconstruct a transient variable from the keyword arguments.
        Also select the default graphics method, depending on the grid type
        of the reconstructed variable. For meshfill, ravel the last two
        dimensions if necessary.
        arglist[0] is assumed to be a Variable."""

        ARRAY_1 = 0
        ARRAY_2 = 1
        TEMPLATE = 2
        GRAPHICS_METHOD = 3
        GRAPHICS_OPTION = 4

        origv = arglist[ARRAY_1]

        # Create copies of domain and attributes
        variable = keyargs.get('variable')
        if variable is not None:
            origv=MV2.array(variable)
        tvdomain = origv.getDomain()
        attrs = copy.copy(origv.attributes)
        axislist = list(map(lambda x: x[0].clone(), tvdomain))

        # Map keywords to dimension indices
        try:     rank = origv.ndim
        except:  rank = len( origv.shape )

        dimmap = {}
        dimmap['x'] = xdim = rank-1
        dimmap['y'] = ydim = rank-2
        dimmap['z'] = zdim = rank-3
        dimmap['t'] = tdim = rank-4
        dimmap['w'] = wdim = rank-5

        # Process grid keyword
        grid = keyargs.get('grid')
        if grid is not None and xdim>=0 and ydim>=0:
            if grid.getOrder() is None or grid.getOrder()=='yx':
                axislist[xdim] = grid.getLongitude().clone()
                axislist[ydim] = grid.getLatitude().clone()
            else:
                axislist[xdim] = grid.getLatitude().clone()
                axislist[ydim] = grid.getLongitude().clone()

        # Process axis keywords
        for c in ['x','y','z','t','w']:
            if dimmap[c]<0:
                continue
            arg = keyargs.get(c+'axis')
            if arg is not None:
                axislist[dimmap[c]] = arg.clone()

        # Process array keywords
        for c in ['x','y','z','t','w']:
            if dimmap[c]<0:
                continue
            arg = keyargs.get(c+'array')
            if arg is not None:
                axis = axislist[dimmap[c]]
                axis = cdms2.createAxis(arg,id=axis.id)
                axis.setBounds(None)
                axislist[dimmap[c]]=axis

        # Process bounds keywords
        for c in ['x','y']:
            if dimmap[c]<0:
                continue
            arg = keyargs.get(c+'bounds')
            if arg is not None:
                axis = axislist[dimmap[c]]
                axis.setBounds(arg)

        # Process axis name keywords
        for c in ['x','y','z','t','w']:
            if dimmap[c]<0:
                continue
            arg = keyargs.get(c+'name')
            if arg is not None:
                axis = axislist[dimmap[c]]
                axis.id = axis.name = arg

        # Create the internal tv
        tv = cdms2.createVariable(origv, copy=0, axes=axislist, attributes=attrs)
        grid = tv.getGrid()

        isgridded = (grid is not None)

        # Set the default graphics method if not already set.
        if arglist[GRAPHICS_METHOD] == "default" or\
                 (arglist[GRAPHICS_METHOD] == 'boxfill' and arglist[GRAPHICS_METHOD+1]=="default"):
                     # See _determine_arg_list
            try:
                nomesh=0
                m=grid.getMesh()
            except:
                nomesh=1

            if grid is None:
                if tv.ndim==1:
                    arglist[GRAPHICS_METHOD] = 'yxvsx'
                else:
                    arglist[GRAPHICS_METHOD] = 'boxfill'
            elif isinstance(grid, AbstractRectGrid):
                arglist[GRAPHICS_METHOD] = 'boxfill'
            else:
                latbounds, lonbounds = grid.getBounds()
                if (latbounds is None) or (lonbounds is None):
                    if not isinstance(grid,cdms2.hgrid.AbstractCurveGrid):
                        # Plug in 'points' graphics method here, with:
                        #   arglist[GRAPHICS_METHOD] = 'points'
                        raise vcsError, "Cell boundary data is missing, cannot plot nonrectangular gridded data."
                    else:
                        arglist[GRAPHICS_METHOD] = 'boxfill'
                else:

                    # tv has a nonrectilinear grid with bounds defined,
                    # so use meshfill. Create another default meshobject to hang
                    # keywords on, since the true 'default' meshobject
                    # is immutable.
                    arglist[GRAPHICS_METHOD] = 'meshfill'

                    # Get the mesh from the grid.
                    try:
                        gridindices = tv.getGridIndices()
                    except:
                        gridindices = None
                    mesh = grid.getMesh(transpose=gridindices)

                    # mesh array needs to be mutable, so make it a tv.
                    # Normally this is done up front in _determine_arg_list.
                    arglist[ARRAY_2] = cdms2.asVariable(mesh, 0)
                    meshobj = self.createmeshfill()
                    meshobj.wrap = [0.0, 360.0] # Wraparound
                    arglist[GRAPHICS_OPTION] = '__d_meshobj'

        # IF Meshfill method and no mesh passed then try to get the mesh from the object
        if arglist[GRAPHICS_METHOD]=='meshfill' and arglist[ARRAY_2] is None:
            # Get the mesh from the grid.
            try:
                gridindices = tv.getGridIndices()
                mesh = grid.getMesh(transpose=gridindices)
            except:
                gridindices = None
                mesh = grid.getMesh()

            # mesh array needs to be mutable, so make it a tv.
            # Normally this is done up front in _determine_arg_list.
            arglist[ARRAY_2] = cdms2.asVariable(mesh, 0)
            if arglist[GRAPHICS_OPTION] == 'default':
                meshobj = self.createmeshfill()
                meshobj.wrap = [0.0, 360.0] # Wraparound
                arglist[GRAPHICS_OPTION] = meshobj.name

        # Ravel the last two dimensions for meshfill if necessary
        ## value to know if we're plotting a grided meshfill
        self.isplottinggridded=False
        #if (arglist[GRAPHICS_METHOD]=='meshfill') and (tv.shape[-1] != arglist[ARRAY_2].shape[-3]):
        #    tvshape = tv.shape
        #    if isgridded:
        #        ny, nx = grid.shape
        #        if nx*ny==arglist[ARRAY_2].shape[-3]:
        #            ravelshape = tuple(list(tvshape)[:-2]+[ny*nx])
        #            xdim=ydim
        #            self.isplottinggridded=True
        #        else:
        #            ny, nx = tvshape[-2:]
        #            ravelshape = tuple(list(tvshape)[:-2]+[ny*nx])
        #    else:
        #        ny, nx = tvshape[-2:]
        #    ravelshape = tuple(list(tvshape)[:-2]+[ny*nx])
        #    tv = MV2.reshape(tv, ravelshape)
        #    xdim=ydim
        #    self.isplottinggridded=True
        #    if (tv.shape[-1] != arglist[ARRAY_2].shape[-3]):
        #        raise vcsError, "Mesh length = %d, does not match variable shape: %s"%(arglist[ARRAY_2].shape[-3], `tvshape`)
        #else:
        if isgridded and (arglist[GRAPHICS_METHOD]=='meshfill'):
                self.isplottinggridded=True

        # Process variable attributes
        _process_keyword(tv, 'comment1', 'comment1', keyargs)
        _process_keyword(tv, 'comment2', 'comment2', keyargs)
        _process_keyword(tv, 'comment3', 'comment3', keyargs)
        _process_keyword(tv, 'comment4', 'comment4', keyargs)
        _process_keyword(tv, 'source', 'file_comment', keyargs)
        _process_keyword(tv, 'time', 'hms', keyargs)
        _process_keyword(tv, 'title', 'long_name', keyargs)
        _process_keyword(tv, 'name', 'name', keyargs, default=tv.id)
        time = keyargs.get('time')
        if time is not None:
            ctime = time.tocomp()
            ar.date = str(ctime)
        _process_keyword(tv, 'units', 'units', keyargs)
        _process_keyword(tv, 'date', 'ymd', keyargs)
        # If date has still not been set, try to get it from the first
        # time value if present
        if not hasattr(tv, 'date') and not hasattr(tv, 'time'):
            change_date_time(tv, 0)

        # Draw continental outlines if specified.
        contout = keyargs.get('continents',None)
        if contout is None:
            #            if xdim>=0 and ydim>=0 and isgridded:
            ## Charles put back the self.isplottinggridded in addition for meshfill,
            if (xdim>=0 and ydim>=0 and tv.getAxis(xdim).isLongitude() and tv.getAxis(ydim).isLatitude()) or (self.isplottinggridded):
                contout = 1
            else:
                contout = 0
        if (isinstance(arglist[GRAPHICS_METHOD],str) and (arglist[GRAPHICS_METHOD]) == 'meshfill') or ((xdim>=0 and ydim>=0 and (contout>=1) and (contout<12))):
            self.setcontinentstype(contout)
            self.savecontinentstype(contout)
        else:
            self.setcontinentstype(0)
            self.savecontinentstype(0)

        # Reverse axis direction if necessary
        xrev = keyargs.get('xrev',0)
        if xrev==1 and xdim>=0:
            tv = tv[... , ::-1]

        # By default, latitudes on the y-axis are plotted S-N
        # levels on the y-axis are plotted with decreasing pressure
        if ydim>=0:
            yaxis = tv.getAxis(ydim)
            yrev = 0
## -- This code forces the latitude axis to alway be shown from -90 (South) to
##    90 (North). This causes a problem when wanting to view polar plots from
##    the North. So this feature has been removed.
##
##             if yaxis.isLatitude() and yaxis[0]>yaxis[-1]: yrev=1
##             if yaxis.isLevel() and yaxis[0]<yaxis[-1]: yrev=1

            yrev = keyargs.get('yrev',yrev)
            if yrev==1:
##                 yarray = copy.copy(yaxis[:])
##                 ybounds = yaxis.getBounds()
##                 yaxis[:] = yarray[::-1]
##                 yaxis.setBounds(ybounds[::-1,::-1])
                tv = tv[..., ::-1, :].clone()


#  -- This s no longer needed since we are making a copy of the data.
#     We now apply the axes changes below in __plot. Dean and Charles keep
#     an eye opened for the errors concerning datawc in the VCS module.
#        tv = self._datawc_tv( tv, arglist )
        return tv

    #############################################################################
    #                                                                           #
    # Print out the object's doc string.                                        #
    #                                                                           #
    #############################################################################
    def objecthelp(self, *arg):
        """
 Function: objecthelp               # Print out the object's doc string

 Description of Function:
    Print out information on the VCS object. See example below on its use.

 Example of Use:
    a=vcs.init()

    ln=a.getline('red')                 # Get a VCS line object
    a.objecthelp(ln)                    # This will print out information on how to use ln
    """
        for x in arg:
            print getattr(x, "__doc__", "")

    #############################################################################
    #                                                                           #
    # Initialize the VCS Canvas and set the Canvas mode to 0. Because the mode  #
    # is set to 0, the user will have to manually update the VCS Canvas by      #
    # using the "update" function.                                              #
    #                                                                           #
    #############################################################################
    def __init__(self, gui = 0, mode = 1, pause_time=0, call_from_gui=0, size=None, backend = "vtk"):
        #############################################################################
        #                                                                           #
        # The two Tkinter calls were needed for earlier versions of CDAT using      #
        # tcl/tk 8.3 and Python 2.2. In these earlier version of CDAT, Tkinter must #
        # be called before "_vcs.init()", which uses threads. That is,              #
        # "_vcs.init()" calls "XInitThreads()" which causes Tkinter keyboard events #
        # to hang. By calling Tkinter.Tk() first solves the problem.                #
        #                                                                           #
        # The code must have "XInitThreads()". Without this function, Xlib produces #
        # asynchronous errors. This X thread function can be found in the           #
        # vcsmodule.c file located in the "initialize_X routine.                    #
        #                                                                           #
        # Graphics User Interface Mode:                                             #
        #        gui = 0|1    if ==1, create the canvas with GUI controls           #
        #                     (Default setting is *not* to display GUI controls)    #
        #                                                                           #
        # Note:                                                                     #
        #     For version 4.0, which uses tcl/tk 8.4 and Python 2.3, the below      #
        #     Tkinter.Tk() calls are not necessary.                                 #
        #                                                                           #
        #     The code will remain here, but commented out in case the bug in       #
        #     tcl/tk reappears.                                                     #
        #                                                                           #
#########if (call_from_gui == 0):                                                   #########
#########   try:                                                                    #########
#########      print ' NO local host'                                               #########
#########      rt = Tkinter.Tk() # Use the default  DISPLAY and screen              #########
#########       print ' I have a rt', rt                                            #########
#########    except:                                                                #########
#########      print ' :0.0 local host'                                             #########
#########      rt = Tkinter.Tk(":0.0") # Use the localhost:0.0 for the DISPLAY and screen ###
#########   rt.withdraw()                                                           #########
########### rt.destroy()                                                            #########
        #                                                                           #
        #############################################################################
        self._canvas_id = vcs.next_canvas_id
        self.ParameterChanged = SIGNAL( 'ParameterChanged' )
        vcs.next_canvas_id+=1
        self.colormap = "default"
        self.backgroundcolor = 255,255,255
        ## default size for bg
        self.bgX = 814
        self.bgY = 606
        ## displays plotted
        self.display_names = []
        self.info = AutoAPI.Info(self)
        self.info.expose=["plot", "boxfill", "isofill", "isoline", "outfill", "outline", "scatter", "xvsy", "xyvsy", "yxvsx", "createboxfill", "getboxfill", "createisofill", "getisofill", "createisoline", "getisoline", "createyxvsx", "getyxvsx", "createxyvsy", "getxyvsy", "createxvsy", "getxvsy", "createscatter", "getscatter", "createoutfill", "getoutfill", "createoutline", "getoutline"]
        ospath = os.environ["PATH"]
        found = False
        for p in ospath.split(":"):
            if p==os.path.join(sys.prefix,"bin"):
                found = True
                break
        if found is False:
            os.environ["PATH"]=os.environ["PATH"]+":"+os.path.join(sys.prefix,"bin")
        global called_initial_attributes_flg
        global gui_canvas_closed
        global canvas_closed
##         import gui_support
        import time
##         from tkMessageBox import showerror

        is_canvas = len(vcs.return_display_names()[0])

        if gui_canvas_closed == 1:
           showerror( "Error Message to User", "There can only be one VCS Canvas GUI opened at any given time and the VCS Canvas GUI cannot operate with other VCS Canvases.")
           return

        self.winfo_id = -99
        self.varglist = []
        self.canvas_gui= None
        self.isplottinggridded=False
        self.canvas_guianimate_info=None
# DEAN or CHARLES -- remove the one line below for VCS Canvas GUI to work
        #gui = 0
        if is_canvas == 0:
           if ( (gui == 1) and (gui_canvas_closed == 0) ):
               no_root = 0
               if (gui_support.root_exists()): no_root = 1
               if (no_root == 0):
                  parent = gui_support.root()
               else:
                  parent = gui_support._root
               self.canvas_gui = _canvasgui.CanvasGUI(canvas=self,top_parent=parent)
               # Must wait for the window ID to return before moving on...
               while self.winfo_id == -99: self.winfo_id = self.canvas_gui.frame.winfo_id()


        if size is None:
            psize = 1.2941176470588236
        elif isinstance(size,(int,float)):
            psize = size
        elif isinstance(size,str):
            if size.lower() in ['letter','usletter']:
                psize = size = 1.2941176470588236
            elif size.lower() in ['a4',]:
                psize = size = 1.4142857142857141
            else:
                raise Exception, 'Unknown size: %s' % size
        else:
            raise Exception, 'Unknown size: %s' % size

        self.size = psize

        self.mode = mode
        self._animate_info=[]
        self.pause_time = pause_time
        self._canvas = vcs
        self.viewport =[0,1,0,1]
        self.worldcoordinate = [0,1,0,1]
        self._dotdir,self._dotdirenv = vcs.getdotdirectory()
        if ( (is_canvas == 0) and (gui == 1) and (gui_canvas_closed == 0) ): gui_canvas_closed = 1
        self.drawLogo = False
        self.enableLogo = True
        if backend == "vtk":
          self.backend = VTKVCSBackend(self)
        elif isinstance(backend,vtk.vtkRenderWindow):
          self.backend = VTKVCSBackend(self, renWin = backend)
        else:
          warnings.warn("Unknown backend type: '%s'\nAssiging 'as is' to backend, no warranty about anything working from this point on" % backend)
          self.backend=backend

        self._animate = self.backend.Animate( self )

        self.configurator = None

## Initial.attributes is being called in main.c, so it is not needed here!
## Actually it is for taylordiagram graphic methods....
###########################################################################################
#  Okay, then this is redundant since it is done in main.c. When time perments, put the   #
#  taylordiagram graphic methods attributes in main.c Because this is here we must check  #
#  to make sure that the initial attributes file is called only once for normalization    #
#  purposes....                                                                           #
###########################################################################################
        if called_initial_attributes_flg == 0:
           pth = vcs.__path__[0].split(os.path.sep)
           pth=pth[:-4] # Maybe need to make sure on none framework config
           pth=['/']+pth+['share','vcs', 'initial.attributes']
           try:
               vcs.scriptrun( os.path.join(*pth))
           except:
               pass
           self._dotdir,self._dotdirenv = vcs.getdotdirectory()
           user_init = os.path.join(os.environ['HOME'], self._dotdir, 'initial.attributes')
           if os.path.exists(user_init):
              vcs.scriptrun(user_init)
           else:
              shutil.copy2(os.path.join(*pth),user_init)

        called_initial_attributes_flg = 1
        self.canvas_template_editor=None
        self.ratio=0
        self._user_actions_names=['Clear Canvas','Close Canvas','Show arguments passsed to user action']
        self._user_actions = [self.clear, self.close, self.dummy_user_action]

    def configure(self):
        for display in self.display_names:
            d = vcs.elements["display"][display]
            if "3d" in d.g_type.lower():
                return
        if self.configurator is None:
            self.configurator = configurator.Configurator(self)
            self.configurator.update()
            self.configurator.show()

    def endconfigure(self):
        if self.configurator is not None:
            self.configurator.detach()
            self.configurator = None

    def processParameterChange( self, args ):
        self.ParameterChanged( args )

    ## Functions to set/querie drawing of UV-CDAT logo
    def drawlogoon(self):
      """Turn on drawing of logo on pix"""
      self.enableLogo = True

    def drawlogooff(self):
      """Turn off drawing of logo on pix"""
      self.enableLogo = False

    def getdrawlogo(self):
      """Return value of draw logo"""
      return self.enableLogo

    def initLogoDrawing(self):
        self.drawLogo = self.enableLogo

    #############################################################################
    #                                                                           #
    # Update wrapper function for VCS.                                          #
    #                                                                           #
    #############################################################################

    def update(self, *args, **kargs):
        """
 Function: update                   # Update the VCS Canvas.

 Description of Function:
    If a series of commands are given to VCS and the Canvas Mode is
    set to manual, then use this function to update the plot(s)
    manually.

 Example of Use:
    ...

    a=vcs.init()
    a.plot(s,'default','boxfill','quick')
    a.mode = 0                             # Go to manual mode
    box=x.getboxfill('quick')
    box.color_1=100
    box.xticlabels('lon30','lon30')
    box.xticlabels('','')
    box.datawc(1e20,1e20,1e20,1e20)
    box.datawc(-45.0, 45.0, -90.0, 90.0)

    a.update()                             # Update the changes manually
"""


        return self.backend.update(*args,**kargs)

    #############################################################################
    #                                                                           #
    # Update wrapper function for VCS with a check to update the continents.    #
    #                                                                           #
    #############################################################################
    def _update_continents_check(self, *args):
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        a = apply(self.canvas.updatecanvas_continents, args)
        self.flush() # update the canvas by processing all the X events
        self.backing_store()
        pause (self.pause_time)

        self.canvas.UNBLOCK_X_SERVER()
        return a

    #############################################################################
    #                                                                           #
    # Script VCS primary or secondary elements wrapper functions for VCS.       #
    #                                                                           #
    #############################################################################
    def scriptobject(self, obj, script_filename=None, mode=None):
        """
 Function: scriptobject       # Script a single primary or secondary class object

 Description of Function:
    Save individual attributes sets (i.e., individual primary class
    objects and/or secondary class objects). These attribute sets
    are saved in the user's current directory.

    Note: If the the filename has a ".py" at the end, it will produce a
          Python script. If the filename has a ".scr" at the end, it will
          produce a VCS script. If neither extensions are give, then by
          default a Python script will be produced.

    Note: Mode is either "w" for replace or "a" for append.

    Note: VCS does not allow the modification of `default' attribute sets,
          it will not allow them to be saved as individual script files.
          However, a `default' attribute set that has been copied under a
          different name can be saved as a script file.

 Example of Use:
    a=vcs.init()
    l=a.getline('red')         # To Modify an existing line object
    i=x.createisoline('dean')  # Create an instance of default isoline object
    ...
    x.scriptsingle(l,'line.scr','w') # Save line object as a VCS file 'line.scr'
    x.scriptsingle(i,'isoline.py')   # Save isoline object as a Python file 'isoline.py'
"""
        if istemplate(obj):
           template.P.script(obj, script_filename, mode)
        elif isgraphicsmethod(obj):
           if (obj.g_name == 'Gfb'):
              boxfill.Gfb.script(obj, script_filename, mode)
           elif (obj.g_name == 'Gfi'):
              isofill.Gfi.script(obj, script_filename, mode)
           elif (obj.g_name == 'Gi'):
              isoline.Gi.script(obj, script_filename, mode)
           elif (obj.g_name == 'Go'):
              outline.Go.script(obj, script_filename, mode)
           elif (obj.g_name == 'Gfo'):
              outfill.Gfo.script(obj, script_filename, mode)
           elif (obj.g_name == 'GXy'):
              xyvsy.GXy.script(obj, script_filename, mode)
           elif (obj.g_name == 'GYx'):
              yxvsx.GYx.script(obj, script_filename, mode)
           elif (obj.g_name == 'GXY'):
              xvsy.GXY.script(obj, script_filename, mode)
           elif (obj.g_name == 'Gv'):
              vector.Gv.script(obj, script_filename, mode)
           elif (obj.g_name == 'GSp'):
              scatter.GSp.script(obj, script_filename, mode)
           elif (obj.g_name == 'Gcon'):
              continents.Gcon.script(obj, script_filename, mode)
           elif (obj.g_name == 'Gtd'):
              obj.script( script_filename, mode)
           elif (obj.g_name == 'Gfm'):
              obj.script( script_filename, mode)
           else:
              print 'Could not find the correct graphics class object.'
        elif issecondaryobject(obj):
           if (obj.s_name == 'Tl'):
              line.Tl.script(obj, script_filename, mode)
           elif (obj.s_name == 'Tm'):
              marker.Tm.script(obj, script_filename, mode)
           elif (obj.s_name == 'Tf'):
              fillarea.Tf.script(obj, script_filename, mode)
           elif (obj.s_name == 'Tt'):
              texttable.Tt.script(obj, script_filename, mode)
           elif (obj.s_name == 'To'):
              textorientation.To.script(obj, script_filename, mode)
           elif (obj.s_name == 'Tc'):
              textcombined.Tc.script(obj, script_filename,mode)
           elif (obj.s_name == 'Proj'):
              obj.script( script_filename,mode)
           else:
              print 'Could not find the correct secondary class object.'
        else:
           print 'This is not a template, graphics method or secondary method object.'

    #############################################################################
    #                                                                           #
    # Remove VCS primary and secondary methods wrapper functions for VCS.       #
    #                                                                           #
    #############################################################################
    def removeobject(self, obj):
        """
 Function: remove

 Description of Function:
    The user has the ability to create primary and secondary class
    objects. The function allows the user to remove these objects
    from the appropriate class list.

    Note, To remove the object completely from Python, remember to
    use the "del" function.

    Also note, The user is not allowed to remove a "default" class
    object.

 Example of Use:
    a=vcs.init()
    line=a.getline('red')       # To Modify an existing line object
    iso=x.createisoline('dean') # Create an instance of an isoline object
    ...
    x.remove(line)      # Removes line object from VCS list
    del line            # Destroy instance "line", garbage collection
    x.remove(iso)       # Remove isoline object from VCS list
    del iso             # Destroy instance "iso", garbage collection
"""
        if istemplate(obj):
           msg =  _vcs.removeP(obj.name)
           obj.__dict__['name'] =  obj.__dict__['p_name'] = '__removed_from_VCS__'
        elif isgraphicsmethod(obj):
           if (obj.g_name == 'Gfb'):
              msg =  _vcs.removeGfb(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'Gfi'):
              msg =  _vcs.removeGfi(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'Gi'):
              msg =  _vcs.removeGi(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'Go'):
              msg =  _vcs.removeGo(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'Gfo'):
              msg =  _vcs.removeGfo(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'GXy'):
              msg =  _vcs.removeGXy(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'GYx'):
              msg =  _vcs.removeGYx(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'GXY'):
              msg =  _vcs.removeGXY(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'Gv'):
              msg =  _vcs.removeGv(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'GSp'):
              msg =  _vcs.removeGSp(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'Gcon'):
              msg =  _vcs.removeGcon(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'Gfm'):
              msg =  _vcs.removeGfm(obj.name)
              obj.name =  obj.g_name = '__removed_from_VCS__'
           elif (obj.g_name == 'Gtd'):
               n=len(vcs.taylordiagrams)
               ndel=0
               for i in range(n):
                   t=vcs.taylordiagrams[i-ndel]
                   if t.name==obj.name:
                       msg =  'Removed Taylordiagram graphics method: '+t.name
                       a=vcs.taylordiagrams.pop(i-ndel)
                       ndel=ndel+1
                       del(a)
           else:
              msg = 'Could not find the correct graphics class object.'
        elif issecondaryobject(obj):
           if (obj.s_name == 'Tl'):
              msg =  _vcs.removeTl(obj.name)
              obj.name =  obj.s_name = '__removed_from_VCS__'
           elif (obj.s_name == 'Tm'):
              msg =  _vcs.removeTm(obj.name)
              obj.name =  obj.s_name = '__removed_from_VCS__'
           elif (obj.s_name == 'Tf'):
              msg =  _vcs.removeTf(obj.name)
              obj.name =  obj.s_name = '__removed_from_VCS__'
           elif (obj.s_name == 'Tt'):
              msg =  _vcs.removeTt(obj.name)
              obj.name =  obj.s_name = '__removed_from_VCS__'
           elif (obj.s_name == 'To'):
              msg =  _vcs.removeTo(obj.name)
              obj.name =  obj.s_name = '__removed_from_VCS__'
           elif (obj.s_name == 'Tc'):
              msg =  _vcs.removeTt(obj.Tt_name)
              msg +=  _vcs.removeTo(obj.To_name)
              obj.Tt_name =  obj.s_name = '__removed_from_VCS__'
              obj.To_name =  obj.s_name = '__removed_from_VCS__'
           elif (obj.s_name == 'Proj'):
              msg =  _vcs.removeProj(obj.name)
              obj.name =  obj.s_name = '__removed_from_VCS__'
           elif (obj.s_name == 'Cp'):
              msg =  _vcs.removeCp(obj.name)
              obj.s_name =  obj.__dict__['name'] = '__removed_from_VCS__'
           else:
              msg =  'Could not find the correct secondary class object.'
        else:
           msg = 'This is not a template, graphics method, or secondary method object.'
        return msg

## Removed by C. Doutriaux, too many prints. We need to think
## if we want to raise an exception here?
##         if msg[:7]!='Removed':
##             print msg

    def syncP(self, *args):
        return apply(self.canvas.syncP, args)

    def removeP(self, *args):
        return apply(self.canvas.removeP, args)


    def clean_auto_generated_objects(self,type=None):
        """ cleans all self/auto genrated objects in vcs, only if they're not in use
        Example:
        import vcs
        x=vcs.init()
        x.clean_auto_generated_objects() # cleans everything
        x.clean_auto_generated_objects('template') # cleans template objects
        """

        if type is None:
            type = self.listelements()
            type.remove("fontNumber")
        elif isinstance(type,str):
            type=[type,]
        elif not isinstance(type,(list,tuple)):
            return
        for objtype in type:
            for obj in self.listelements(objtype):
                if obj[:2]=="__":
                    try:
                        exec("o = self.get%s(obj)" % objtype)
                        destroy = True
                        if objtype=='template':
##                             print o.name
                            dnames = self.return_display_names()
                            for d in dnames:
                                dpy = self.getplot(d)
                                if o.name in [dpy.template,dpy._template_origin]:
                                    destroy = False
                                    break
                        if destroy : self.removeobject(o)
##                         try:
##                             exec("o = self.get%s(obj)" % objtype)
##                             print 'stayed'
##                         except:
##                             print 'gone'
                    except Exception,err:
##                         print 'Error for:',o.name,err
##                         raise vcsError,err
                        pass

        return

    def check_name_source(self,name,source,typ):
        return vcs.check_name_source(name,source,typ)

    #############################################################################
    #                                                                           #
    # Template functions for VCS.                                               #
    #                                                                           #
    #############################################################################
    def createtemplate(self, name=None, source='default'):
        return vcs.createtemplate(name,source)
    createtemplate.__doc__ = vcs.manageElements.createtemplate.__doc__

    def gettemplate(self, Pt_name_src='default'):
      return vcs.gettemplate(Pt_name_src)
    gettemplate.__doc__ = vcs.manageElements.gettemplate.__doc__

    #############################################################################
    #                                                                           #
    # Projection functions for VCS.                                             #
    #                                                                           #
    #############################################################################
    def createprojection(self,name=None, source='default'):
        return vcs.createprojection(name, source)
    createprojection.__doc__ = vcs.manageElements.createprojection.__doc__

    def getprojection(self,Proj_name_src='default'):
        return vcs.getprojection(Proj_name_src)
    getprojection.__doc__ = vcs.manageElements.getprojection.__doc__


    #############################################################################
    #                                                                           #
    # Boxfill functions for VCS.                                                #
    #                                                                           #
    #############################################################################
    def createboxfill(self,name=None, source='default'):
        return vcs.createboxfill(name, source)
    createboxfill.__doc__ = vcs.manageElements.createboxfill.__doc__

    def getboxfill(self,Gfb_name_src='default'):
        return vcs.getboxfill(Gfb_name_src)
    getboxfill.__doc__ = vcs.manageElements.getboxfill


    def boxfill(self, *args, **parms):
        """
Options:::
%s
%s
%s
:::
 Input:::
%s
    :::
 Output:::
%s
    :::

 Function: boxfill                        # Generate a boxfill plot

 Description of Function:
    Generate a boxfill plot given the data, boxfill graphics method, and
    template. If no boxfill class object is given, then the 'default' boxfill
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('boxfill')                        # Show all the existing boxfill graphics methods
    box=a.getboxfill('quick')                # Create instance of 'quick'
    a.boxfill(array,box)                # Plot array using specified box and default
                                        #         template
    templt=a.gettemplate('AMIP')        # Create an instance of template 'AMIP'
    a.clear()                           # Clear VCS canvas
    a.boxfill(array,box,template)       # Plot array using specified box and template
    a.boxfill(box,array,template)       # Plot array using specified box and template
    a.boxfill(template,array,box)       # Plot array using specified box and template
    a.boxfill(template,array,box)       # Plot array using specified box and template
    a.boxfill(array,'AMIP','quick')     # Use 'AMIP' template and 'quick' boxfill
    a.boxfill('AMIP',array,'quick')     # Use 'AMIP' template and 'quick' boxfill
    a.boxfill('AMIP','quick',array)     # Use 'AMIP' template and 'quick' boxfill

###################################################################################################################
###########################################                         ###############################################
########################################## End boxfill Description ################################################
#########################################                         #################################################
###################################################################################################################

"""
        arglist=_determine_arg_list('boxfill',args)
        return self.__plot(arglist, parms)
    boxfill.__doc__ = boxfill.__doc__ % (plot_keywords_doc,graphics_method_core,axesconvert,plot_2D_input, plot_output)

    #############################################################################
    #                                                                           #
    # Taylordiagram functions for VCS.                                          #
    #                                                                           #
    #############################################################################
    def createtaylordiagram(self,name=None, source='default'):
        return vcs.createtaylordiagram(name,source)
    createtaylordiagram.__doc__ = vcs.manageElements.createtaylordiagram.__doc__

    def gettaylordiagram(self,Gtd_name_src='default'):
        return vcs.gettaylordiagram(Gtd_name_src)
    gettaylordiagram.__doc__ = vcs.manageElements.gettaylordiagram.__doc__

    def taylordiagram(self, *args, **parms):
        """
 Function: taylordiagram                        # Generate an taylordiagram plot

 Description of Function:
    Generate a taylordiagram plot given the data, taylordiagram graphics method, and
    template. If no taylordiagram class object is given, then the 'default' taylordiagram
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('taylordiagram')                   # Show all the existing taylordiagram graphics methods
    td=a.gettaylordiagram()                   # Create instance of 'default'
    a.taylordiagram(array,td)                 # Plot array using specified iso and default
                                              #       template
    a.clear()                                 # Clear VCS canvas
    a.taylordiagram(array,td,template)        # Plot array using specified iso and template
"""
        arglist=_determine_arg_list('taylordiagram',args)
        return self.__plot(arglist, parms)


    #############################################################################
    #                                                                           #
    # Meshfill functions for VCS.                                               #
    #                                                                           #
    #############################################################################

    def createmeshfill(self,name=None, source='default'):
        return vcs.createmeshfill(name, source)
    createmeshfill.__doc__ = vcs.manageElements.createmeshfill.__doc__

    def getmeshfill(self,Gfm_name_src='default'):
        return vcs.getmeshfill(Gfm_name_src)
    getmeshfill.__doc__ = vcs.manageElements.getmeshfill.__doc__


    def meshfill(self,*args, **parms):
        """
 Function: meshfill               # Generate an meshfill plot

 Description of Function:
    Generate a meshfill plot given the data, the mesh, a meshfill graphics method, and
    a template. If no meshfill class object is given, then the 'default' meshfill
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

    Format:
    This function expects 1D data (any extra dimension will be used for animation)
    In addition the mesh array must be of the same shape than data with 2 additional dimension representing the vertices coordinates for the Y (0) and X (1) dimension
    Let's say you want to plot a spatial assuming mesh containing 10,000 grid cell, then data must be shape (10000,) or (n1,n2,n3,...,10000) if additional dimensions exist (ex time,level), these dimension would be used only for animation and will be ignored in the rest of this example.
    The shape of the mesh, assuming 4 vertices per grid cell, must be (1000,2,4), where the array [:,0,:] represent the Y coordinates of the vertices (clockwise or counterclockwise) and the array [:,1:] represents the X coordinates of the vertices (the same clockwise/counterclockwise than the Y coordinates)
    In brief you'd have:
    data.shape=(10000,)
    mesh.shape=(10000,2,4)

 Example of Use:
    a=vcs.init()
    a.show('meshfill')                   # Show all the existing meshfill graphics methods
    mesh=a.getmeshfill()                 # Create instance of 'default'
    a.meshfill(array,mesh)               # Plot array using specified mesh and default
                                         #       template
    a.clear()                            # Clear VCS canvas
    a.meshfill(array,mesh,mesh_graphic_method,template) # Plot array using specified mesh mesh graphic method and template
"""
        arglist=_determine_arg_list('meshfill',args)
        return self.__plot(arglist, parms)

    #############################################################################
    #                                                                           #
    # DV3D functions for VCS.                                                #
    #                                                                           #
    #############################################################################

    def create3d_scalar(self,name=None,source='default'):
      return vcs.create3d_scalar(name,source)

    create3d_scalar.__doc__ = vcs.manageElements.create3d_scalar.__doc__
    def get3d_scalar(self,Gfdv3d_name_src='default'):
      return vcs.get3d_scalar(Gfdv3d_name_src)
    get3d_scalar.__doc__ = vcs.manageElements.get3d_scalar.__doc__

    def scalar3d(self, *args, **parms):
        arglist=_determine_arg_list('3d_scalar',args)
        return self.__plot(arglist, parms)

    def create3d_vector(self,name=None,source='default'):
      return vcs.create3d_vector(name,source)

    create3d_vector.__doc__ = vcs.manageElements.create3d_vector.__doc__
    def get3d_vector(self,Gfdv3d_name_src='default'):
      return vcs.get3d_vector(Gfdv3d_name_src)
    get3d_vector.__doc__ = vcs.manageElements.get3d_vector.__doc__

    def vector3d(self, *args, **parms):
        arglist=_determine_arg_list('3d_vector',args)
        return self.__plot(arglist, parms)

    def create3d_dual_scalar(self,name=None,source='default'):
      return vcs.create3d_dual_scalar(name,source)

    create3d_dual_scalar.__doc__ = vcs.manageElements.create3d_dual_scalar.__doc__
    def get3d_dual_scalar(self,Gfdv3d_name_src='default'):
      return vcs.get3d_dual_scalar(Gfdv3d_name_src)
    get3d_dual_scalar.__doc__ = vcs.manageElements.get3d_dual_scalar.__doc__

    def dual_scalar3d(self, *args, **parms):
        arglist=_determine_arg_list('3d_dual_scalar',args)
        return self.__plot(arglist, parms)

    #############################################################################
    #                                                                           #
    # Isofill functions for VCS.                                                #
    #                                                                           #
    #############################################################################
    def createisofill(self,name=None, source='default'):
        return vcs.createisofill(name, source)
    createisofill.__doc__ = vcs.manageElements.createisofill.__doc__

    def getisofill(self,Gfi_name_src='default'):
        return vcs.getisofill(Gfi_name_src)
    getisofill.__doc__ = vcs.manageElements.getisofill.__doc__

    def isofill(self, *args, **parms):
        """
Options:::
%s
%s
%s
:::
 Input:::
%s
    :::
 Output:::
%s
    :::

 Function: isofill                        # Generate an isofill plot

 Description of Function:
    Generate a isofill plot given the data, isofill graphics method, and
    template. If no isofill class object is given, then the 'default' isofill
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('isofill')                   # Show all the existing isofill graphics methods
    iso=a.getisofill('quick')           # Create instance of 'quick'
    a.isofill(array,iso)                # Plot array using specified iso and default
                                        #       template
    a.clear()                           # Clear VCS canvas
    a.isofill(array,iso,template)       # Plot array using specified iso and template

###################################################################################################################
###########################################                         ###############################################
########################################## End isofill Description ################################################
#########################################                         #################################################
###################################################################################################################

"""
        arglist=_determine_arg_list('isofill',args)
        return self.__plot(arglist, parms)
    isofill.__doc__ = isofill.__doc__ % (plot_keywords_doc,graphics_method_core,axesconvert,plot_2D_input, plot_output)


    #############################################################################
    #                                                                           #
    # Isoline functions for VCS.                                                #
    #                                                                           #
    #############################################################################
    def createisoline(self, name=None, source='default'):
        return vcs.createisoline(name, source)
    createisoline.__doc__ = vcs.manageElements.createisoline.__doc__

    def getisoline(self,Gi_name_src='default'):
        return vcs.getisoline(Gi_name_src)
    getisoline.__doc__ = vcs.manageElements.getisoline.__doc__

    def isoline(self, *args, **parms):
        """
Options:::
%s
%s
%s
:::
 Input:::
%s
    :::
 Output:::
%s
    :::

 Function: isoline                        # Generate an isoline plot

 Description of Function:
    Generate a isoline plot given the data, isoline graphics method, and
    template. If no isoline class object is given, then the 'default' isoline
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('isoline')                   # Show all the existing isoline graphics methods
    iso=a.getisoline('quick')           # Create instance of 'quick'
    a.isoline(array,iso)                # Plot array using specified iso and default
                                        #       template
    a.clear()                           # Clear VCS canvas
    a.isoline(array,iso,template)       # Plot array using specified iso and template

###################################################################################################################
###########################################                         ###############################################
########################################## End isoline Description ################################################
#########################################                         #################################################
###################################################################################################################

"""
        arglist=_determine_arg_list('isoline',args)
        return self.__plot(arglist, parms)
    isoline.__doc__ = isoline.__doc__ % (plot_keywords_doc,graphics_method_core,axesconvert,plot_2D_input, plot_output)

    def create1d(self,name=None,source='default'):
        return vcs.create1d(name,source)
    create1d.__doc__ = vcs.manageElements.create1d.__doc__

    def get1d(self,name):
        return vcs.get1d(name)
    create1d.__doc__ = vcs.manageElements.create1d.__doc__


    #############################################################################
    #                                                                           #
    # Xyvsy functions for VCS.                                                  #
    #                                                                           #
    #############################################################################
    def createxyvsy(self,name=None, source='default'):
        return vcs.createxyvsy(name,source)
    createxyvsy.__doc__ = vcs.manageElements.createxyvsy.__doc__

    def getxyvsy(self,GXy_name_src='default'):
        return vcs.getxyvsy(GXy_name_src)
    getxyvsy.__doc__ = vcs.manageElements.getxyvsy.__doc__

    def xyvsy(self, *args, **parms):
        """
Options:::
%s
%s
%s
:::
 Input:::
%s
    :::
 Output:::
%s
    :::

 Function: xyvsy                        # Generate a Xyvsy plot

 Description of Function:
    Generate a Xyvsy plot given the data, Xyvsy graphics method, and
    template. If no Xyvsy class object is given, then the 'default' Xyvsy
    graphics method is used. Simerly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('xyvsy')                   # Show all the existing Xyvsy graphics methods
    xyy=a.getxyvsy('quick')           # Create instance of 'quick'
    a.xyvsy(array,xyy)                # Plot array using specified xyy and default
                                        #       template
    a.clear()                           # Clear VCS canvas
    a.xyvsy(array,xyy,template)       # Plot array using specified xyy and template

#################################################################################################################
###########################################                       ###############################################
########################################## End xyvsy Description ################################################
#########################################                       #################################################
#################################################################################################################

"""
        arglist=_determine_arg_list('xyvsy',args)
        return self.__plot(arglist, parms)
    xyvsy.__doc__ = xyvsy.__doc__ % (plot_keywords_doc,graphics_method_core,xaxisconvert,plot_1D_input, plot_output)

    #############################################################################
    #                                                                           #
    # Yxvsx functions for VCS.                                                  #
    #                                                                           #
    #############################################################################
    def createyxvsx(self, name=None, source='default'):
        return vcs.createyxvsx(name,source)
    createyxvsx.__doc__ = vcs.manageElements.createyxvsx.__doc__

    def getyxvsx(self,GYx_name_src='default'):
        return vcs.getyxvsx(GYx_name_src)
    getyxvsx.__doc__ = vcs.manageElements.getyxvsx.__doc__

    def yxvsx(self, *args, **parms):
        """
Options:::
%s
%s
%s
:::
 Input:::
%s
    :::
 Output:::
%s
    :::

 Function: yxvsx                        # Generate a Yxvsx plot

 Description of Function:
    Generate a Yxvsx plot given the data, Yxvsx graphics method, and
    template. If no Yxvsx class object is given, then the 'default' Yxvsx
    graphics method is used. Simerly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('yxvsx')                   # Show all the existing Yxvsx graphics methods
    yxx=a.getyxvsx('quick')           # Create instance of 'quick'
    a.yxvsx(array,yxx)                # Plot array using specified yxx and default
                                      #       template
    a.clear()                         # Clear VCS canvas
    a.yxvsx(array,yxx,template)       # Plot array using specified yxx and template

#################################################################################################################
###########################################                       ###############################################
########################################## End yxvsx Description ################################################
#########################################                       #################################################
#################################################################################################################

"""
        arglist=_determine_arg_list('yxvsx',args)
        return self.__plot(arglist, parms)
    yxvsx.__doc__ = yxvsx.__doc__ % (plot_keywords_doc,graphics_method_core,xaxisconvert,plot_1D_input, plot_output)

    #############################################################################
    #                                                                           #
    # XvsY functions for VCS.                                                   #
    #                                                                           #
    #############################################################################
    def createxvsy(self, name=None, source='default'):
        return vcs.createxvsy(name,source)
    createxvsy.__doc__ = vcs.manageElements.createxvsy.__doc__

    def getxvsy(self,GXY_name_src='default'):
        return vcs.getxvsy(GXY_name_src)
    getxvsy.__doc__ = vcs.manageElements.getxvsy.__doc__

    def xvsy(self, *args, **parms):
        """
Options:::
%s
%s
%s
%s
    :::
 Output:::
%s
    :::

 Function: xvsy                      # Generate a XvsY plot

 Description of Function:
    Generate a XvsY plot given the data, XvsY graphics method, and
    template. If no XvsY class object is given, then the 'default' XvsY
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('xvsy')                   # Show all the existing XvsY graphics methods
    xy=a.getxvsy('quick')            # Create instance of 'quick'
    a.xvsy(array,xy)                 # Plot array using specified xy and default
                                     #       template
    a.clear()                        # Clear VCS canvas
    a.xvsy(array,xy,template)        # Plot array using specified xy and template

#################################################################################################################
###########################################                       ###############################################
########################################## End xvsy Description ################################################
#########################################                       #################################################
#################################################################################################################

"""
        arglist=_determine_arg_list('xvsy',args)
        return self.__plot(arglist, parms)
    xvsy.__doc__ = xvsy.__doc__ % (plot_keywords_doc,graphics_method_core,axesconvert,plot_2_1D_input, plot_output)

    #############################################################################
    #                                                                           #
    # Vector functions for VCS.                                                 #
    #                                                                           #
    #############################################################################
    def createvector(self, name=None, source='default'):
        return vcs.createvector(name, source)
    createvector.__doc__=vcs.manageElements.createvector.__doc__

    def getvector(self,Gv_name_src='default'):
        return vcs.getvector(Gv_name_src)
    getvector.__doc__=vcs.manageElements.getvector.__doc__

    def vector(self, *args, **parms):
        """
 Function: vector                      # Generate a vector plot

 Description of Function:
    Generate a vector plot given the data, vector graphics method, and
    template. If no vector class object is given, then the 'default' vector
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('vector')                   # Show all the existing vector graphics methods
    vec=a.getvector('quick')           # Create instance of 'quick'
    a.vector(array,vec)                # Plot array using specified vec and default
                                        #       template
    a.clear()                           # Clear VCS canvas
    a.vector(array,vec,template)       # Plot array using specified vec and template
"""
        arglist=_determine_arg_list('vector',args)
        return self.__plot(arglist, parms)

    #############################################################################
    #                                                                           #
    # Scatter functions for VCS.                                                #
    #                                                                           #
    #############################################################################
    def createscatter(self, name=None, source='default'):
        return vcs.createscatter(name,source)
    createscatter.__doc__ = vcs.manageElements.createscatter.__doc__

    def getscatter(self,GSp_name_src='default'):
        return vcs.getscatter(GSp_name_src)
    getscatter.__doc__ = vcs.manageElements.getscatter.__doc__

    def scatter(self, *args, **parms):
        """
Options:::
%s
%s
%s
%s
    :::
 Output:::
%s
    :::

 Function: scatter                      # Generate a scatter plot

 Description of Function:
    Generate a scatter plot given the data, scatter graphics method, and
    template. If no scatter class object is given, then the 'default' scatter
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('scatter')                   # Show all the existing scatter graphics methods
    sct=a.getscatter('quick')           # Create instance of 'quick'
    a.scatter(array,sct)                # Plot array using specified sct and default
                                        #       template
    a.clear()                           # Clear VCS canvas
    a.scatter(array,sct,template)       # Plot array using specified sct and template

###################################################################################################################
###########################################                         ###############################################
########################################## End scatter Description ################################################
#########################################                         #################################################
###################################################################################################################

"""

        arglist=_determine_arg_list('scatter',args)
        return self.__plot(arglist, parms)
    scatter.__doc__ = scatter.__doc__ % (plot_keywords_doc,graphics_method_core,axesconvert,plot_2_1D_input, plot_output)


    #############################################################################
    #                                                                           #
    # Continents functions for VCS.                                             #
    #                                                                           #
    #############################################################################
    def createcontinents(self, name=None, source='default'):
        """
 Function: createcontinents               # Construct a new continents graphics method

 Description of Function:
    Create a new continents graphics method given the the name and the existing
    continents graphics method to copy the attributes from. If no existing
    continents graphics method name is given, then the default continents graphics
    method will be used as the graphics method to which the attributes will
    be copied from.

    If the name provided already exists, then a error will be returned. Graphics
    method names must be unique.

 Example of Use:
    a=vcs.init()
    a.show('continents')
    con=a.createcontinents('example1',)
    a.show('continents')
    con=a.createcontinents('example2','quick')
    a.show('continents')
"""

        name,source = self.check_name_source(name,source,'continents')

        return continents.Gcon(self, name, source, 0)

    def getcontinents(self,Gcon_name_src='default'):
        """
 Function: getcontinents               # Construct a new continents graphics method

 Description of Function:
    VCS contains a list of graphics methods. This function will create a
    continents class object from an existing VCS continents graphics method. If
    no continents name is given, then continents 'default' will be used.

    Note, VCS does not allow the modification of `default' attribute
    sets. However, a `default' attribute set that has been copied under a
    different name can be modified. (See the createcontinents function.)

 Example of Use:
    a=vcs.init()
    a.show('continents')              # Show all the existing continents graphics
                                      # methods
    con=a.getcontinents()               # con instance of 'default' continents graphics
                                        #       method
    con2=a.getcontinents('quick')       # con2 instance of existing 'quick' continents
                                        #       graphics method
"""

        # Check to make sure the argument passed in is a STRING
        if not isinstance(Gcon_name_src,str):
           raise vcsError, 'The argument must be a string.'

        Gcon_name = None
        return continents.Gcon(self, Gcon_name, Gcon_name_src, 1)

    def continents(self, *args, **parms):
        """
 Function: continents                      # Generate a continents plot

 Description of Function:
    Generate a continents plot given the data, continents graphics method, and
    template. If no continents class object is given, then the 'default' continents
    graphics method is used. Similarly, if no template class object is given,
    then the 'default' template is used.

 Example of Use:
    a=vcs.init()
    a.show('continents')                # Show all the existing continents graphics
                                        # methods
    con=a.getcontinents('quick')        # Create instance of 'quick'
    a.continents(array,con)             # Plot array using specified con and default
                                        #       template
    a.clear()                           # Clear VCS canvas
    a.continents(array,con,template)    # Plot array using specified con and template
"""
        arglist=_determine_arg_list('continents',args)
        return self.__plot(arglist, parms)

    #############################################################################
    #                                                                           #
    # Line  functions for VCS.                                                  #
    #                                                                           #
    #############################################################################
    def createline(self,name=None, source='default', ltype=None,
                 width=None, color=None, priority=None,
                 viewport=None, worldcoordinate=None,
                 x=None, y=None, projection=None):
        return vcs.createline(name,source,ltype,width,color,priority,viewport,worldcoordinate,x,y,projection)
    createline.__doc__ = vcs.manageElements.createline.__doc__

    def getline(self,name='default', ltype=None, width=None, color=None,
                 priority=None, viewport=None,
                 worldcoordinate=None,
                 x=None, y=None):
        return  vcs.getline(name,ltype,width,color,priority,viewport,worldcoordinate,x,y)
    getline.__doc__ = vcs.manageElements.getline.__doc__

    def line(self, *args, **parms):
        """
 Function: line                           # Generate a line plot

 Description of Function:
    Plot a line segment on the Vcs Canvas. If no line class
    object is given, then an error will be returned.

 Example of Use:
    a=vcs.init()
    a.show('line')                      # Show all the existing line objects
    ln=a.getline('red')                 # Create instance of 'red'
    ln.width=4                          # Set the line width
    ln.color = 242                      # Set the line color
    ln.type = 4                         # Set the line type
    ln.x=[[0.0,2.0,2.0,0.0,0.0], [0.5,1.5]] # Set the x value points
    ln.y=[[0.0,0.0,2.0,2.0,0.0], [1.0,1.0]] # Set the y value points
    a.line(ln)                          # Plot using specified line object
"""
        arglist=_determine_arg_list('line',args)
        return self.__plot(arglist, parms)

    def drawline(self, name=None, ltype='solid', width=1, color=241,
                 priority=1, viewport=[0.0,1.0,0.0,1.0],
                 worldcoordinate=[0.0,1.0,0.0,1.0],
                 x=None, y=None,projection='default',bg=0):
        """
 Function: drawline                           # Generate and draw a line plot

 Description of Function:
    Generate and draw a line object on the VCS Canvas.

 Example of Use:
    a=vcs.init()
    a.show('line')                      # Show all the existing line objects
    ln=a.drawline(name='red', ltype='dash', width=2,
                  color=242, priority=1, viewport=[0, 2.0, 0, 2.0],
                  worldcoordinate=[0,100, 0,50]
                  x=[0,20,40,60,80,100],
                  y=[0,10,20,30,40,50] )      # Create instance of line object 'red'
    a.line(ln)                          # Plot using specified line object
"""
        if (name is None) or (not isinstance(name,str)):
            raise vcsError, 'Must provide string name for the line.'
        else:
            lo = self.listelements('line')
            if name in lo:
               ln = self.getline( name )
            else:
               ln = self.createline( name )
        ln.type = ltype
        ln.width = width
        ln.color = color
        ln.priority = priority
        ln.viewport = viewport
        ln.worldcoordinate = worldcoordinate
        ln.x = x
        ln.y = y
        ln.projection=projection
        self.line( ln ,bg=bg)

        return ln


    #############################################################################
    #                                                                           #
    # Marker  functions for VCS.                                                #
    #                                                                           #
    #############################################################################
    def createmarker(self,name=None, source='default', mtype=None,
                 size=None, color=None,priority=1,
                 viewport=None, worldcoordinate=None,
                 x=None, y=None,projection=None):
        return vcs.createmarker(name,source,mtype,size,color,priority,
                                viewport,worldcoordinate,x,y,projection)
    createmarker.__doc__ = vcs.manageElements.createmarker.__doc__

    def getmarker(self,name='default', mtype=None, size=None, color=None,
                 priority=None, viewport=None,
                 worldcoordinate=None,
                 x=None, y=None):
        return vcs.getmarker(name,mtype,size,color,priority,viewport,worldcoordinate,x,y)
    getmarker.__doc__ = vcs.manageElements.getmarker.__doc__

    def marker(self, *args, **parms):
        """
 Function: marker                           # Generate a marker plot

 Description of Function:
    Plot a marker segment on the Vcs Canvas. If no marker class
    object is given, then an error will be returned.

 Example of Use:
    a=vcs.init()
    a.show('marker')                     # Show all the existing marker objects
    mrk=a.getmarker('red')               # Create instance of 'red'
    mrk.size=4                           # Set the marker size
    mrk.color = 242                      # Set the marker color
    mrk.type = 4                         # Set the marker type
    mrk.x=[[0.0,2.0,2.0,0.0,0.0], [0.5,1.5]] # Set the x value points
    mrk.y=[[0.0,0.0,2.0,2.0,0.0], [1.0,1.0]] # Set the y value points
    a.marker(mrk)                          # Plot using specified marker object
"""
        arglist=_determine_arg_list('marker',args)
        return self.__plot(arglist, parms)

    def drawmarker(self, name=None, mtype='solid', size=1, color=241,
                 priority=1, viewport=[0.0,1.0,0.0,1.0],
                 worldcoordinate=[0.0,1.0,0.0,1.0],
                 x=None, y=None,bg=0):
        """
 Function: drawmarker                           # Generate and draw a marker plot

 Description of Function:
    Generate and draw a marker object on the VCS Canvas.

 Example of Use:
    a=vcs.init()
    a.show('marker')                      # Show all the existing marker objects
    mrk=a.drawmarker(name='red', mtype='dash', size=2,
                  color=242, priority=1, viewport=[0, 2.0, 0, 2.0],
                  worldcoordinate=[0,100, 0,50]
                  x=[0,20,40,60,80,100],
                  y=[0,10,20,30,40,50] )      # Create instance of marker object 'red'
    a.marker(mrk)                          # Plot using specified marker object
"""
        if (name is None) or (not isinstance(name,str)):
            raise vcsError, 'Must provide string name for the marker.'
        else:
            lo = self.listelements('marker')
            if name in lo:
               mrk = self.getmarker( name )
            else:
               mrk = self.createmarker( name )
        mrk.type = mtype
        mrk.size = size
        mrk.color = color
        mrk.priority = priority
        mrk.viewport = viewport
        mrk.worldcoordinate = worldcoordinate
        mrk.x = x
        mrk.y = y
        self.marker( mrk ,bg=bg)

        return mrk


    #############################################################################
    #                                                                           #
    # Fillarea  functions for VCS.                                              #
    #                                                                           #
    #############################################################################
    def createfillarea(self,name=None, source='default', style=None,
                 index=None, color=None, priority=1,
                 viewport=None, worldcoordinate=None,
                 x=None, y=None):
        return vcs.createfillarea(name,source,style,index,color,priority,viewport,worldcoordinate,x,y)
    createfillarea.__doc__ = vcs.manageElements.createfillarea.__doc__


    def getfillarea(self,name='default', style=None,
                 index=None, color=None,
                 priority=None, viewport=None,
                 worldcoordinate=None,
                 x=None, y=None):
        return vcs.getfillarea(name,style,index,color,priority,viewport,worldcoordinate,x,y)
    getfillarea.__doc__ = vcs.manageElements.getfillarea.__doc__

    def fillarea(self, *args, **parms):
        """
 Function: fillarea                           # Generate a fillarea plot

 Description of Function:
    Plot a fillarea segment on the Vcs Canvas. If no fillarea class
    object is given, then an error will be returned.

 Example of Use:
    a=vcs.init()
    a.show('fillarea')                  # Show all the existing fillarea objects
    fa=a.getfillarea('red')             # Create instance of 'red'
    fa.style=1                          # Set the fillarea style
    fa.index=4                          # Set the fillarea index
    fa.color = 242                      # Set the fillarea color
    fa.type = 4                         # Set the fillarea type
    fa.x=[[0.0,2.0,2.0,0.0,0.0], [0.5,1.5]] # Set the x value points
    fa.y=[[0.0,0.0,2.0,2.0,0.0], [1.0,1.0]] # Set the y value points
    a.fillarea(fa)                          # Plot using specified fillarea object
"""
        arglist=_determine_arg_list('fillarea',args)
        return self.__plot(arglist, parms)

    def drawfillarea(self, name=None, style=1, index=1, color=241,
                 priority=1, viewport=[0.0,1.0,0.0,1.0],
                 worldcoordinate=[0.0,1.0,0.0,1.0],
                 x=None, y=None,bg=0):
        """
 Function: drawfillarea                           # Generate and draw a fillarea plot

 Description of Function:
    Generate and draw a fillarea object on the VCS Canvas.

 Example of Use:
    a=vcs.init()
    a.show('fillarea')                      # Show all the existing fillarea objects
    fa=a.drawfillarea(name='red', mtype='dash', size=2,
                  color=242, priority=1, viewport=[0, 2.0, 0, 2.0],
                  worldcoordinate=[0,100, 0,50]
                  x=[0,20,40,60,80,100],
                  y=[0,10,20,30,40,50] )      # Create instance of fillarea object 'red'
    a.fillarea(fa)                          # Plot using specified fillarea object
"""
        if (name is None) or (not isinstance(name,str)):
            raise vcsError, 'Must provide string name for the fillarea.'
        else:
            lo = self.listelements('fillarea')
            if name in lo:
               fa = self.getfillarea( name )
            else:
               fa = self.createfillarea( name )
        fa.style = style
        fa.index = index
        fa.color = color
        fa.priority = priority
        fa.viewport = viewport
        fa.worldcoordinate = worldcoordinate
        fa.x = x
        fa.y = y
        self.fillarea( fa, bg=bg )

        return fa


    #############################################################################
    #                                                                           #
    # Text Table  functions for VCS.                                            #
    #                                                                           #
    #############################################################################
    def createtexttable(self,name=None, source='default', font=None,
                 spacing=None, expansion=None, color=None, priority=None,
                 viewport=None, worldcoordinate=None,
                 x=None, y=None):
      return vcs.createtexttable(name,source,font,spacing,expansion,color,priority,
                                 viewport,worldcoordinate,x,y)
    createtexttable.__doc__=vcs.manageElements.createtexttable.__doc__

    def gettexttable(self,name='default', font=None,
                 spacing=None, expansion=None, color=None,
                 priority=None, viewport=None,
                 worldcoordinate=None,
                 x=None, y=None):
      return vcs.gettexttable(name,font,spacing,expansion,color,priority,
                                 viewport,worldcoordinate,x,y)
    gettexttable.__doc__=vcs.manageElements.gettexttable.__doc__

    #############################################################################
    #                                                                           #
    # Text Orientation  functions for VCS.                                      #
    #                                                                           #
    #############################################################################
    def createtextorientation(self,name=None, source='default'):
        return vcs.createtextorientation(name, source)
    createtextorientation.__doc__=vcs.manageElements.createtextorientation.__doc__

    def gettextorientation(self,To_name_src='default'):
        return vcs.gettextorientation(To_name_src)
    gettextorientation.__doc__=vcs.manageElements.gettextorientation.__doc__

    #############################################################################
    #                                                                           #
    # Text Combined  functions for VCS.                                         #
    #                                                                           #
    #############################################################################
    def createtextcombined(self,Tt_name=None, Tt_source='default', To_name=None, To_source='default', font=None, spacing=None, expansion=None, color=None, priority=None, viewport=None, worldcoordinate=None, x=None, y=None, height=None, angle=None, path=None, halign=None, valign=None, projection=None):
        return vcs.createtextcombined(Tt_name, Tt_source, To_name, To_source,
            font, spacing, expansion, color, priority, viewport, worldcoordinate,
            x, y, height, angle, path, halign, valign, projection)
    createtextcombined.__doc__ = vcs.manageElements.createtextcombined.__doc__
    #
    # Set alias for the secondary createtextcombined.
    createtext = createtextcombined

    def gettextcombined(self,Tt_name_src='default', To_name_src=None, string=None, font=None, spacing=None, expansion=None, color=None, priority=None, viewport=None, worldcoordinate=None , x=None, y=None, height=None, angle=None, path=None, halign=None, valign=None):
        return vcs.gettextcombined(Tt_name_src, To_name_src, string,
            font, spacing, expansion, color, priority, viewport, worldcoordinate,
            x, y, height, angle, path, halign, valign)
    gettextcombined.__doc__ = vcs.manageElements.gettextcombined.__doc__
    #
    # Set alias for the secondary gettextcombined.
    gettext = gettextcombined

    def textcombined(self, *args, **parms):
        """
        Function: text or textcombined         # Generate a textcombined plot

        Description of Function:
        Plot a textcombined segment on the Vcs Canvas. If no textcombined class
        object is given, then an error will be returned.

        Example of Use:
        a=vcs.init()
        a.show('texttable')                 # Show all the existing texttable objects
        a.show('textorientation')           # Show all the existing textorientation objects
        tt=a.gettext('std','7left')         # Create instance of 'std' and '7left'
        tt.string = 'Text1'                 # Show the string "Text1" on the VCS Canvas
        tt.font=2                           # Set the text size
        tt.color = 242                      # Set the text color
        tt.angle = 45                       # Set the text angle
        tt.x=[[0.0,2.0,2.0,0.0,0.0], [0.5,1.5]] # Set the x value points
        tt.y=[[0.0,0.0,2.0,2.0,0.0], [1.0,1.0]] # Set the y value points
        a.text(tt)                          # Plot using specified text object

        Optionally you can pass a string, the coordinates and any keyword
        Example:
        x.plot('Hi',.5,.5,color=241,angle=45)
        """
        ## First check if color is a string
        if 'color' in parms.keys():
            if type(parms['color'])==type(''):
                parms['color']=self.match_color(parms['color'])

        if not isinstance(args[0],vcs.textcombined.Tc):
            args=list(args)
            ## Ok we have a user passed text object let's first create a random text combined
##             icont=1
##             while icont:
##                 n=random.randint(0,100000)
##                 try:
##                     t=self.createtextcombined('__'+str(n),'default','__'+str(n),'default')
##                     icont=0
##                 except:
##                     pass
            t=self.createtextcombined()
            t.string=[args.pop(0)]
            t.x=[args.pop(0)]
            t.y=[args.pop(0)]
            #t.list()
            for k in parms.keys():
                setattr(t,k,parms[k])
                del(parms[k])
            args.insert(0,t)
        arglist=_determine_arg_list('text',args)
        return self.__plot(arglist, parms)
    #
    # Set alias for the secondary textcombined.
    text = textcombined

    def gettextextent(self,textobject):
        """Returns the coordinate of the box surrounding a text object once printed
        Example:
        x=vcs.init()
        t=x.createtext()
        t.x=[.5]
        t.y=[.5]
        t.string=['Hello World']
        extent = x.gettextextent(t)
        print extent
        """
        if not vcs.istext(textobject):
            raise vcsError,'You must pass a text object'
        To = textobject.To_name
        Tt = textobject.Tt_name
        return self.backend.gettextextent(To,Tt)

    def match_color(self,color,colormap=None):
        return vcs.match_color(color,colormap)

    def drawtextcombined(self, Tt_name=None, To_name=None, string=None,
                 font=1, spacing=2, expansion=100, color=241,
                 height = 14, angle=0, path='right', halign = 'left',
                 valign = 'half',
                 priority=1, viewport=[0.0,1.0,0.0,1.0],
                 worldcoordinate=[0.0,1.0,0.0,1.0],
                 x=None, y=None,bg=0):
        """
 Function: drawtexttable                           # Generate and draw a texttable plot

 Description of Function:
    Generate and draw a texttable object on the VCS Canvas.

 Example of Use:
    a=vcs.init()
    a.show('texttable')                      # Show all the existing texttable objects
    tt=a.drawtexttable(Tt_name = 'red', To_name='7left', mtype='dash', size=2,
                  color=242, priority=1, viewport=[0, 2.0, 0, 2.0],
                  worldcoordinate=[0,100, 0,50]
                  x=[0,20,40,60,80,100],
                  y=[0,10,20,30,40,50] )      # Create instance of texttable object 'red'
    a.texttable(tt)                          # Plot using specified texttable object
"""
        if (Tt_name is None) or (not isinstance(Tt_name,str)):
            raise vcsError, 'Must provide string name for the texttable.'
        else:
            lot = self.listelements('texttable')
            if Tt_name not in lot:
               tt = self.createtexttable( Tt_name )
            loo = self.listelements('textorientation')
            if To_name not in loo:
               to = self.createtextorientation( To_name )
            t=self.gettextcombined( Tt_name, To_name )

        # Set the Text Table (Tt) members
        t.string = string

        # Set the Text Table (Tt) members
        t.font = font
        t.spacing = spacing
        t.expansion = expansion
        t.color = color
        t.priority = priority
        t.viewport = viewport
        t.worldcoordinate = worldcoordinate
        t.x = x
        t.y = y

        # Set the Text Orientation (To) members
        t.height = height
        t.angle = angle
        t.path = path
        t.halign = halign
        t.valign = valign

        self.text( t ,bg=bg)

        return t
    #
    # Set alias for the secondary drawtextcombined.
    drawtext = drawtextcombined


    _plot_keywords_ = ['variable','grid','xaxis','yaxis','xrev','yrev','continents','xarray','yarray',
                       'name','time','units','ymd','file_comment',
                       'xbounds','ybounds','xname','yname','xunits','yunits','xweights','yweights',
                       'comment1','comment2','comment3','comment4','hms','long_name','zaxis',
                       'zarray','zname','zunits','taxis','tarray','tname','tunits','waxis','warray',
                       'wname','wunits','bg','ratio','donotstoredisplay', 'render']



    #def replot(self):
    #    """ Clears and plots with last used plot arguments
    #    """
    #    self.clear()
    #    self.plot(*self.__last_plot_actual_args, **self.__last_plot_keyargs)

    ###########################################################################
    #                                                                         #
    # Plot wrapper for VCS.                                                   #
    #                                                                         #
    ###########################################################################
    def plot(self, *actual_args, **keyargs):

        """
Options:::
%s
%s
%s
%s
%s
    :::
 Output:::
%s
    :::

 Function: plot

 Description of plot:
    Plot an array(s) of data given a template and graphics method. The VCS template is
    used to define where the data and variable attributes will be displayed on the VCS
    Canvas. The VCS graphics method is used to define how the array(s) will be shown
    on the VCS Canvas.

 The form of the call is:
    plot(array1=None, array2=None, template_name=None, graphics_method=None,
            graphics_name=None, [key=value [, key=value [, ...]]])

            where array1 and array2 are NumPy arrays.

    Plot keywords:
      ratio [default is none]
            None: let the self.ratio attribute decide
            0,'off': overwritte self.ratio and do nothing about the ratio
            'auto': computes an automatic ratio
            '3',3: y dim will be 3 times bigger than x dim (restricted to original tempalte.data area
            Adding a 't' at the end of the ratio, makes the tickmarks and boxes move along.

    Variable attribute keys:
       comment1         = string   #Comment plotted above file_comment
       comment2         = string   #Comment plotted above comment1
       comment3         = string   #Comment plotted above comment2
       comment4         = string   #Comment plotted above comment4
       file_comment     = string   #Comment (defaults to file.comment)
       hms              = string (hh:mm:ss) #Hour, minute, second
       long_name        = string   #Descriptive variable name
       name             = string   #Variable name (defaults to var.id)
       time             = cdtime   #instance (relative or absolute),
                                    cdtime, reltime or abstime value
       units            = string   #Variable units
       ymd              = string (yy/mm/dd) #Year, month, day

    Dimension attribute keys (dimension length=n):
       [x|y|z|t|w]array = NumPy array of length n    # x or y Dimension values
       [x|y|z|t|w]array = NumPy array of length n    # x or y Dimension values
       [x|y]bounds       = NumPy array of shape (n,2) # x or y Dimension boundaries
       [x|y|z|t|w]name   = string                     # x or y Dimension name
       [x|y|z|t|w]units  = string                     # x or y Dimension units
       [x|y]weights      = NumPy array of length n    # x or y Dimension weights (used to
                                                        calculate area-weighted mean)

    CDMS object:
       [x|y|z|t|w]axis   = CDMS axis object           # x or y Axis
       grid              = CDMS grid object           # Grid object (e.g. grid=var.getGrid()
       variable          = CDMS variable object       # Variable object

    Other:
       [x|y]rev         = 0|1                         # if ==1, reverse the direction of the x
    							     or y axis
       continents	= 0,1,2,3,4,5,6,7,8,9,10,11   #	if >=1, plot continental outlines
    							     (default: plot if xaxis is
    							     longitude, yaxis is latitude -or-
    							     xname is 'longitude' and yname is
    							     'latitude'
                                                      # The continents-type values are integers
						      # ranging from 0 to 11, where:
						      #    0 signifies "No Continents"
						      #    1 signifies "Fine Continents"
						      #    2 signifies "Coarse Continents"
						      #    3 signifies "United States"
						      #    4 signifies "Political Borders"
						      #    5 signifies "Rivers"

						      # Values 6 through 11 signify the line type
                                                      # defined by the files data_continent_other7
                                                      # through data_continent_other12.

    Graphics Output in Background Mode:
       bg                 = 0|1   # if ==1, create images in the background
                                                             (Don't display the VCS Canvas)

 Note:
    More specific attributes take precedence over general attributes. In particular,
    specifie attributes override variable object attributes, dimension attributes and
    arrays override axis objects, which override grid objects, which override variable
    objects.

    For example, if both 'file_comment' and 'variable' keywords are specified, the value of
    'file_comment' is used instead of the file comment in the parent of variable. Similarly,
    if both 'xaxis' and 'grid' keywords are specified, the value of 'xaxis' takes precedence
    over the x-axis of grid.

 Example of Use:
    x=vcs.init()        # x is an instance of the VCS class object (constructor)
    x.plot(array)       # this call will use default settings for template and boxfill
    x.plot(array, 'AMIP', 'isofill','AMIP_psl') # this is specifying the template and
                                                  graphics method
    t=x.gettemplate('AMIP')        # get a predefined the template 'AMIP'
    vec=x.getvector('quick')       # get a predefined the vector graphics method 'quick'
    x.plot(array1, array2, t, vec) # plot the data as a vector using the 'AMIP' template
    x.clear()                      # clear the VCS Canvas of all plots
    box=x.createboxfill('new')     # create boxfill graphics method 'new'
    x.plot(box,t,array)            # plot array data using box 'new' and template 't'

###############################################################################################################
###########################################                      ##############################################
########################################## End plot Description ###############################################
#########################################                      ################################################
###############################################################################################################

"""
        self.__last_plot_actual_args = actual_args
        self.__last_plot_keyargs = keyargs
        passed_var = keyargs.get("variable",None)
        arglist = _determine_arg_list ( None, actual_args )
        if passed_var is not None:
            arglist[0] = cdms2.asVariable(passed_var)

        # Prevent the varglist from duplicating its contents if the GUI Canvas is in use
        try:
            sal = keyargs['sal']
            if (keyargs['sal'] == 0): del keyargs['sal']
        except:
            sal = 1

        try:
            pfile = actual_args[0].parent
            keyargs['cdmsfile'] = pfile.uri if hasattr( pfile, 'uri' ) else pfile.id
        except:
            pass

    #    try:
    #        if (self.canvas_gui.top_parent.menu.vcs_canvas_gui_settings_flg == 1): # Must be from VCDAT
    #           self.canvas_gui.dialog.dialog.configure( title = ("Visualization and Control System (VCS) GUI"))
    #    except:
    #        # Connect the VCS Canvas to the GUI
    #        if (self.canvas_gui is not None) and (sal == 1):
    #           #####################################################################################################
    #           # Charles and Dean - This command will only allow one plot on a page for the VCS Canvas GUI.        #
    #           # It is committed out so that there can be two or more plots on a page. Must keep a watch to see    #
    #           # what other problems occur without this command. See vcsmodule.c: PyVCS_connect_gui_and_canvas.    #
    #           #                                                                                                   #
    #           # self._connect_gui_and_canvas( self.winfo_id )                                                     #
    #           #####################################################################################################
    #           self.canvas_gui.dialog.dialog.configure( title = ("%i. Visualization and Control System (VCS)" % self.canvasid()))

        # Plot the data
        a = self.__plot( arglist, keyargs )

        # Continuation to remove arglist from duplicating its contents
        #if (sal == 0): arglist = []

        #for x in arglist: self.varglist.append( x ) # save the plot argument list

#        if self.canvas_gui is not None:
#            self.canvas_gui.dialog.dialog.deiconify()
            # This command makes sure that the VCS Canvas Gui is in front of the VCDAT window.
#            self.canvas_gui.dialog.dialog.transient( self.canvas_gui.top_parent )
#            self.canvas_gui.show_data_plot_info( self.canvas_gui.parent, self )
        return a
    plot.__doc__ = plot.__doc__ % (plot_2_1D_options, plot_keywords_doc,graphics_method_core,axesconvert,plot_2_1D_input, plot_output)

    def plot_filledcontinents(self,slab,template_name,g_type,g_name,bg,ratio):
        cf=cdutil.continent_fill.Gcf()
        if g_type.lower()=='boxfill':
            g=self.getboxfill(g_name)
        lons=slab.getLongitude()
        lats=slab.getLatitude()

        if lons is None or lats is None:
            return
        if g.datawc_x1>9.9E19:
            cf.datawc_x1=lons[0]
        else:
            cf.datawc_x1=g.datawc_x1
        if g.datawc_x2>9.9E19:
            cf.datawc_x2=lons[-1]
        else:
            cf.datawc_x2=g.datawc_x2
        if g.datawc_y1>9.9E19:
            cf.datawc_y1=lats[0]
        else:
            cf.datawc_y1=g.datawc_y1
        if g.datawc_y2>9.9E19:
            cf.datawc_y2=lats[-1]
        else:
            cf.datawc_y2=g.datawc_y2
        try:
            t=self.gettemplate(template_name)
            cf.plot(x=self,template=template_name,ratio=ratio)
        except Exception,err:
            print err

    def __plot (self, arglist, keyargs):

        # This routine has five arguments in arglist from _determine_arg_list
        # It adds one for bg and passes those on to Canvas.plot as its sixth arguments.

        ## First of all try some cleanup
        assert len(arglist) == 6
        xtrakw=arglist.pop(5)
        for k in xtrakw.keys():
            if k in keyargs.keys():
                raise vcsError,'Multiple Definition for '+str(k)
            else:
                keyargs[k]=xtrakw[k]
        assert arglist[0] is None or cdms2.isVariable (arglist[0])
        assert arglist[1] is None or cdms2.isVariable (arglist[1])
        assert isinstance(arglist[2],str)
        if not isinstance(arglist[3],vcsaddons.core.VCSaddon): assert isinstance(arglist[3],str)
        assert isinstance(arglist[4],str)

        if self.animate.is_playing():
            self.animate.stop()
            while self.animate.is_playing():
                pass
        ##reset animation
        self.animate.create_flg = 0

        # Store the origin template. The template used to plot may be changed below by the
        # _create_random_template function, which copies templates for modifications.
        template_origin = arglist[2]
        tmptmpl = self.gettemplate(arglist[2])
        tmptmpl.data._ratio=-999

        copy_mthd=None
        copy_tmpl=None
        if arglist[2] in ['default','default_dud']:
            if arglist[3]=='taylordiagram':
              arglist[2]="deftaylor"
                #copy_tmpl=self.createtemplate(source='deftaylor')
            #else:
            #    copy_tmpl=self.createtemplate(source=arglist[2])
        check_mthd = vcs.getgraphicsmethod(arglist[3],arglist[4])
        check_tmpl = vcs.gettemplate(arglist[2])
        # By defalut do the ratio thing for lat/lon and linear projection
        # but it can be overwritten by keyword
        Doratio = keyargs.get("ratio",None)
        doratio=str(keyargs.get('ratio',self.ratio)).strip().lower()
        if doratio[-1]=='t' and doratio[0]=='0' :
            if float(doratio[:-1])==0.: doratio='0'

        ## Check for curvilinear grids, and wrap options !
        if arglist[0] is not None:
            inGrid = arglist[0].getGrid()
        else:
            inGrid = None
        if arglist[0] is not None and arglist[1] is None and arglist[3]=="meshfill":
            if isinstance(inGrid, (cdms2.gengrid.AbstractGenericGrid,cdms2.hgrid.AbstractCurveGrid)):
                g=self.getmeshfill(arglist[4])
                if not 'wrap' in keyargs.keys() and g.wrap==[0.,0.]:
                    keyargs['wrap']=[0.,360.]
            else:
                if arglist[0].rank<2:
                    arglist[3]='yxvsx'
                    arglist[4]='default'
                else:
                    xs=arglist[0].getAxis(-1)
                    ys=arglist[0].getAxis(-2)
                    if xs.isLongitude() and ys.isLatitude() and isinstance(inGrid,cdms2.grid.TransientRectGrid):
                        arglist[1]=MV2.array(inGrid.getMesh())
                        if not 'wrap' in keyargs.keys():
                            keyargs['wrap']=[0.,360.]
                    elif ys.isLongitude() and xs.isLatitude() and isinstance(inGrid,cdms2.grid.TransientRectGrid):
                        arglist[1]=MV2.array(inGrid.getMesh())
                        if not 'wrap' in keyargs.keys():
                            keyargs['wrap']=[360.,0.]
                    else:
                        arglist[3]='boxfill'
                        copy_mthd=vcs.creategraphicsmethod('boxfill','default')
                        check_mthd = copy_mthd
                        m=self.getmeshfill(arglist[4])
                        md=self.getmeshfill()
                        if md.levels!=m.levels:
                            copy_mthd.boxfill_type='custom'
                            copy_mthd.levels=m.levels
                            copy_mthd.fillareacolors=m.fillareacolors
                        for att in ['projection',
                                    'xticlabels1',
                                    'xticlabels2',
                                    'xmtics1',
                                    'xmtics2',
                                    'yticlabels1',
                                    'yticlabels2',
                                    'ymtics1',
                                    'ymtics2',
                                    'datawc_x1',
                                    'datawc_x2',
                                    'datawc_y1',
                                    'datawc_y2',
                                    'xaxisconvert',
                                    'yaxisconvert',
                                    'legend',
                                    'ext_1',
                                    'ext_2',
                                    'missing']:
                            setattr(copy_mthd,att,getattr(m,att))
        elif arglist[0] is not None and arglist[0].rank()<2 and arglist[3] in ['boxfill','default'] and not isinstance(inGrid,cdms2.gengrid.AbstractGenericGrid):
            arglist[3]='1d'
            try:
                tmp=self.getyxvsx(arglist[4])
                #tmp.list()
            except Exception,err:
                arglist[4]='default'
        elif inGrid is not None and (arglist[0] is not None and isinstance(arglist[0],cdms2.avariable.AbstractVariable) and not isinstance(inGrid,cdms2.grid.AbstractRectGrid)) and arglist[3] in ["boxfill","default"] and arglist[4]=="default":
          arglist[3]="meshfill"

##                         arglist[4]=copy_mthd.name
        # Ok let's check for meshfill needed
        if inGrid is not None and (arglist[0] is not None and isinstance(arglist[0],cdms2.avariable.AbstractVariable) and not isinstance(arglist[0].getGrid(),cdms2.grid.AbstractRectGrid)) and arglist[3] not in ["meshfill",]:
          raise RuntimeError("You are attempting to plot unstructured grid with a method that is not meshfill")
        # preprocessing for extra keyword (at-plotting-time options)
        cmds={}
        # First of all a little preprocessing for legend !
        if 'legend' in keyargs.keys() and arglist[3]=='boxfill':
            # we now have a possible problem since it can be legend for the graphic method or the template!
            k=keyargs['legend']
            isboxfilllegend=0
            if type(k)==type({}):
#                print k.keys()
                # ok it's a dictionary if the key type is string then it's for template, else it's for boxfill
                if type(k.keys()[0])!=type(''):
                    # not a string, therefore it's boxfill !
                    isboxfilllegend=1
            elif type(k) in [type([]), type(())]:
                # ok it's a list therefore if the length is not 4 we have a boxfill legend
                if len(k)!=4 and len(k)!=5:
                    isboxfilllegend=1
                elif len(k)==5:
                    if not type(k[4]) in [type({}),type(0),type(0.)]:
                        raise vcsError, "Error, at-plotting-time argument 'legend' is ambiguous in this context\nCannot determine if it is template or boxfill keyword,\n tips to solve that:\n\tif you aim at boxfill keyword, pass legend as a dictionary, \n\tif your aim at template, add {'priority':1} at the end of the list\nCurrently legend is passed as:"+repr(k)
                    elif type(k[4])!=type({}):
                        isboxfilllegend=1
                else:
                    # ok it's length 4, now the only hope left is that not all values are between 0 and 1
                    for i in range(4):
                        if k[i]>1. or k[i]<0. : isboxfilllegend=1
                    if isboxfilllegend==0: raise vcsError, "Error, at-plotting-time argument 'legend' is ambiguous in this context\nCannot determine if it is template or boxfill keyword,\n tips to solve that:\n\tif you aim at boxfill keyword, pass legend as a dictionary, \n\tif your aim at template, add {'priority':1} at the end of the list\nCurrently legend is passed as:"+repr(k)

            # ok it is for the boxfill let's do it
            if isboxfilllegend:
                if copy_mthd is None:
                    copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                copy_mthd.legend=k
                del(keyargs['legend'])
                check_mthd = copy_mthd


        # There is no way of knowing if the template has been called prior to this plot command.
        # So it is done here to make sure that the template coordinates are normalized. If already
        # normalized, then no change will to the template.
        try: self.gettemplate( template_origin )
        except:
            pass

        ## Creates dictionary/list to remember what we changed
        slab_changed_attributes={}
        slab_created_attributes=[]
        axes_changed={}
        axes_changed2={}


        for p in keyargs.keys(): # loops through possible keywords for graphic method
            if p in [
                'projection',
                'xticlabels1',
                'xticlabels2',
                'xmtics1',
                'xmtics2',
                'yticlabels1',
                'yticlabels2',
                'ymtics1',
                'ymtics2',
                'datawc_x1',
                'datawc_y1',
                'datawc_x2',
                'datawc_y2',
                'xaxisconvert',
                'yaxisconvert',
                'label',
                'line',
                'linewidth',
                'linecolors',
                'text',
                'textcolors',
                'level',
                'level_1',
                'level_2',
                'ext_1',
                'ext_2',
                'missing',
                'color_1',
                'color_2',
                'fillareastyle',
                'fillareacolors',
                'fillareaindices',
                'levels',
                'mesh',
                'wrap',
                'marker',
                'markercolor',
                'markersize',
                'linecolor',
                'outline',
                'outfill',
                'detail',
                'max',
                'quadrans',
                'skillValues',
                'skillColor',
                'skillCoefficient',
                'referencevalue',
                'arrowlength',
                'arrowangle',
                'arrowbase',
                'scale',
                'alignement',
                'type',
                'reference',
                # Now the "special" keywords
                'worldcoordinate',
                ]:
                #if copy_mthd is None: raise vcsError, 'Error, at-plotting-time option: '+p+' is not available for graphic method type:'+arglist[3]
                if not p in ['worldcoordinate',]: # not a special keywords
                    if copy_mthd is None:
                      copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                      check_mthd = copy_mthd
                    setattr(copy_mthd,p,keyargs[p])
                elif p=='worldcoordinate':
                    if copy_mthd is None:
                      copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                      check_mthd = copy_mthd
                    setattr(copy_mthd,'datawc_x1',keyargs[p][0])
                    setattr(copy_mthd,'datawc_x2',keyargs[p][1])
                    setattr(copy_mthd,'datawc_y1',keyargs[p][2])
                    setattr(copy_mthd,'datawc_y2',keyargs[p][3])
                del(keyargs[p])
            # Now template settings keywords
            elif p in [
                'viewport',
                ]:
                if copy_tmpl is None:
                    copy_tmpl=vcs.createtemplate(source=arglist[2])
                    check_tmpl=copy_tmpl
                copy_tmpl.reset('x',keyargs[p][0],keyargs[p][1],copy_tmpl.data.x1,copy_tmpl.data.x2)
                copy_tmpl.reset('y',keyargs[p][2],keyargs[p][3],copy_tmpl.data.y1,copy_tmpl.data.y2)
                del(keyargs[p])
            # Now template and x/y related stuff (1 dir only)
            elif p[1:] in [
                'label1',
                'label2',
                ]:
                if copy_tmpl is None:
                    copy_tmpl=vcs.createtemplate(source=arglist[2])
                    check_tmpl=copy_tmpl
                k=keyargs[p]
                if type(k)!=type([]):# not a list means only priority set
                    if not type(k)==type({}):
                        setattr(getattr(copy_tmpl,p),'priority',k)
                    elif type(k)==type({}):
                        for kk in k.keys():
                            setattr(getattr(copy_tmpl,p),kk,k[kk])
                else:
                    if p[0]=='x':
                        setattr(getattr(copy_tmpl,p),'y',k[0])
                    else:
                        setattr(getattr(copy_tmpl,p),'x',k[0])
                    if type(k[-1])==type({}):
                        for kk in k[-1].keys():
                            setattr(getattr(copy_tmpl,p),kk,k[-1][kk])

                del(keyargs[p])
            # Now template and x1 and x2/y1 and y2 related stuff (1 dir only)
            elif p[1:] in [
                'mintic1',
                'mintic2',
                'tic1',
                'tic2',
                ]:
                if copy_tmpl is None:
                    copy_tmpl=vcs.createtemplate(source=arglist[2])
                    check_tmpl=copy_tmpl

                k=keyargs[p]
                if type(k)!=type([]):# not a list means only priority set
                    if not type(k)==type({}):
                        setattr(getattr(copy_tmpl,p),'priority',k)
                    elif type(k)==type({}):
                        for kk in k.keys():
                            setattr(getattr(copy_tmpl,p),kk,k[kk])
                else:
                    if p[0]=='x':
                        setattr(getattr(copy_tmpl,p),'y1',k[0])
                        setattr(getattr(copy_tmpl,p),'y2',k[1])
                    else:
                        setattr(getattr(copy_tmpl,p),'x1',k[0])
                        setattr(getattr(copy_tmpl,p),'x2',k[1])
                    if type(k[-1])==type({}):
                        for kk in k[-1].keys():
                            setattr(getattr(copy_tmpl,p),kk,k[-1][kk])

                del(keyargs[p])
            # Now template with x1, x2, x3, x4, x5
            elif p in [
                'box1','box2','box3','box4',
                'line1','line2','line3','line4',
                'data','legend',
                ]:
                if copy_tmpl is None:
                    copy_tmpl=vcs.createtemplate(source=arglist[2])
                    check_tmpl=copy_tmpl
                k=keyargs[p]
                if type(k)!=type([]):# not a list means only priority set
                    if not type(k)==type({}):
                        setattr(getattr(copy_tmpl,p),'priority',k)
                    elif type(k)==type({}):
                        for kk in k.keys():
                            setattr(getattr(copy_tmpl,p),kk,k[kk])
                else:
                    setattr(getattr(copy_tmpl,p),'x1',k[0])
                    setattr(getattr(copy_tmpl,p),'x2',k[1])
                    setattr(getattr(copy_tmpl,p),'y1',k[2])
                    setattr(getattr(copy_tmpl,p),'y2',k[3])
                    if type(k[-1])==type({}):
                        for kk in k[-1].keys():
                            setattr(getattr(copy_tmpl,p),kk,k[-1][kk])

                del(keyargs[p])
            # Now MV2 related keywords
            ## Charles note: It's here that we need to remember what changed so i can unset it later
            elif p in [
                'title',
                'comment1',
                'comment2',
                'comment3',
                'comment4',
                'source',
                'crdate',
                'crtime',
                'dataname',
                'file',
                'function',
                'transformation',
                'units',
                'id',
               ]:
                k=keyargs[p]
                if copy_tmpl is None:
                    copy_tmpl=vcs.createtemplate(source=arglist[2])
                    check_tmpl=copy_tmpl
                if getattr(getattr(check_tmpl,p),'priority')==0:
                    setattr(getattr(copy_tmpl,p),'priority',1)
                if not isinstance(k,list):# not a list means only priority set
                    if isinstance(k,dict):
                        for kk in k.keys():
                            setattr(getattr(copy_tmpl,p),kk,k[kk])
                    elif isinstance(k,int):
                        setattr(getattr(copy_tmpl,p),'priority',k)
                    elif isinstance(k,str):
                        slab_changed_attributes[p]=k
##                         if hasattr(arglist[0],p):
##                             slab_changed_attributes[p]=getattr(arglist[0],p)
##                         else:
##                             slab_created_attributes.append(p)
##                         setattr(arglist[0],p,k)
                else:
##                     if hasattr(arglist[0],p):
##                         slab_changed_attributes[p]=getattr(arglist[0],p)
##                     else:
##                         slab_created_attributes.append(p)
##                     setattr(arglist[0],p,k[0])
                    slab_changed_attributes[p]=k[0]
                    setattr(getattr(copy_tmpl,p),'x',k[1])
                    setattr(getattr(copy_tmpl,p),'y',k[2])
                    if type(k[-1])==type({}):
                        for kk in k[-1].keys():
                            setattr(getattr(copy_tmpl,p),kk,k[-1][kk])

                del(keyargs[p])
            # Now Axis related keywords
            elif p[1:] in [
                'name',
                'value',
                'units',
               ]:
                if p[0]=='x':
                    ax=arglist[0].getAxis(-1)
                    if ax is not None:
                        ax=ax.clone()
                    if keyargs.has_key('xaxis'):
                        ax=keyargs['xaxis'].clone()
                        keyargs['xaxis']=ax
                    g=arglist[0].getGrid()
                    if isinstance(g, (cdms2.gengrid.AbstractGenericGrid,cdms2.hgrid.AbstractCurveGrid)) or arglist[3].lower()=='meshfill':
                        ax=None
                        del(g)
                elif p[0]=='y':
                    ax=arglist[0].getAxis(-2)
                    if ax is not None:
                        ax=ax.clone()
                    if keyargs.has_key('yaxis'):
                        ax=keyargs['yaxis'].clone()
                        keyargs['yaxis']=ax
                    g=arglist[0].getGrid()
                    if isinstance(g, (cdms2.gengrid.AbstractGenericGrid,cdms2.hgrid.AbstractCurveGrid)) or arglist[3].lower()=='meshfill':
                        ax=None
                        del(g)
                elif p[0]=='z':
                    ax=arglist[0].getLevel()
                    if ax is not None:
                        ax=ax.clone()
                elif p[0]=='t':
                    ax=arglist[0].getTime()
                    if ax is not None:
                        ax=ax.clone()
                if not ax is None:
                    ids=arglist[0].getAxisIds()
                    for i in range(len(ids)):
                        if ax.id==ids[i]:
                            if not axes_changed.has_key(i):
                                axes_changed[i]=ax
                    if arglist[1] is not None:
                        ids2=arglist[1].getAxisIds()
                        for i in range(len(ids2)):
                            if ax.id==ids2[i]:
                                if not axes_changed2.has_key(i):
                                    axes_changed2[i]=ax
                if copy_tmpl is None:
                    check_tmpl = copy_tmpl=vcs.createtemplate(source=arglist[2])
                k=keyargs[p]
                if getattr(getattr(copy_tmpl,p),'priority')==0:
                    setattr(getattr(copy_tmpl,p),'priority',1)
                if type(k)!=type([]):# not a list means only priority set
                    if type(k)==type({}):
                        for kk in k.keys():
                            setattr(getattr(copy_tmpl,p),kk,k[kk])
                    elif type(k)==type(0):
                        setattr(getattr(copy_tmpl,p),'priority',k)
                    elif isinstance(k,str):
                        if p[1:]!='name':
                            setattr(ax,p[1:],k)
                        else:
                            try:
                                setattr(ax,'id',k)
                            except Exception,err:
##                                 print err
                                pass
                    elif k is None:
                        if p[1:]!='name':
                            setattr(ax,p[1:],'')
                        else:
                            setattr(ax,'id','')

                else:
                    if p[1:]!='name':
                        setattr(ax,p[1:],k[0])
                    else:
                        setattr(ax,'id',k)
                    setattr(getattr(copy_tmpl,p),'x',k[1])
                    setattr(getattr(copy_tmpl,p),'y',k[2])
                    if type(k[-1])==type({}):
                        for kk in k[-1].keys():
                            setattr(getattr(copy_tmpl,p),kk,k[-1][kk])

                del(keyargs[p])
            # Finally take care of commands
            elif p in [
                'pdf','ps','postscript','gif','ras',
               ]:
                cmds[p]=keyargs[p]
                del(keyargs[p])


        ## Check if datawc has time setting in it
        #if copy_mthd is None:
       #     if arglist[3]!='default':
       #         copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
       #         print "5555555"
       #     else:
       #         copy_mthd=vcs.creategraphicsmethod('boxfill',arglist[4])
       #         print "5555555bbbbbbbb"
       #     wasnone=1
##                and (type(copy_mthd.datawc_x1) in [type(cdtime.comptime(1900)),type(cdtime.reltime(0,'days since 1900'))] or \
##                type(copy_mthd.datawc_x2) in [type(cdtime.comptime(1900)),type(cdtime.reltime(0,'days since 1900'))]) \


        if (hasattr(check_mthd,'datawc_x1') and hasattr(check_mthd,'datawc_x2')) \
               and arglist[0].getAxis(-1).isTime() \
               and check_mthd.xticlabels1=='*' \
               and check_mthd.xticlabels2=='*' \
               and check_mthd.xmtics1 in ['*',''] \
               and check_mthd.xmtics2 in ['*',''] \
               and not (check_mthd.g_name in ['G1d'] and (check_mthd.flip== True or arglist[1] is not None) and arglist[0].ndim==1) : #used to be GXy GX
            ax=arglist[0].getAxis(-1).clone()
            ids=arglist[0].getAxisIds()
            for i in range(len(ids)):
                if ax.id==ids[i]:
                    if not axes_changed.has_key(i):
                        ax=ax.clone()
                        axes_changed[i]=ax
                    break
            if arglist[1] is not None:
                ids2=arglist[1].getAxisIds()
                for i in range(len(ids2)):
                    if ax.id==ids2[i]:
                        if not axes_changed2.has_key(i):
                            axes_changed2[i]=ax
            try:
                ax.toRelativeTime(check_mthd.datawc_timeunits,check_mthd.datawc_calendar)
                convertedok = True
            except:
                convertedok = False
            if (check_mthd.xticlabels1=='*' or check_mthd.xticlabels2=='*') and convertedok :#and check_mthd.g_name not in ["G1d",]: #used to be Gsp
                convert_datawc = False
                for cax in axes_changed.keys():
                    if axes_changed[cax] == ax:
                        convert_datawc = True
                        break
                if convert_datawc:
                    oax = arglist[0].getAxis(cax).clone()
                    t=type(check_mthd.datawc_x1)
                    if not t in [type(cdtime.reltime(0,'months since 1900')),type(cdtime.comptime(1900))]:
                        if copy_mthd is None:
                          copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                          check_mthd = copy_mthd
                        if check_mthd.datawc_x1>9.E19:
                            copy_mthd.datawc_x1 = cdtime.reltime(oax[0],oax.units).tocomp(oax.getCalendar()).torel(copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                        else:
                            copy_mthd.datawc_x1 = cdtime.reltime(copy_mthd.datawc_x1,oax.units).tocomp(oax.getCalendar()).torel(copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                        if copy_mthd.datawc_x2>9.E19:
                            copy_mthd.datawc_x2 = cdtime.reltime(oax[-1],oax.units).tocomp(oax.getCalendar()).torel(copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                        else:
                            copy_mthd.datawc_x2 = cdtime.reltime(copy_mthd.datawc_x2,oax.units).tocomp(oax.getCalendar()).torel(copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                if copy_mthd.xticlabels1=='*' :
                  if copy_mthd is None:
                    copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                    check_mthd = copy_mthd
                  copy_mthd.xticlabels1=vcs.generate_time_labels(copy_mthd.datawc_x1,copy_mthd.datawc_x2,copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                if copy_mthd.xticlabels2=='*' :
                  if copy_mthd is None:
                    copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                    check_mthd = copy_mthd
                  copy_mthd.xticlabels2=vcs.generate_time_labels(copy_mthd.datawc_x1,copy_mthd.datawc_x2,copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
        elif not (getattr(check_mthd,'g_name','')=='Gfm' and isinstance(arglist[0].getGrid(), (cdms2.gengrid.AbstractGenericGrid,cdms2.hgrid.AbstractCurveGrid))):
            try:
                if arglist[0].getAxis(-1).isTime():#used to GXy
                    if (check_mthd.xticlabels1=='*' and check_mthd.xticlabels2=='*' and not (check_mthd.g_name == 'G1d' and check_mthd.flip) ) \
                       and check_mthd.g_name not in ['G1d']: # used to be GSp
                        if copy_mthd is None:
                            copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                            check_mthd=copy_mthd
                        t=arglist[0].getAxis(-1).clone()
                        timeunits=t.units
                        calendar=t.getCalendar()
                        t0=cdtime.reltime(t[0],timeunits)
                        t1=cdtime.reltime(t[-1],timeunits)
                        copy_mthd.xticlabels1=vcs.generate_time_labels(t0,t1,timeunits,calendar)
            except:
                pass

        if (hasattr(check_mthd,'datawc_y1') and hasattr(check_mthd,'datawc_y2'))\
               and check_mthd.yticlabels1=='*' \
               and check_mthd.yticlabels2=='*' \
               and check_mthd.ymtics1 in ['*',''] \
               and check_mthd.ymtics2 in ['*',''] \
               and arglist[0].getAxis(-2).isTime() and (arglist[0].ndim>1 or (check_mthd.g_name == 'G1d' and check_mthd.flip)) \
               and not (check_mthd.g_name=='Gfm' and isinstance(arglist[0].getGrid(), (cdms2.gengrid.AbstractGenericGrid,cdms2.hgrid.AbstractCurveGrid))): #GXy
            ax=arglist[0].getAxis(-2).clone()
            if check_mthd.g_name == "G1d" and check_mthd.linewidth==0: # used to be  Sp
                ax = arglist[1].getAxis(-2).clone()
                axes_changed2={}
            ids=arglist[0].getAxisIds()
            for i in range(len(ids)):
                if ax.id==ids[i]:
                    if not axes_changed.has_key(i):
                        ax=ax.clone()
                        axes_changed[i]=ax
##                     else:
##                         ax=axes_changed[i]
                    break
            if arglist[1] is not None:
                ids2=arglist[1].getAxisIds()
                for i in range(len(ids2)):
                    if ax.id==ids2[i]:
                        if not axes_changed2.has_key(i):
                            axes_changed2[i]=ax
##                         else:
##                             ax=axes_changed2[i]
                        break
            try:
                ax.toRelativeTime(check_mthd.datawc_timeunits,check_mthd.datawc_calendar)
                convertedok = True
            except:
                convertedok = False
            if (check_mthd.yticlabels1=='*' or check_mthd.yticlabels2=='*') and convertedok:
                convert_datawc = False
                A=axes_changed
                if check_mthd.g_name=="G1d" and check_mthd.linewidth==0:  #GSp
                    A=axes_changed2
                for cax in A.keys():
                    if A[cax] is ax:
                        convert_datawc = True
                        break
                if convert_datawc:
                    oax = arglist[0].getAxis(cax).clone()
                    if copy_mthd is None:
                        copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                        check_mthd = copy_mthd
                    if copy_mthd.datawc_y1>9.E19:
                        copy_mthd.datawc_y1 = cdtime.reltime(oax[0],oax.units).tocomp(oax.getCalendar()).torel(copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                    else:
                        copy_mthd.datawc_y1 = cdtime.reltime(copy_mthd.datawc_y1,oax.units).tocomp(oax.getCalendar()).torel(copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                    if copy_mthd.datawc_y2>9.E19:
                        copy_mthd.datawc_y2 = cdtime.reltime(oax[-1],oax.units).tocomp(oax.getCalendar()).torel(copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                    else:
                        copy_mthd.datawc_y2 = cdtime.reltime(copy_mthd.datawc_y2,oax.units).tocomp(oax.getCalendar()).torel(copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                if check_mthd.yticlabels1=='*' :
                    if copy_mthd is None:
                        copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                        check_mthd = copy_mthd
                    copy_mthd.yticlabels1=vcs.generate_time_labels(copy_mthd.datawc_y1,copy_mthd.datawc_y2,copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
                if check_mthd.yticlabels2=='*' :
                    if copy_mthd is None:
                        copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                        check_mthd = copy_mthd
                    copy_mthd.yticlabels2=vcs.generate_time_labels(copy_mthd.datawc_y1,copy_mthd.datawc_y2,copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar)
        elif not (getattr(check_mthd,'g_name','')=='Gfm' and isinstance(arglist[0].getGrid(), (cdms2.gengrid.AbstractGenericGrid,cdms2.hgrid.AbstractCurveGrid))):
            try:
              if arglist[0].getAxis(-2).isTime() and arglist[0].ndim>1 and copy_mthd.g_name not in ["G1d",]: #['GYx','GXy','GXY','GSp']:
                    if check_mthd.yticlabels1=='*' and check_mthd.yticlabels2=='*':
                        if copy_mthd is None:
                            copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
                            check_mthd = copy_mthd
##                         print copy_mthd.datawc_y1,copy_mthd.datawc_y2,copy_mthd.datawc_timeunits,copy_mthd.datawc_calendar
                        t=arglist[0].getAxis(-2).clone()
                        timeunits=t.units
                        calendar=t.getCalendar()
                        t0=cdtime.reltime(t[0],timeunits)
                        t1=cdtime.reltime(t[-1],timeunits)
                        copy_mthd.yticlabels1=vcs.generate_time_labels(t0,t1,timeunits,calendar)
            except:
                pass

        def clean_val(value):
            if numpy.allclose(value,0.):
                return 0.
            elif value<0:
                sign=-1
                value=-value
            else:
                sign=1
            i=int(numpy.log10(value))
            if i>0:
                j=i
                k=10.
            else:
                j=i-1
                k=10.
            v=int(value/numpy.power(k,j))*numpy.power(k,j)
            return v*sign

        def mkdic(method,values):
            if method=='area_wt':
                func=numpy.sin
                func2=numpy.arcsin
            elif method=='exp':
                func=numpy.exp
                func2=numpy.log
            elif method=='ln':
                func=numpy.log
                func2=numpy.exp
            elif method=='log10':
                func=numpy.log10
            vals=[]
            for v in values:
                if method=='area_wt':
                    vals.append(func(v*numpy.pi/180.))
                else:
                    vals.append(func(v))
            min,max=vcs.minmax(vals)
            levs=vcs.mkscale(min,max)
##             levs=vcs.mkevenlevels(min,max)
            vals=[]
            for l in levs:
                if method=='log10':
                    v=numpy.power(10,l)
                elif method=='area_wt':
                    v=func2(l)/numpy.pi*180.
                else:
                    v=func2(l)
                vals.append(clean_val(v))
            dic=vcs.mklabels(vals)
            dic2={}
            for k in dic.keys():
                try:
                    if method=='area_wt':
                        dic2[func(k*numpy.pi/180.)]=dic[k]
                    else:
                        dic2[func(k)]=dic[k]
                except:
                    pass
            return dic2

        def set_convert_labels(copy_mthd,test=0):
            did_something = False
            for axc in ['x','y']:
                try:
                    mthd=getattr(copy_mthd,axc+'axisconvert')
                    if mthd!='linear':
                        for num in ['1','2']:
                            if getattr(copy_mthd,axc+'ticlabels'+num)=='*':
                                if axc=='x':
                                    axn=-1
                                else:
                                    axn=-2
                                dic=mkdic(mthd,arglist[0].getAxis(axn)[:])
                                if test==0 : setattr(copy_mthd,axc+'ticlabels'+num,dic)
                                did_something = True
                except:
                    pass
            return did_something

        if set_convert_labels(check_mthd,test=1):
            if copy_mthd is None:
              copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
              check_mthd = copy_mthd
              set_convert_labels(copy_mthd)
        if copy_mthd is None:
          copy_mthd=vcs.creategraphicsmethod(arglist[3],arglist[4])
          check_mthd = copy_mthd

        x=None
        y=None
        try:
            if arglist[0].getAxis(-1).isLongitude():
                x="longitude"
            elif arglist[0].getAxis(-1).isLatitude():
                x="latitude"
            if check_mthd.g_name=="G1d" and (check_mthd.flip or arglist[1] is not None):# in ["GXy","GXY"]:
                datawc_x1=MV2.minimum(arglist[0])
                datawc_x2=MV2.maximum(arglist[0])
                x=None
            else:
              try:
                if arglist[0].getAxis(-1).isCircularAxis():
                  datawc_x1=arglist[0].getAxis(-1)[0]
                else:
                  datawc_x1=arglist[0].getAxis(-1).getBounds()[0][0]
              except:
                datawc_x1=arglist[0].getAxis(-1)[0]
              try:
                if arglist[0].getAxis(-1).isCircularAxis():
                  datawc_x2=arglist[0].getAxis(-1)[-1]
                else:
                  datawc_x2=arglist[0].getAxis(-1).getBounds()[-1][1]
              except:
                datawc_x2=arglist[0].getAxis(-1)[-1]
            if arglist[0].getAxis(-2).isLongitude():
                y="longitude"
            elif arglist[0].getAxis(-2).isLatitude():
                y="latitude"

            if check_mthd.g_name=="G1d" and not check_mthd.flip and arglist[1] is None: # in ["GYx",]:
                datawc_y1=MV2.minimum(arglist[0])
                datawc_y2=MV2.maximum(arglist[0])
                y=None
            elif check_mthd.g_name=="G1d" and arglist[1] is not None: # in ["GYX",]:
                datawc_y1=MV2.minimum(arglist[1])
                datawc_y2=MV2.maximum(arglist[1])
                y=None
            else:
                try:
                  datawc_y1=arglist[0].getAxis(-2).getBounds()[0][0]
                except:
                  datawc_y1=arglist[0].getAxis(-2)[0]
                try:
                  datawc_y2=arglist[0].getAxis(-2).getBounds()[-1][1]
                except:
                  datawc_y2=arglist[0].getAxis(-2)[-1]
            if isinstance(arglist[0].getGrid(), (cdms2.gengrid.AbstractGenericGrid,cdms2.hgrid.AbstractCurveGrid)):
              x="longitude"
              y="latitude"
        except Exception,err:
            pass
        try:
          copy_mthd = vcs.setTicksandLabels(check_mthd,copy_mthd,datawc_x1,datawc_x2,datawc_y1,datawc_y2,x=x,y=y)
        except Exception,err:
            pass

        if not copy_mthd is None: arglist[4]=copy_mthd.name
        if not copy_tmpl is None: arglist[2]=copy_tmpl.name

        ## End of preprocessing !

        # get the background value
        bg = keyargs.get('bg', 0)

        # line added by Charles Doutriaux to plugin the taylordiagram and bypass the C code for graphic methods
        #warnings.warn("Do something about hold_continent type circa line 5386 in Canvas.py")
        hold_cont_type = self.getcontinentstype()
        if isinstance(arglist[3],str) and arglist[3].lower()=='taylordiagram':
            for p in slab_changed_attributes.keys():
                if hasattr(arglist[0],p):
                    tmp = getattr(arglist[0],p)
                else:
                    tmp = (None,None)
                setattr(arglist[0],p,slab_changed_attributes[p])
                slab_changed_attributes[p]=tmp
            # first look at the extra arguments and make sure there is no duplicate
            for k in keyargs.keys():
                if not k in ['template','skill','bg']:
                    del(keyargs[k])
                if k=='template':
                    arglist[2]=keyargs[k]
                    del(keyargs[k])
            # look through the available taylordiagram methods and use the plot function
            t = vcs.elements["taylordiagram"].get(arglist[4],None)
            if t is None:
              raise ValueError("unknown taylordiagram graphic method: %s" % arglist[4])
            t.plot(arglist[0],canvas=self,template=arglist[2],**keyargs)
            nm,src = self.check_name_source(None,"default","display")
            dn = displayplot.Dp(nm)
            dn.template = arglist[2]
            dn.g_type = arglist[3]
            dn.g_name = arglist[4]
            dn.array = arglist[:2]
            dn.extradisplays=t.displays
##                     dn.array=arglist[0]
            for p in slab_changed_attributes.keys():
                tmp = slab_changed_attributes[p]
                if tmp == (None,None):
                    delattr(arglist[0],p)
                else:
                    setattr(arglist[0],p,tmp)
            return dn
        else: #not taylor diagram
            if isinstance(arglist[3],vcsaddons.core.VCSaddon):
                gm= arglist[3]
            else:
                tp = arglist[3]
                if tp=="text":
                  tp="textcombined"
                elif tp=="default":
                  tp="boxfill"
                gm=vcs.elements[tp][arglist[4]]
                if hasattr(gm,"priority") and gm.priority==0:
                    return
            p=self.getprojection(gm.projection)
            if p.type in round_projections and (doratio=="0" or doratio[:4]=="auto"):
              doratio="1t"
            for keyarg in keyargs.keys():
                if not keyarg in self.__class__._plot_keywords_+self.backend._plot_keywords:
                     warnings.warn('Unrecognized vcs plot keyword: %s, assuming backend (%s) keyword'%(keyarg,self.backend.type))

            if arglist[0] is not None or keyargs.has_key('variable'):
                arglist[0] = self._reconstruct_tv(arglist, keyargs)
                ## Now applies the attributes change
                for p in slab_changed_attributes.keys():
                    if hasattr(arglist[0],p):
                        tmp = getattr(arglist[0],p)
                    else:
                        tmp=(None,None)
                    setattr(arglist[0],p,slab_changed_attributes[p])
                    slab_changed_attributes[p]=tmp
                ## Now applies the axes changes
                for i in axes_changed.keys():
                    arglist[0].setAxis(i,axes_changed[i])
                for i in axes_changed2.keys():
                    arglist[1].setAxis(i,axes_changed2[i])
            # Check to make sure that you have at least 2 dimensions for the follow graphics methods
##             if (len(arglist[0].shape) < 2) and (arglist[3] in ['boxfill', 'isofill', 'isoline', 'outfill', 'outline', 'vector', 'scatter']):
            ## Flipping the order to avoid the tv not exist problem
            if (arglist[3] in ['boxfill', 'isofill', 'isoline', 'outfill', 'outline', 'vector']) and (len(arglist[0].shape) < 2 ):
                raise vcsError, 'Invalid number of dimensions for %s' % arglist[3]


            ## Ok now does the linear projection for lat/lon ratio stuff
            if arglist[3] in ['marker','line','fillarea','text']:
                # fist create a dummy template
                t=self.createtemplate()
                # Now creates a copy of the primitives, in case it's used on other canvases with diferent ratios
                if arglist[3]=='text':
                    nms = arglist[4].split(":::")
                    P=self.gettext(nms[0],nms[1])
                    p = self.createtext(Tt_source=nms[0],To_source=nms[1])
                elif arglist[3]=='marker':
                    p = self.createmarker(source=arglist[4])
                elif arglist[3]=='line':
                    p = self.createline(source=arglist[4])
                elif arglist[3]=='fillarea':
                    p = self.createfillarea(source=arglist[4])
                t.data.x1 = p.viewport[0]
                t.data.x2 = p.viewport[1]
                t.data.y1 = p.viewport[2]
                t.data.y2 = p.viewport[3]

                proj = self.getprojection(p.projection)
                if proj.type in round_projections and (doratio=="0" or doratio[:4]=="auto"):
                  doratio="1t"

                if proj.type=='linear' and doratio[:4]=='auto':
                    lon1,lon2,lat2,lat2 = p.worldcoordinate
                    t.ratio_linear_projection(lon1,lon2,lat1,lat2,None,box_and_ticks=box_and_ticks)
                    p.viewport = [t.data.x1,t.data.x2,t.data.y1,t.data.y2]
                    arglist[4] = p.name
                elif not doratio in ['0','off','none','auto','autot']:
                    if doratio[-1]=='t':
                        doratio=doratio[:-1]
                    Ratio=float(doratio)
                    t.ratio(Ratio)
                    p.viewport = [t.data.x1,t.data.x2,t.data.y1,t.data.y2]
                    if arglist[3]=='text':
                        arglist[4] = p.Tt_name+':::'+p.To_name
                    else:
                        arglist[4]=p.name
                else:
                  if arglist[3]=='text' and keyargs.get("donotstoredisplay",False) is True:
                      sp = p.name.split(":::")
                      del(vcs.elements["texttable"][sp[0]])
                      del(vcs.elements["textorientation"][sp[1]])
                      del(vcs.elements["textcombined"][p.name])
                  elif arglist[3]=='marker':
                      del(vcs.elements["marker"][p.name])
                  elif arglist[3]=='line':
                      del(vcs.elements["line"][p.name])
                  elif arglist[3]=='fillarea':
                      del(vcs.elements["fillarea"][p.name])
                # cleanup temp template
                del(vcs.elements["template"][t.name])
            elif (arglist[3] in ['boxfill','isofill','isoline','outfill','outline','vector','meshfill'] or isinstance(arglist[3],vcsaddons.core.VCSaddon)) and doratio in ['auto','autot'] and not (doratio=='auto' and arglist[2]=='ASD'):
                box_and_ticks=0
                if doratio[-1]=='t' or template_origin=='default':
                    box_and_ticks=1

                if isinstance(arglist[3],vcsaddons.core.VCSaddon):
                    gm= arglist[3]
                else:
                    tp = arglist[3]
                    if tp=="text":
                      tp="textcombined"
                    gm=vcs.elements[tp][arglist[4]]
                p=self.getprojection(gm.projection)
                if p.type in round_projections:
                  doratio="1t"
                if p.type == 'linear':
                    if gm.g_name =='Gfm':
                        if self.isplottinggridded:
                            lon1,lon2=vcs.minmax(arglist[1][...,:,1,:])
                            lat1,lat2=vcs.minmax(arglist[1][...,:,0,:])
                            if lon2-lon1>360:
                                lon1,lon2=0.,360.
                            if gm.datawc_x1<9.99E19:
                                lon1=gm.datawc_x1
                            if gm.datawc_x2<9.99E19:
                                lon2=gm.datawc_x2
                            if gm.datawc_y1<9.99E19:
                                lat1=gm.datawc_y1
                            if gm.datawc_y2<9.99E19:
                                lat2=gm.datawc_y2
                            if copy_tmpl is None:
                                copy_tmpl=vcs.createtemplate(source=arglist[2])
                                arglist[2]=copy_tmpl.name
                            copy_tmpl.ratio_linear_projection(lon1,lon2,lat1,lat2,None,box_and_ticks=box_and_ticks)
                    elif arglist[0].getAxis(-1).isLongitude() and arglist[0].getAxis(-2).isLatitude():
                        if copy_tmpl is None:
                            copy_tmpl=vcs.createtemplate(source=arglist[2])
                        if gm.datawc_x1<9.99E19:
                            lon1=gm.datawc_x1
                        else:
                            lon1=min(arglist[0].getAxis(-1))
                        if gm.datawc_x2<9.99E19:
                            lon2=gm.datawc_x2
                        else:
                            lon2=max(arglist[0].getAxis(-1))
                        if gm.datawc_y1<9.99E19:
                            lat1=gm.datawc_y1
                        else:
                           lat1=min(arglist[0].getAxis(-2))
                        if gm.datawc_y2<9.99E19:
                            lat2=gm.datawc_y2
                        else:
                            lat2=max(arglist[0].getAxis(-2))
                        copy_tmpl.ratio_linear_projection(lon1,lon2,lat1,lat2,None,box_and_ticks=box_and_ticks,x=self)
                        arglist[2]=copy_tmpl.name
            elif not (doratio in ['0','off','none','auto','autot']) or  (arglist[3] in ['boxfill','isofill','isoline','outfill','outline','vector','meshfill'] and str(doratio).lower() in ['auto','autot']) and arglist[2]!='ASD' :
                box_and_ticks=0
                if doratio[-1]=='t' or template_origin=='default':
                    box_and_ticks=1
                    if doratio[-1]=='t':
                        doratio=doratio[:-1]
                try:
                    Ratio=float(doratio)
                except:
                    Ratio=doratio
                if copy_tmpl is None:
                    copy_tmpl=vcs.createtemplate(source=arglist[2])
                    arglist[2]=copy_tmpl.name
                copy_tmpl.ratio(Ratio,box_and_ticks=box_and_ticks,x=self)


            if hasattr(self,'_isplottinggridded') : del(self._isplottinggridded)
            # Get the continents for animation generation
            self.animate.continents_value = self.getcontinentstype()

            # Get the option for doing graphics in the background.
            if bg:
                arglist.append(True)
            else:
                arglist.append(False)
            if arglist[3]=='scatter':
                if not (numpy.equal(arglist[0].getAxis(-1)[:],arglist[1].getAxis(-1)[:]).all()):
                    raise vcsError, 'Error - ScatterPlot requires X and Y defined in the same place'
            if arglist[3]=='vector':
                if not (numpy.equal(arglist[0].getAxis(-1)[:],arglist[1].getAxis(-1)[:]).all()) or not(numpy.equal(arglist[0].getAxis(-2)[:],arglist[1].getAxis(-2)[:]).all()):
                    raise vcsError, 'Error - VECTOR components must be on the same grid.'
            if keyargs.has_key("bg"):
              del(keyargs["bg"])
            if isinstance(arglist[3],vcsaddons.core.VCSaddon):
                if arglist[1] is None:
                    dn = arglist[3].plot(arglist[0],template=arglist[2],bg=bg,x=self,**keyargs)
                else:
                    dn = arglist[3].plot(arglist[0],arglist[1],template=arglist[2],bg=bg,x=self,**keyargs)
            else:
                returned_kargs = self.backend.plot(*arglist,**keyargs)
                if not keyargs.get("donotstoredisplay",False):
                  nm,src = self.check_name_source(None,"default","display")
                  dn = displayplot.Dp(nm)
                  dn.template = arglist[2]
                  dn.g_type = arglist[3]
                  dn.g_name = arglist[4]
                  dn.array = arglist[:2]
                  dn.backend = returned_kargs
                else:
                  dn = None

            if dn is not None:
              dn._template_origin = template_origin
              dn.ratio=Doratio

            if self.mode!=0 :
              #self.update()
              pass
            #if not bg: pause(self.pause_time)

            # Restore the continents type
##             print 'HOLD CONTINENTS:',hold_cont_type,self.canvas.getcontinentstype()
##             self.plot_filledcontinents(arglist[0],arglist[2],arglist[3],arglist[4],bg,doratio)


        result = dn
        if isinstance(arglist[3],str):
            #warnings.warn("please restore getplot functionality in Canvas.py circa 5640")
#            result = self.getplot(dn, template_origin)
            #self.canvas.setcontinentstype(hold_cont_type)
            # Pointer to the plotted slab of data and the VCS Canas display infomation.
            # This is needed to find the animation min and max values and the number of
            # displays on the VCS Canvas.
            if dn is not None:
              self.animate_info.append( (result, arglist[:2]) )
#            self.animate.update_animate_display_list( )


        # Make sure xmainloop is started. This is needed to check for X events
        # (such as, Canvas Exposer, button or key press and release, etc.)
        #if ( (self.canvas.THREADED() == 0) and (bg == 0) ):
        #    thread.start_new_thread( self.canvas.startxmainloop, ( ) )

        # Now executes output commands
        for cc in cmds.keys():
            c=cc.lower()
            if type(cmds[cc])!=type(''):
                args=tuple(cmds[cc])
            else:
                args=(cmds[cc],)
            if c=='ps' or c=='postscript':
                apply(self.postscript,args)
            elif c=='pdf':
                apply(self.pdf,args)
            elif c=='gif':
                apply(self.gif,args)
            elif c=='eps':
                apply(self.eps,args)
            elif c=='cgm':
                apply(self.cgm,args)
            elif c=='ras':
                apply(self.ras,args)

        #self.clean_auto_generated_objects("template")
        for p in slab_changed_attributes.keys():
            tmp = slab_changed_attributes[p]
            if tmp == (None,None):
                delattr(arglist[0],p)
            else:
                setattr(arglist[0],p,tmp)
        if dn is not None:
          self.display_names.append(result.name)
          if result.g_type in ("3d_scalar", "3d_vector") and self.configurator is not None:
            self.endconfigure()
          if self.backend.bg == False and self.configurator is not None:
            self.configurator.update()

        # Commented out as agreed we shouldn't use warnings in these contexts.
        #if not hasattr(__main__,"__file__") and not bg:
        #    warnings.warn("VCS Behaviour changed, in order to interact with window, start the interaction mode with:\n x.interact()")
        return result

    def setAnimationStepper( self, stepper ):
        self.backend.setAnimationStepper( stepper )

    #############################################################################
    #                                                                           #
    # VCS utility wrapper to return the number of displays that are "ON".       #
    #                                                                           #
    #############################################################################
    def return_display_ON_num(self, *args):
        return apply(self.canvas.return_display_ON_num, args)

    #############################################################################
    #                                                                           #
    # VCS utility wrapper to return the current display names.                  #
    #                                                                           #
    #############################################################################
    def return_display_names(self, *args):
        return self.display_names

    #############################################################################
    #                                                                           #
    # VCS utility wrapper to remove the display names.                          #
    #                                                                           #
    #############################################################################
    def remove_display_name(self, *args):
        return apply(self.canvas.remove_display_name, args)

    #############################################################################
    #                                                                           #
    # CGM  wrapper for VCS.                                                     #
    #                                                                           #
    #############################################################################
    def cgm(self, file,mode='w'):
        """
 Function: cgm

 Description of Function:
    To save a graphics plot in CDAT the user can call CGM along with the name of
    the output. This routine will save the displayed image on the VCS canvas as
    a binary vector graphics that can be imported into MSWord or Framemaker. CGM
    files are in ISO standards output format.

    The CGM command is used to create or append to a cgm file. There are two modes
    for saving a cgm file: `Append' mode (a) appends cgm output to an existing cgm
    file; `Replace' (r) mode overwrites an existing cgm file with new cgm output.
    The default mode is to overwrite an existing cgm file (i.e. mode (r)).

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.cgm(o)
    a.cgm('example')           # by default a cgm file will overwrite an existing file
    a.cgm('example','w')  # 'r' will instruct cgm to overwrite an existing file
    a.cgm('example',mode='w')  # 'r' will instruct cgm to overwrite an existing file

"""
        if mode!='w':
          warnings.warn("cgm only supports 'w' mode ignoring your mode ('%s')" % mode)
        return self.backend.cgm(file)

    #############################################################################
    #                                                                           #
    # Clear VCS Canvas wrapper for VCS.                                         #
    #                                                                           #
    #############################################################################
    def clear(self, *args, **kargs):
        """
 Function: clear

 Description of Function:
    In VCS it is necessary to clear all the plots from a page. This routine
    will clear all the VCS displays on a page (i.e., the VCS Canvas object).

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.clear()

"""
        if self.animate.created():
            self.animate.close()
        if self.configurator is not None:
            self.configurator.stop_animating()
        self.animate_info=[]
        self.animate.update_animate_display_list( )
        self.backend.clear(*args,**kargs)
        for nm in self.display_names:
          del(vcs.elements["display"][nm])
        self.display_names=[]
        return

    #############################################################################
    #                                                                           #
    # Close VCS Canvas wrapper for VCS.                                         #
    #                                                                           #
    #############################################################################
    def close(self, *args, **kargs):
        """
 Function: close

 Description of Function:
    Close the VCS Canvas. It will not deallocate the VCS Canvas object.
    To deallocate the VCS Canvas, use the destroy method.

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.close()

"""
        #global gui_canvas_closed

        #finish_queued_X_server_requests( self )
        #self.canvas.BLOCK_X_SERVER()

        #   Hide the GUI
        #if (self.canvas_gui is not None):
        #   self.canvas_gui.dialog.dialog.withdraw() # just withdraw the GUI for later
        #   gui_canvas_closed = 0
        if self.configurator:
            self.endconfigure()
        # Close the VCS Canvas
        a = self.backend.close(*args,**kargs)

        # Stop the (thread) execution of the X main loop (if it is running).
        #self.canvas.stopxmainloop( )
        #self.canvas.UNBLOCK_X_SERVER()

        return a

    #############################################################################
    #                                                                           #
    # Destroy VCS Canvas Object (i.e., call the Dealloc C code).      		#
    #                                                                           #
    #############################################################################
    def destroy(self):
        """
 Function: destroy

 Description of Function:
    Destroy the VCS Canvas. It will deallocate the VCS Canvas object.

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.destory()

"""
        import gc

        # Now stop the X main loop and its thread. Also close the VCS Canvas if it
	# is visible.
#        self.canvas.stopxmainloop( )
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        del self
        gc.garbage
        gc.collect()
# This is in contruction...... I have not yet completed this. This function
# generates a segmentation fault.
#        try:
#           apply(self.canvas.destroy)
#        except:
#           pass



    #############################################################################
    #                                                                           #
    # Colormap Graphical User Interface wrapper for VCS.                        #
    #                                                                           #
    #############################################################################
    def colormapgui(self, gui_parent=None, transient=0, max_intensity=None):
        '''
 Function: colormapgui

 Description of Function:
    Run the VCS colormap interface.

    The colormapgui command is used to bring up the VCS colormap interface. The interface
    is used to select, create, change, or remove colormaps.

 Example of Use:
    a=vcs.init()
    a.colormapgui()
    a.colormapgui(max_intensity = 255)
'''
        # removing warning shouln't be used for software usage.
        #warnings.warn("The colormap gui has been removed from CDAT, you can access it via the UV-CDAT GUI.", Warning)
        return
##         _colormapgui.create(self, gui_parent=gui_parent, transient=transient, max_intensity=max_intensity)

    #############################################################################
    #                                                                           #
    # Projection Editor, Graphic User Interface wrapper for VCS.                #
    #                                                                           #
    #############################################################################
    def projectiongui(self, gui_parent=None, projection='default'):
        '''
 Function: projectiongui

 Description of Function:
    Run the VCS projection editor interface.

    The projectiongui command is used to bring up the VCS projection interface. The interface
    is used to select, create, change, or remove projections.

 Example of Use:
    a=vcs.init()
    a.projectiongui()
'''
        # removing warning shouln't be used for software usage.
        #warnings.warn("The projection gui has been removed from CDAT, you can access it via the UV-CDAT GUI.", Warning)
        return
        ## _projectiongui.create(gui_parent=gui_parent,canvas=self,projection=projection)

    #############################################################################
    #                                                                           #
    # Graphics Method Change display.                                           #
    #                                                                           #
    #############################################################################
    def change_display_graphic_method(self,display,type,name):
        '''
 Function: change_display_graphic_method

 Description of Function:
    Changes the type and graphic metohd of a display.

'''
        return apply(self.canvas.change_display_graphic_method,(display,type,name))
    #############################################################################
    #                                                                           #
    # Figures out which display is selected in graphic method editor mode       #
    #                                                                           #
    #############################################################################
    def get_selected_display(self):
        """
 Function: get_selected_display

 Description of Function:
    In GMEDITOR mode returns selected display.
    If nothing selected returns None
    """
        return apply(self.canvas.get_selected_display,())
    #############################################################################
    #                                                                           #
    # Graphics Method Graphical User Interface wrapper for VCS.                 #
    #                                                                           #
    #############################################################################
    def graphicsmethodgui(self, gm_type='boxfill', gm_name='default',
                          gui_parent=None):
        '''
 Function: graphicsmethodgui

 Description of Function:
    Run the VCS graphicsmethod interface.

    The graphicsmethodgui command is used to bring up the VCS graphics method interface.
    The interface is used to alter existing graphics method attributes.

 Example of Use:
    a=vcs.init()
    a.graphicsmethodgui('boxfill', 'quick')
'''
        # removing warning shouln't be used for software usage.
        #warnings.warn("The graphics method gui has been removed from CDAT, you can access it via the UV-CDAT GUI.", Warning)
        return
    ## _graphicsmethodgui.create( self, gm_type=gm_type, gm_name=gm_name,
    ## gui_parent=gui_parent)

    #############################################################################
    #                                                                           #
    # Template Editor Graphical User Interface wrapper for VCS.                 #
    #                                                                           #
    #############################################################################
    def templateeditor(self, template_name='default', template_orig_name='default', plot=None, gui_parent=None, canvas = None, called_from = 0):
        ##from tkMessageBox import showerror
        '''
 Function: templateeditor

 Description of Function:
    Run the VCS templateeditor GUI.

    The templateeditor command is used to bring up the VCS template editor interface.
    The interface is used to alter templates.

 Example of Use:
    a=vcs.init()
    a.templateeditor('AMIP2')
'''
        send_canvas = canvas
        if (canvas == None): send_canvas = self

        if (template_name == 'default'):
           showerror( 'Error Message to User', 'Cannot edit the "default" template. Please copy the "default" template to new name and then edit the newly created template.')
        else:
           if (self.canvas.SCREEN_MODE() == "DATA"):
              self.canvas.SCREEN_TEMPLATE_FLAG()
              t=_gui_template_editor.create(gui_parent=gui_parent, canvas=send_canvas, plot=plot, template_name=template_name, template_orig_name=template_orig_name, called_from = called_from)
              return t
           else:
              showerror( 'Error Message to User', 'VCS will only allow one Template Editor at a time. Please the close previous template editor and try again.')

    #############################################################################
    #                                                                           #
    # Send a request to turn on a picture template object in the VCS Canvas.    #
    #                                                                           #
    #############################################################################
    def _select_one(self, template_name,attr_name,X1,X2,Y1,Y2):
        # flush and block the X main loop
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        self.canvas._select_one(template_name,attr_name,X1,X2,Y1,Y2)

        self.canvas.UNBLOCK_X_SERVER()

    #############################################################################
    #                                                                           #
    # Send a request to turn off a picture template object in the VCS Canvas.   #
    #                                                                           #
    #############################################################################
    def _unselect_one(self, template_name,attr_name,X1,X2,Y1,Y2):
        # flush and block the X main loop
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        self.canvas._unselect_one(template_name,attr_name,X1,X2,Y1,Y2)

        self.canvas.UNBLOCK_X_SERVER()

    #############################################################################
    #                                                                           #
    # Set the template editor event flag to select all template objects on the  #
    # VCS Canvas.                                                               #
    #                                                                           #
    #############################################################################
    def _select_all(self):
        # flush and block the X main loop
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        self.canvas._select_all()

        self.canvas.UNBLOCK_X_SERVER()

    #############################################################################
    #                                                                           #
    # Set the template editor event flag to unselect all the template objects   #
    # on the VCS Canvas.                                                        #
    #                                                                           #
    #############################################################################
    def _unselect_all(self):
        # flush and block the X main loop
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        self.canvas._unselect_all()

        self.canvas.UNBLOCK_X_SERVER()

    #############################################################################
    #                                                                           #
    # Set the template editor mode for the VCS Canvas screen.                   #
    #                                                                           #
    #############################################################################
    def _SCREEN_TEMPLATE_FLAG(self):
         self.canvas.SCREEN_TEMPLATE_FLAG()

    #############################################################################
    #                                                                           #
    # Set the graphic method editor mode for the VCS Canvas screen.                   #
    #                                                                           #
    #############################################################################
    def _SCREEN_GM_FLAG(self):
         self.canvas.SCREEN_GM_FLAG()

    #############################################################################
    #                                                                           #
    # Set the data mode for the VCS Canvas screen.                              #
    #                                                                           #
    #############################################################################
    def _SCREEN_DATA_FLAG(self):
         self.canvas.SCREEN_DATA_FLAG()

    #############################################################################
    #                                                                           #
    # Set the screen check mode to DATA for the VCS Canvas.                     #
    #                                                                           #
    #############################################################################
    def _SCREEN_CHECKMODE_DATA_FLAG(self):
         self.canvas.SCREEN_CHECKMODE_DATA_FLAG()

    #############################################################################
    #                                                                           #
    # Return the Screen mode, either data mode or template editor mode.         #
    #                                                                           #
    #############################################################################
    def SCREEN_MODE(self, *args):
        return apply(self.canvas.SCREEN_MODE, args)

    #############################################################################
    #                                                                           #
    # Return the Screen mode, either data mode or template editor mode.         #
    #                                                                           #
    #############################################################################
    def plot_annotation(self, *args):
        apply(self.canvas.plot_annotation, args)

    def pageeditor(self, gui_parent=None, continents=None):
        '''
 Function: pageeditor

 Description of Function:
    Run the VCS page editor GUI.

    The pageeditor command is used to bring up the VCS page editor interface.
    The interface is used to design canvases.

 Example of Use:
    a=vcs.init()
    a.pageieditor()
'''
        #_pagegui.create(canvas=self, gui_parent=gui_parent)
        return _pagegui.PageDescriptionEditor(canvas=self, gui_parent=gui_parent,
                                              continents=continents)

    #############################################################################
    #                                                                           #
    # Flush X event que wrapper for VCS.                                        #
    #                                                                           #
    #############################################################################
    def flush(self, *args):
        """
 Function: flush

 Description of Function:
    The flush command executes all buffered X events in the que.

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.flush()

"""
        return apply(self.backend.flush, args)

    #############################################################################
    #                                                                           #
    # Return how many events are in the que.                                    #
    #                                                                           #
    #############################################################################
    def xpending(self, *args):
        return apply(self.canvas.xpending, args)

    #############################################################################
    #                                                                           #
    # Block the X server. It may NOT process do X11 commands.                   #
    #                                                                           #
    #############################################################################
    def BLOCK_X_SERVER(self, *args):
        return apply(self.canvas.BLOCK_X_SERVER, args)

    #############################################################################
    #                                                                           #
    # Unblock the X server. It may now proceed to do X11 commands.              #
    #                                                                           #
    #############################################################################
    def UNBLOCK_X_SERVER(self, *args):
        return apply(self.canvas.UNBLOCK_X_SERVER, args)

    #############################################################################
    #                                                                           #
    # Return whether or not it is threaded.                                     #
    #                                                                           #
    #############################################################################
    def THREADED(self, *args):
        return apply(self.canvas.THREADED, args)

    #############################################################################
    #                                                                           #
    # Geometry wrapper for VCS.                                                 #
    #                                                                           #
    #############################################################################
    def geometry(self, *args):
        """
 Function: geometry

 Description of Function:
    The geometry command is used to set the size and position of the VCS canvas.

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.geometry(450,337)

"""
        if (args[0] <= 0) or (args[1] <= 0):
           raise ValueError, 'Error -  The width and height values must be an integer greater than 0.'

        a=apply(self.backend.geometry, args)
        self.flush() # update the canvas by processing all the X events

        return a

    #############################################################################
    #                                                                           #
    # VCS Canvas Information wrapper.                                           #
    #                                                                           #
    #############################################################################
    def canvasinfo(self, *args,**kargs):
        """
 Function: canvasinfo

 Description of Function:
    Obtain the current attributes of the VCS Canvas window.

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.canvasinfo()

"""
        return self.backend.canvasinfo(*args,**kargs)

    #############################################################################
    #                                                                           #
    # Get continents type wrapper for VCS.                                      #
    #                                                                           #
    #############################################################################
    def getcontinentstype(self, *args):
        """
 Function: getcontinentstype

 Description of Function:
    Retrieve continents type from VCS. Remember the value can only be between
    0 and 11.

 Example of Use:
     a=vcs.init()
     cont_type = a.getcontinentstype() # Get the continents type
"""
        try:
          return self._continents
        except:
          return None


    ###########################################################################
    #                                                                         #
    # Postscript to GIF wrapper for VCS.                                      #
    #                                                                         #
    ###########################################################################
    def pstogif(self, filename, *opt):
        """
  Function: pstogif

  Description of Function:
     In some cases, the user may want to save the plot out as a gif image. This
     routine allows the user to convert a postscript file to a gif file.

  Example of Use:
     a=vcs.init()
     a.plot(array)
     a.pstogif('filename.ps')       # convert the postscript file to a gif file (l=landscape)
     a.pstogif('filename.ps','l')   # convert the postscript file to a gif file (l=landscape)
     a.pstogif('filename.ps','p')   # convert the postscript file to a gif file (p=portrait)
 """
        from os import popen

        # Generate the VCS postscript file
        if (filename[-3:] != '.ps'):
           filename = filename + '.ps'

        # Set the default orientation to landscape'
        if len(opt) == 0:
            orientation = 'l'
        else:
            orientation = opt[0]
        # end of if len(orientation) == 0:

        cmd1 = 'gs -r72x72 -q -sDEVICE=ppmraw -sOutputFile=- '
        cmd2flip = ' | pnmflip -cw '
        cmd3 = '| pnmcrop | ppmtogif > '

        if orientation == 'l':
            cmd = cmd1 + filename + cmd2flip + cmd3 + filename[:-2] + 'gif\n'
        elif orientation == 'p':
            cmd = cmd1 + filename + cmd3 + filename[:-2] + 'gif \n'
        else:
            cmd = '\n'
        # end if orientation == 'l':
        f=popen(cmd, 'w')
        f.close()
        return

    #############################################################################
    #                                                                           #
    # Grid wrapper for VCS.                                                     #
    #                                                                           #
    #############################################################################
    def grid(self, *args):
        """
 Function: grid

 Description of Function:
    Set the default plotting region for variables that have more dimension values
    than the graphics method. This will also be used for animating plots over the
    third and fourth dimensions.


 Example of Use:
    a=vcs.init()
    a.grid(12,12,0,71,0,45)
"""
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        p = apply(self.canvas.grid, args)

        self.canvas.UNBLOCK_X_SERVER()

        return p

    #############################################################################
    #                                                                           #
    # Landscape VCS Canvas orientation wrapper for VCS.                         #
    #                                                                           #
    #############################################################################
    def landscape(self, width=-99, height=-99, x=-99, y=-99, clear=0):
        """
 Function: landscape

 Description of Function:
    Change the VCS Canvas orientation to Landscape.

     Note: the (width, height) and (x, y) arguments work in pairs. That is, you must
           set (width, height) or (x, y) together to see any change in the VCS Canvas.

           If the portrait method is called  with arguments before displaying a VCS Canvas,
           then the arguments (width, height, x, y, and clear) will have no effect on the
           canvas.

     Known Bug: If the visible plot on the VCS Canvas is not adjusted properly, then resize
                the screen with the point. Some X servers are not handling the threads properly
                to keep up with the demands of the X client.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.landscape() # Change the VCS Canvas orientation and set object flag to landscape
    a.landscape(clear=1) # Change the VCS Canvas to landscape and clear the page
    a.landscape(width = 400, height = 337) # Change to landscape and set the window size
    a.landscape(x=100, y = 200) # Change to landscape and set the x and y screen position
    a.landscape(width = 400, height = 337, x=100, y = 200, clear=1) # Chagne to landscape and give specifications
"""
        if (self.orientation() == 'landscape'): return

        if ( ((not isinstance(width, IntType))) or ((not isinstance(height, IntType))) or
             ((not isinstance(x, IntType))) or ((not isinstance(y, IntType))) or
             ((width != -99) and (width < 0)) or ( (height != -99) and (height < 0)) or
              ((x != -99) and  (x < 0)) or ((y != -99) and (y <0)) ):
           raise ValueError, 'If specified, width, height, x, and y must be integer values greater than or equal to 0.'
        if ( ((not isinstance(clear, IntType))) and (clear not in [0,1])):
           raise ValueError, "clear must be: 0 - 'the default value for not clearing the canvas' or 1 - 'for clearing the canvas'."

        if ( (width==-99) and (height==-99) and (x==-99) and (y==-99) and (clear==0) ):
            cargs = ()
            try: dict = apply(self.canvas.canvasinfo, cargs)
            except: dict={}
            height=dict.get('width',-99)
            width=dict.get('height',-99)
            x=dict.get('x',-99)
            y=dict.get('y',-99)
        self.flush() # update the canvas by processing all the X events

        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        args = (width, height, x, y, clear)
        l = apply(self.canvas.landscape, args)

        self.canvas.UNBLOCK_X_SERVER()

        return l

    #############################################################################
    #                                                                           #
    # List Primary and Secondary elements wrapper for VCS.                      #
    #                                                                           #
    #############################################################################
    def listelements(self, *args):
        """
 Function: listelements

 Description of Function:
    Returns a Python list of all the VCS class objects.

   The list that will be returned:
   ['template', 'boxfill', 'continent', 'isofill', 'isoline', 'outfill', 'outline',
    'scatter', 'vector', 'xvsy', 'xyvsy', 'yxvsx', 'colormap', 'fillarea', 'format',
    'line', 'list', 'marker', 'text']

 Example of Use:
    a=vcs.init()
    a.listelements()
"""
        f = vcs.listelements
        L = apply(f, args)

        L.sort()

        return L

    #############################################################################
    #                                                                           #
    # update VCS's Canvas orientation wrapper for VCS.                          #
    #                                                                           #
    #############################################################################
    def updateorientation(self, *args):
        """
 Example of Use:
    a=vcs.init()
    x.updateorientation()
"""
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        a = apply(self.canvas.updateorientation, args)

        self.canvas.UNBLOCK_X_SERVER()
        return a

    #############################################################################
    #                                                                           #
    # Open VCS Canvas wrapper for VCS.                                          #
    #                                                                           #
    #############################################################################
    def open(self, *args, **kargs):
        """
 Function: open

 Description of Function:
    Open VCS Canvas object. This routine really just manages the VCS canvas. It will
    popup the VCS Canvas for viewing. It can be used to display the VCS Canvas.

 Example of Use:
    a=vcs.init()
    a.open()
"""

        a = self.backend.open(*args,**kargs)

        # Make sure xmainloop is started. This is needed to check for X events
        # (such as, Canvas Exposer, button or key press and release, etc.)
        #if ( self.canvas.THREADED() == 0 ):
        #  thread.start_new_thread( self.canvas.startxmainloop, ( ) )

        return a

    #############################################################################
    #                                                                           #
    # Return VCS Canvas ID.                                                     #
    #                                                                           #
    #############################################################################
    def canvasid(self, *args):
        '''
 Function: canvasid

 Description of Function:
    Return VCS Canvas object ID. This ID number is found at the top of the VCS Canvas
    as part of its title.

 Example of Use:
    a=vcs.init()
    a.open()
    id = a.canvasid()
'''
        return self._canvas_id

    #############################################################################
    #                                                                           #
    # Connect the VCS Canvas to the GUI.                                        #
    #                                                                           #
    #############################################################################
    def _connect_gui_and_canvas(self, *args):
        return apply(self.canvas.connect_gui_and_canvas, args)

    #############################################################################
    #                                                                           #
    # Page VCS Canvas orientation ('portrait' or 'landscape') wrapper for VCS.  #
    #                                                                           #
    #############################################################################
    def page(self, *args):
        """
 Function: page

 Description of Function:
    Change the VCS Canvas orientation to either 'portrait' or 'landscape'.

    The orientation of the VCS Canvas and of cgm and raster images is controlled by
    the PAGE command. Only portrait (y > x) or landscape (x > y) orientations are
    permitted.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.page()      # Change the VCS Canvas orientation and set object flag to portrait
"""
        finish_queued_X_server_requests( self )
        self.canvas.BLOCK_X_SERVER()

        l = apply(self.canvas.page, args)

        self.canvas.UNBLOCK_X_SERVER()

        return l

    #############################################################################
    #                                                                           #
    # Portrait VCS Canvas orientation wrapper for VCS.                          #
    #                                                                           #
    #############################################################################
    def portrait(self, width=-99, height=-99, x=-99, y=-99, clear=0):
        """
 Function: portrait

 Description of Function:
    Change the VCS Canvas orientation to Portrait.

     Note: the (width, height) and (x, y) arguments work in pairs. That is, you must
           set (width, height) or (x, y) together to see any change in the VCS Canvas.

           If the portrait method is called  with arguments before displaying a VCS Canvas,
           then the arguments (width, height, x, y, and clear) will have no effect on the
           canvas.

     Known Bug: If the visible plot on the VCS Canvas is not adjusted properly, then resize
                the screen with the point. Some X servers are not handling the threads properly
                to keep up with the demands of the X client.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.portrait()      # Change the VCS Canvas orientation and set object flag to portrait
    a.portrait(clear=1) # Change the VCS Canvas to portrait and clear the page
    a.portrait(width = 337, height = 400) # Change to portrait and set the window size
    a.portrait(x=100, y = 200) # Change to portrait and set the x and y screen position
    a.portrait(width = 337, height = 400, x=100, y = 200, clear=1) # Chagne to portrait and give specifications
"""
        if (self.orientation() == 'portrait'): return

        if ( ((not isinstance(width, int))) or ((not isinstance(height, int))) or
             ((not isinstance(x, int))) or ((not isinstance(y, int)))  or
             ((width != -99) and (width < 0)) or ( (height != -99) and (height < 0)) or
              ((x != -99) and  (x < 0)) or ((y != -99) and (y <0)) ):
           raise ValueError, 'If specified, width, height, x, and y must be integer values greater than or equal to 0.'
        if ( ((not isinstance(clear, int))) and (clear not in [0,1])):
           raise ValueError, "clear must be: 0 - 'the default value for not clearing the canvas' or 1 - 'for clearing the canvas'."

        if ( (width==-99) and (height==-99) and (x==-99) and (y==-99) and (clear==0) ):
            cargs = ()
            try: dict = apply(self.canvas.canvasinfo, cargs)
            except: dict={}
            height=dict.get('width',-99)
            width=dict.get('height',-99)
            x=dict.get('x',-99)
            y=dict.get('y',-99)
        self.flush() # update the canvas by processing all the X events

        #finish_queued_X_server_requests( self )
        #self.canvas.BLOCK_X_SERVER()

        args = (width, height, x, y, clear)
        p = self.backend.portrait(*args)

        #self.canvas.UNBLOCK_X_SERVER()
        return p

    ##########################################################################
    #                                                                        #
    # png wrapper for VCS.                                                   #
    #                                                                        #
    ##########################################################################
    def ffmpeg(self, movie, files, bitrate=1024, rate=None, options=''):
        """
 Function: ffmpeg

 Description of Function:
    MPEG output from a list of valid files.
    Note that ffmpeg is smart enough to output to more than just mpeg format

 Example of Use:
    a=vcs.init()
    #... code to generate png files ...
    # here is dummy example
    files =[]
    for i in range(10):
      x.png('my_png__%i' % i)
      files.append('my_png__%i.png' % i)
    x.ffmpeg('mymovie.mpeg','my_png_%d.png') # generates mpeg from pattern
    x.ffmpeg('mymovie.mpeg',files) # generates from list of files
    x.ffmpeg('mymovie.mpeg','my_png_%d.png',bitrate=512) # generates mpeg at 512kbit bitrate (bitrate is important to movie quality)
    x.ffmpeg('mymovie.mpeg','my_png_%d.png',rate=50) # generates movie with 50 frame per second
    x.ffmpeg('mymovie.mpeg','my_png_%d.png',options='-r 50 -b 1024k') # genrats movie at 50 frame per sec and 1024k bitrate
    NOTE : via the optins arg you can add audio file to your movie (see ffmpeg help)
    returns the output string generated by ffmpeg program
    ALWAYS overwrite output file
"""
        cmd = 'ffmpeg -y '

        if rate is not None:
            cmd+=' -r %s ' % rate
        if isinstance(files,(list,tuple)):
            rnd = "%s/.uvcdat/__uvcdat_%i" % (os.environ["HOME"],numpy.random.randint(600000000))
            Files = []
            for i,f in enumerate(files):
                fnm = "%s_%i.png" % (rnd,i)
                shutil.copy(f,fnm)
                Files.append(fnm)
            cmd+='-i %s_%%d.png' % (rnd)
        elif isinstance(files,str):
            cmd+='-i '+files
        if rate is not None:
            cmd+=' -r %s ' % rate
        if bitrate is not None:
            cmd+=' -b:v %sk' % bitrate
        cmd+=' '+options
        cmd+=' '+movie
        o = os.popen(cmd).read()
        if isinstance(files,(list,tuple)):
            for f in Files:
                os.remove(f)
        return o

    def getantialiasing(self):
        return self.backend.getantialiasing()

    def setantialiasing(self,antialiasing):
        """ Turn ON/OFF antialiasing"""
        self.backend.setantialiasing(antialiasing)

    ##########################################################################
    #                                                                        #
    # bg dims wrapper for VCS.                                               #
    #                                                                        #
    ##########################################################################
    def setbgoutputdimensions(self, width=None,height=None,units='inches'):
        """
 Function: setbgoutputdimensions

 Description of Function:
    Sets dimensions for output in bg mode.

 Example of Use:
    a=vcs.init()
    a.setbgoutputdimensions(width=11.5, height= 8.5)  # US Legal
    a.setbgoutputdimensions(width=21, height=29.7, units='cm')  # A4
"""
        if not units in ['inches','in','cm','mm','pixel','pixels','dot','dots']:
            raise Exception,"units must be on of inches, in, cm, mm, pixel(s) or dot(s)"

        dpi = 72. # dot per inches
        if units in ["in","inches"]:
            factor = 1.
        elif units == 'cm':
            factor = 0.393700787
        elif units=='mm':
            factor = 0.0393700787
        else:
            factor = 1./72
        width,height,sfactor = self._compute_width_height(width,height,factor)
        W = int(width*dpi*sfactor)
        H = int(height*dpi*sfactor)

        # if portrait then switch
        if self.isportrait() and W>H:
            tmp = W
            W= H
            H = tmp
        #in pixels?
        self.bgX = W
        self.bgY = H
        return
    # display ping
    def put_png_on_canvas(self,filename,zoom=1,xOffset=0,yOffset=0,*args,**kargs):
      self.backend.put_png_on_canvas(filename,zoom,xOffset,yOffset,*args,**kargs)

    ##########################################################################
    #                                                                        #
    # png wrapper for VCS.                                                   #
    #                                                                        #
    ##########################################################################
    def png(self, file, width=None,height=None,units=None,draw_white_background = True, **args ):

        """
 Function: png

 Description of Function:
    PNG output, dimensions set via setbgoutputdimensions

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.png('example')       # Overwrite a png file
"""
        return self.backend.png(file,width,height,units,draw_white_background, **args )

    #############################################################################
    #                                                                           #
    # pdf wrapper for VCS.                                               #
    #                                                                           #
    #############################################################################
    def pdf(self, file, width=None,height=None,units='inches'):
        """
 Function: postscript

 Description of Function:
    SVG output is another form of vector graphics.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.png('example')       # Overwrite a postscript file
    a.png('example', width=11.5, height= 8.5)  # US Legal
    a.png('example', width=21, height=29.7, units='cm')  # A4
"""
        if not units in ['inches','in','cm','mm','pixel','pixels','dot','dots']:
            raise Exception,"units must be on of inches, in, cm, mm, pixel(s) or dot(s)"

        dpi = 72. # dot per inches
        if units in ["in","inches"]:
            factor = 1.
        elif units == 'cm':
            factor = 0.393700787
        elif units=='mm':
            factor = 0.0393700787
        else:
            factor = 1./72
        width,height,sfactor = self._compute_width_height(width,height,factor)
        W = int(width*dpi*sfactor)
        H = int(height*dpi*sfactor)


        if not file.split('.')[-1].lower() in ['pdf']:
            file+='.pdf'
        return self.backend.pdf(file,W,H)
    #############################################################################
    #                                                                           #
    # SVG wrapper for VCS.                                               #
    #                                                                           #
    #############################################################################
    def svg(self, file, width=None,height=None,units='inches'):
        """
 Function: postscript

 Description of Function:
    SVG output is another form of vector graphics.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.svg('example')       # Overwrite a postscript file
    a.svg('example', width=11.5, height= 8.5)  # US Legal
    a.svg('example', width=21, height=29.7, units='cm')  # A4
"""
        if not units in ['inches','in','cm','mm','pixel','pixels','dot','dots']:
            raise Exception,"units must be on of inches, in, cm, mm, pixel(s) or dot(s)"

        dpi = 72. # dot per inches
        if units in ["in","inches"]:
            factor = 1.
        elif units == 'cm':
            factor = 0.393700787
        elif units=='mm':
            factor = 0.0393700787
        else:
            factor = 1./72
        width,height,sfactor = self._compute_width_height(width,height,factor)
        W = int(width*dpi*sfactor)
        H = int(height*dpi*sfactor)

         # if portrait then switch
        if self.isportrait() and W>H:
            tmp = W
            W= H
            H = tmp

        if not file.split('.')[-1].lower() in ['svg']:
            file+='.svg'
        return self.backend.svg(file,W,H)

    def _compute_margins(self,W,H,top_margin,bottom_margin,right_margin,left_margin,dpi):
        try:
            ci = self.canvasinfo()
            height = ci['height']
            width = ci['width']
            factor=1./72;
            size = float(width)/float(height)
        except Exception,err:
            factor=1.;
            if self.size is None:
                size = 1.2941176470588236
            else:
                size = self.size
        if bottom_margin is not None:
            bottom_margin  = bottom_margin*factor
        if left_margin is not None:
            left_margin = left_margin*factor
        if right_margin is not None:
            right_margin=right_margin*factor
        if top_margin is not None:
            top_margin  = top_margin*factor

        # now for sure factor is 1.
        factor =1.
        if left_margin is None and right_margin is None and top_margin is None and bottom_margin is None:
            # default margins
            left_margin = .25
            right_margin = .25
            top_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            bottom_margin = (H - twidth/size)/dpi - top_margin
            bottom_margin = (top_margin+bottom_margin)/2.
            top_margin=bottom_margin
        elif left_margin is None and right_margin is None and top_margin is None:    # bottom_defined
            left_margin = .25
            right_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            top_margin = (H - twidth/size)/dpi - bottom_margin
        elif left_margin is None and right_margin is None and bottom_margin is None: # top_defined
            left_margin = .25
            right_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            bottom_margin = (H)/dpi - top_margin
        elif top_margin is None and bottom_margin is None and left_margin is None:   # right defined
            left_margin = .25
            top_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            bottom_margin = (H - twidth/size)/dpi - top_margin
        elif top_margin is None and bottom_margin is None and right_margin is None:  # left defined
            right_margin = .25
            top_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            bottom_margin = (H - twidth/size)/dpi - top_margin
        elif top_margin is None and right_margin is None:                            # left defined and bottom
            right_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            top_margin = (H - twidth/size)/dpi - bottom_margin
        elif top_margin is None and left_margin is None:                             # right defined and bottom
            left_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            top_margin = (H - twidth/size)/dpi - bottom_margin
        elif bottom_margin is None and left_margin is None:                          # right defined and top
            left_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            bottom_margin = (H - twidth/size)/dpi - top_margin
        elif bottom_margin is None and right_margin is None:                         # left defined and top
            right_margin = .25
            twidth = W - (left_margin+right_margin)*dpi
            bottom_margin = (H - twidth/size)/dpi - top_margin
        elif bottom_margin is None:                                                  # all but bottom
            twidth = W - (left_margin+right_margin)*dpi
            bottom_margin = (H - twidth/size)/dpi - top_margin
        elif top_margin is None:                                                     # all but top
            twidth = W - (left_margin+right_margin)*dpi
            top_margin = (H - twidth/size)/dpi - bottom_margin
        elif right_margin is None:                                                   # all but right
            theight = H - (top_margin+bottom_margin)*dpi
            right_margin = (W - theight*size)/dpi + left_margin
        elif left_margin is None:                                                   # all but left
            theight = H - (top_margin+bottom_margin)*dpi
            left_margin = (W - theight*size)/dpi + right_margin

        return top_margin,bottom_margin,right_margin,left_margin


    def _compute_width_height(self,width,height,factor,ps=True):
        sfactor = factor
        if width is None and height is None:
            try:
                ci = self.canvasinfo()
                height = ci['height']
                width = ci['width']
                sfactor =  1./72.
                if ps is True:
                    ratio  = width/float(height)
                    if self.size == 1.4142857142857141:
                        # A4 output
                        width=29.7
                        sfactor=0.393700787
                        height= 21.
                    elif self.size == 1./1.4142857142857141:
                        width=21.
                        sfactor=0.393700787
                        height= 29.7
                    else:
                        sfactor = 1.
                        if ratio >1:
                            width=11.
                            height=width/ratio
                        else:
                            height=11.
                            width=height*ratio
            except: # canvas never opened
                if self.size is None:
                    sfactor = 1.
                    height=8.5
                    width= 11.
                elif self.size == 1.4142857142857141:
                    sfactor = 0.393700787
                    width = 29.7
                    height = 21.
                else:
                    sfactor = 1.
                    height=8.5
                    width= self.size*height
        elif width is None:
            if self.size is None:
                width = 1.2941176470588236*height
            else:
                width = self.size*height
        elif height is None:
            if self.size is None:
                height = width / 1.2941176470588236
            else:
                height = width / self.size
        ## Now forces correct aspect ratio for dumping in bg
        ## if self.iscanvasdisplayed():
        ##     info=self.canvasinfo()
        ##     ratio = float(info["height"])/float(info["width"])
        ##     if ratio < 1.:
        ##         ratio=1./ratio
        ## else:
        ##     ratio = 1.3127035830618892
        ## if height>width:
        ##     if height/width>ratio:
        ##         height=ratio*width
        ##     else:
        ##         width=height/ratio
        ## else:
        ##     if width/height>ratio:
        ##         width=ratio*height
        ##     else:
        ##         height=width/ratio
        return width,height,sfactor

    def postscript(self, file,mode='r',orientation=None,width=None,height=None,units='inches',left_margin=None,right_margin=None,top_margin=None,bottom_margin=None):
        """
 Function: postscript

 Description of Function:
    Postscript output is another form of vector graphics. It is larger than its CGM output
    counter part, because it is stored out in ASCII format.

    There are two modes for saving a postscript file: `Append' (a) mode appends postscript
    output to an existing postscript file; and `Replace' (r) mode overwrites an existing
    postscript file with new postscript output. The default mode is to overwrite an existing
    postscript file (i.e. mode (r)).


 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.postscript('example')       # Overwrite a postscript file
    a.postscript('example', 'a')  # Append postscript to an existing file
    a.postscript('example', 'r')  # Overwrite an existing file
    a.postscript('example', mode='a')  # Append postscript to an existing file
    a.postscript('example', width=11.5, height= 8.5)  # US Legal (default)
    a.postscript('example', width=21, height=29.7, units='cm')  # A4
    a.postscript('example', right_margin=.2,left_margin=.2,top_margin=.2,bottom_margin=.2)  # US Legal output and control of margins (for printer friendly output), default units 'inches'
"""
        if not units in ['inches','in','cm','mm','pixel','pixels','dot','dots']:
            raise Exception,"units must be on of inches, in, cm, mm, pixel(s) or dot(s)"

        dpi = 72. # dot per inches
        if units in ["in","inches"]:
            factor = 1.
        elif units == 'cm':
            factor = 0.393700787
        elif units=='mm':
            factor = 0.0393700787
        else:
            factor = 1./72

        # figures out width/height
        width,height,sfactor = self._compute_width_height(width,height,factor)
        W = int(width*dpi*sfactor)
        H = int(height*dpi*sfactor)

##         print "will usE:",W,H,float(W)/H
        # figures out margins

        top_margin,bottom_margin,right_margin,left_margin = self._compute_margins(W,H,top_margin,bottom_margin,right_margin,left_margin,dpi)

        R = int(right_margin*dpi)
        L = int(left_margin*dpi)
        T = int(top_margin*dpi)
        B = int(bottom_margin*dpi)

        if W>H:
            tmp = H
            H = W
            W = tmp
        # orientation keyword is useless left for backward compatibility
        if not file.split('.')[-1].lower() in ['ps','eps']:
            file+='.ps'
        if mode=='r':
            return self.backend.postscript(file,W,H,R,L,T,B)
        else:
            n=random.randint(0,10000000000000)
            psnm='/tmp/'+'__VCS__tmp__'+str(n)+'.ps'
            self.backend.postscript(psnm,W,H,R,L,T,B)
            if os.path.exists(file):
                f=open(file,'r+')
                f.seek(0,2) # goes to end of file
                f2=open(psnm)
                f.writelines(f2.readlines())
                f2.close()
                f.close()
                os.remove(psnm)
            else:
                shutil.move(psnm,file)

    #############################################################################
    #                                                                           #
    # Postscript wrapper for VCS.                                               #
    #                                                                           #
    #############################################################################
    def postscript_old(self, file,mode='r',orientation=None):
        """
 Function: postscript

 Description of Function:
    Postscript output is another form of vector graphics. It is larger than its CGM output
    counter part, because it is stored out in ASCII format. To save out a postscript file,
    VCS will first create a cgm file in the user's %s directory. Then it will
    use gplot to convert the cgm file to a postscript file in the location the user has
    chosen.

    There are two modes for saving a postscript file: `Append' (a) mode appends postscript
    output to an existing postscript file; and `Replace' (r) mode overwrites an existing
    postscript file with new postscript output. The default mode is to overwrite an existing
    postscript file (i.e. mode (r)).

    The POSTSCRIPT command is used to create a postscript file. Orientation is 'l' = landscape,
    or 'p' = portrait. The default is the current orientation of your canvas.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.postscript('example')       # Overwrite a postscript file
    a.postscript('example', 'a')  # Append postscript to an existing file
    a.postscript('example', 'r')  # Overwrite an existing file
    a.postscript('example', 'r', 'p')  # Overwrite postscript file with a portrait postscript file
    a.postscript('example', mode='a')  # Append postscript to an existing file
    a.postscript('example', orientation='r')  # Overwrite an existing file
    a.postscript('example', mode='r', orientation='p')  # Overwrite postscript file with a portrait postscript file
""" % self._dotdir
        if orientation is None:
            orientation=self.orientation()[0]
        return apply(self.canvas.postscript_old,(file,mode,orientation))

    #############################################################################
    #                                                                           #
    # Old PDF wrapper for VCS.                                                  #
    #                                                                           #
    #############################################################################
    def pdf_old(self, file,orientation=None,options='',width=None,height=None,units='inches',left_margin=None,right_margin=None,top_margin=None,bottom_margin=None):
        """
 Function: pdf

 Description of Function:
    To save out a PDF file,
    VCS will first create a cgm file in the user's %s directory. Then it will
    use gplot to convert the cgm file to a postscript file in the location the user has
    chosen. And then convert it pdf using ps2pdf

    The pdf command is used to create a pdf file. Orientation is 'l' = landscape,
    or 'p' = portrait. The default is landscape.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.pdf('example')      # Creates a landscape pdf file
    a.pdf('example','p')  # Creates a portrait pdf file
    a.pdf(file='example',orientation='p')  # Creates a portrait pdf file
    a.pdf(file='example',options='-dCompressPages=false')  # Creates a pdf file w/o compressing page, can be any option understood by ps2pdf
""" % (self._dotdir)

        n=random.randint(0,100000000000)
        if file[-3:].lower()!='pdf':
            file+='.pdf'
        psnm='/tmp/'+'__VCS__tmp__'+str(n)+'.ps'
        a=self.postscript(psnm,orientation=orientation,width=width,height=height,units=units,left_margin=left_margin,right_margin=right_margin,top_margin=top_margin,bottom_margin=bottom_margin)
        os.popen('ps2pdf14 '+options+' '+psnm+' '+file).readlines()
        os.remove(psnm)
        return a


    #############################################################################
    #                                                                           #
    # Printer wrapper for VCS.                                                  #
    #                                                                           #
    #############################################################################
    def printer(self, printer= None, orientation=None,width=None,height=None,units='inches',left_margin=None,right_margin=None,top_margin=None,bottom_margin=None):
        """
 Function: printer

 Description of Function:
    This function creates a temporary cgm file and then sends it to the specified
    printer. Once the printer received the information, then the temporary cgm file
    is deleted. The temporary cgm file is created in the user's %s directory.

    The PRINTER command is used to send the VCS Canvas plot(s) directly to the printer.
    Orientation can be either: 'l' = landscape, or 'p' = portrait.

    Note: VCS graphical displays can be printed only if the user customizes a HARD_COPY
    file (included with the VCS software) for the home system. The path to the HARD_COPY
    file must be:

              /$HOME/%s/HARD_COPY

    where /$HOME denotes the user's home directory.


    For more information on the HARD_COPY file, see URL:

    http://www-pcmdi.llnl.gov/software/vcs/vcs_guidetoc.html#1.Setup

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.printer('printer_name') # Send plot(s) to postscript printer
    a.printer('printer_name',top_margin=1,units='cm') # Send plot(s) to postscript printer with 1cm margin on top of plot
""" % (self._dotdir,self._dotdir)
        if printer is None:
            printer = (os.environ.get('PRINTER'),)

        if not units in ['inches','in','cm','mm','pixel','pixels','dot','dots']:
            raise Exception,"units must be on of inches, in, cm, mm, pixel(s) or dot(s)"

        dpi = 72. # dot per inches
        if units in ["in","inches"]:
            factor = 1.
        elif units == 'cm':
            factor = 0.393700787
        elif units=='mm':
            factor = 0.0393700787
        else:
            factor = 1./72
        # figures out width/height
        width,height,sfactor = self._compute_width_height(width,height,factor)
        W = int(width*dpi*sfactor)
        H = int(height*dpi*sfactor)
        top_margin,bottom_margin,right_margin,left_margin = self._compute_margins(W,H,top_margin,bottom_margin,right_margin,left_margin,dpi)

        R = int(right_margin*dpi)
        L = int(left_margin*dpi)
        T = int(top_margin*dpi)
        B = int(bottom_margin*dpi)

        if W>H:
            tmp = H
            H = W
            W = tmp

        return apply(self.canvas.printer, (printer,W,H,R,L,T,B))

    #############################################################################
    #                                                                           #
    # Showbg wrapper for VCS.                                                   #
    #                                                                           #
    #############################################################################
    def showbg(self, *args):
        """
 Function: showbg

 Description of Function:
    This function displays graphics segments, which are currently stored in the frame buffer,
    on the VCS Canvas. That is, if the plot function was called with the option bg = 1 (i.e.,
    background mode), then the plot is produced in the frame buffer and not visible to the
    user. In order to view  the graphics segments, this function will copy the contents of
    the frame buffer to the VCS Canvas, where the graphics can be viewed by the user.

 Example of Use:
    a=vcs.init()
    a.plot(array, bg=1)
    x.showbg()
"""
        a = apply(self.canvas.showbg, args)

        # Make sure xmainloop is started. This is needed to check for X events
        # (such as, Canvas Exposer, button or key press and release, etc.)
        if ( self.canvas.THREADED() == 0 ):
          thread.start_new_thread( self.canvas.startxmainloop, ( ) )

        return a

    #############################################################################
    #                                                                           #
    # Backing Store wrapper for VCS.                                            #
    #                                                                           #
    #############################################################################
    def backing_store(self, *args):
        """
 Function: backing_store

 Description of Function:
    This function creates a backing store pixmap for the VCS Canvas.

 Example of Use:
    a=vcs.init()
    a.backing_store()
"""
        return apply(self.canvas.backing_store, args)

    #############################################################################
    #                                                                           #
    # Update the animation slab. Used only for the VCS Canvas GUI.              #
    #                                                                           #
    #############################################################################
    def update_animation_data(self, *args):
        return apply(self.canvas.update_animation_data, args)

    #############################################################################
    #                                                                           #
    # Return the dimension information. Used only for the VCS Canvas GUI.       #
    #                                                                           #
    #############################################################################
    def return_dimension_info(self, *args):
        return apply(self.canvas.return_dimension_info, args)

    #############################################################################
    #                                                                           #
    # Raster wrapper for VCS.                                                   #
    #                                                                           #
    #############################################################################
    def raster(self, file, mode='a'):
        """
 Function: raster

 Description of Function:
    In some cases, the user may want to save the plot out as an raster image. This
    routine allows the user to save the VCS canvas output as a SUN raster file.
    This file can be converted to other raster formats with the aid of xv and other
    such imaging tools found freely on the web.

    If no path/file name is given and no previously created raster file has been
    designated, then file

    /$HOME/%s/default.ras

    will be used for storing raster images. However, if a previously created raster
    file is designated, that file will be used for raster output.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.raster('example','a')   # append raster image to existing file
    a.raster('example','r')   # overwrite existing raster file
    a.raster(file='example',mode='r')   # overwrite existing raster file
"""  % (self._dotdir)
        return apply(self.canvas.raster, (file,mode))

    #############################################################################
    #                                                                           #
    # Reset grid wrapper for VCS.                                               #
    #                                                                           #
    #############################################################################
    def resetgrid(self, *args):
        """
 Function: resetgrid

 Description of Function:
    Set the plotting region to default values.

 Example of Use:
    Not Working!
"""
        return apply(self.canvas.resetgrid, args)

    #############################################################################
    #                                                                           #
    # Script wrapper for VCS.                                                   #
    #                                                                           #
    #############################################################################
    def _scriptrun(self, *args):
      return vcs._scriptrun(*args)

    def scriptrun(self, aFile, *args, **kargs):
      vcs.scriptrun(aFile,*args,**kargs)

    #############################################################################
    #                                                                           #
    # Set default graphics method and template wrapper for VCS.                 #
    #                                                                           #
    #############################################################################
    def set(self, *args):
        """
 Function: set

 Description of Function:
    Set the default VCS primary class objects: template and graphics methods.
    Keep in mind the template, determines the appearance of each graphics segment;
    the graphic method specifies the display technique; and the data defines what
    is to be displayed. Note, the data cannot be set with this function.

 Example of Use:
    a=vcs.init()
    a.set('isofill','quick') # Changes the default graphics method to Isofill: 'quick'
    a.plot(array)
"""
        return apply(self.canvas.set, args)

    #############################################################################
    #                                                                           #
    # Touch all segements displayed on the VCS Canvas.                          #
    #                                                                           #
    #############################################################################
    #def updateVCSsegments(self, *args):
    #    finish_queued_X_server_requests( self )
    #    self.canvas.BLOCK_X_SERVER()
#
#        a = apply(self.canvas.updateVCSsegments, args)
#
#        self.canvas.UNBLOCK_X_SERVER()
#        return a

    #############################################################################
    #                                                                           #
    # Set VCS color map wrapper for VCS.                                        #
    #                                                                           #
    #############################################################################
    def setcolormap(self, name):
        """
 Function: setcolormap

 Description of Function:
    It is necessary to change the colormap. This routine will change the VCS
    color map.

    If the the visul display is 16-bit, 24-bit, or 32-bit TrueColor, then a redrawing
    of the VCS Canvas is made evertime the colormap is changed.

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.setcolormap("AMIP")
"""
        # Don't update the VCS segment if there is no Canvas. This condition
        # happens in the initalize function for VCDAT only. This will cause a
        # core dump is not checked.
        #try:
        #   updateVCSsegments_flag = args[1]
        #except:
        #   updateVCSsegments_flag = 1
        self.colormap = name
        self.update()
        return

    #############################################################################
    #                                                                           #
    # Set VCS color map cell wrapper for VCS.                                   #
    #                                                                           #
    #############################################################################
    def setcolorcell(self, *args):
        """
 Function: setcolorcell

 Description of Function:
    Set a individual color cell in the active colormap. If default is
    the active colormap, then return an error string.

    If the the visul display is 16-bit, 24-bit, or 32-bit TrueColor, then a redrawing
    of the VCS Canvas is made evertime the color cell is changed.

    Note, the user can only change color cells 0 through 239 and R,G,B
    value must range from 0 to 100. Where 0 represents no color intensity
    and 100 is the greatest color intensity.

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.setcolormap("AMIP")
    a.setcolorcell(11,0,0,0)
    a.setcolorcell(21,100,0,0)
    a.setcolorcell(31,0,100,0)
    a.setcolorcell(41,0,0,100)
    a.setcolorcell(51,100,100,100)
    a.setcolorcell(61,70,70,70)

"""

        a=vcs.setcolorcell(self.colormap, *args)
        return a

    #############################################################################
    #                                                                           #
    # Set continents type wrapper for VCS.                           		#
    #                                                                           #
    #############################################################################
    def setcontinentstype(self, value):
      """
 Function: setcontinentstype

 Description of Function:
    One has the option of using continental maps that are predefined or that
    are user-defined. Predefined continental maps are either internal to VCS
    or are specified by external files. User-defined continental maps are
    specified by additional external files that must be read as input.

    The continents-type values are integers ranging from 0 to 11, where:
        0 signifies "No Continents"
        1 signifies "Fine Continents"
        2 signifies "Coarse Continents"
        3 signifies "United States" (with "Fine Continents")
        4 signifies "Political Borders" (with "Fine Continents")
        5 signifies "Rivers" (with "Fine Continents")

    Values 6 through 11 signify the line type defined by the files
    data_continent_other7 through data_continent_other12.

    You can also pass a file

 Example of Use:
    a=vcs.init()
    a.setcontinentstype(3)
    #a.setcontinentstype(os.environ["HOME"]+"/.uvcdat/data_continents_states")
    a.plot(array,'default','isofill','quick')
"""
      nms = ["fine","coarse","states","political","river","other6","other7","other8","other9","other10","other11","other12"]
      if isinstance(value,int):
        if value == 0:
          self._continents = None
        elif 0<value<12:
          self._continents = os.path.join(os.environ.get("HOME",""),os.environ.get(vcs.getdotdirectory()[1],vcs.getdotdirectory()[0]),"data_continent_%s" % nms[value-1])
          if not os.path.exists(self._continents):
            #fallback on installed with system one
            self._continents = os.path.join(vcs.prefix,"share","vcs","data_continent_%s" % nms[value-1])
        else:
          raise Exception("Error continents value must be file or int < 12")
      elif isinstance(value,str):
        self._continents = value
      else:
        self._continents=None
      if self._continents is not None and not os.path.exists(self._continents):
        warnings.warn("Continents file not found: %s, substituing with coarse continents" % self._continents)
        self._continents = os.path.join(os.environ.get("HOME",""),os.environ.get(vcs.getdotdirectory()[1],vcs.getdotdirectory()[0]),"data_continent_coarse")
        if not  os.path.exists(self._continent):
          self._continents = os.path.join(vcs.prefix,"share","vcs","data_continent_coarse")
        return

    #############################################################################
    #                                                                           #
    # Screen GIF wrapper for VCS.                                               #
    #                                                                           #
    #############################################################################
    def gif(self, filename='noname.gif', merge='r', orientation=None, geometry='1600x1200'):
        """
 Function: gif

 Description of Function:
    In some cases, the user may want to save the plot out as a gif image. This
    routine allows the user to save the VCS canvas output as a SUN gif file.
    This file can be converted to other gif formats with the aid of xv and other
    such imaging tools found freely on the web.

    If no path/file name is given and no previously created gif file has been
    designated, then file

        /$HOME/%s/default.gif

    will be used for storing gif images. However, if a previously created gif
    file is designated, that file will be used for gif output.

    By default, the page orientation is in Landscape mode (l). To translate the page
    orientation to portrait mode (p), set the orientation = 'p'.

    The GIF command is used to create or append to a gif file. There are two modes
    for saving a gif file: `Append' mode (a) appends gif output to an existing gif
    file; `Replace' (r) mode overwrites an existing gif file with new gif output.
    The default mode is to overwrite an existing gif file (i.e. mode (r)).

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.gif(filename='example.gif', merge='a', orientation='l', geometry='800x600')
    a.gif('example')         # overwrite existing gif file (default is merge='r')
    a.gif('example',merge='r')  # overwrite existing gif file
    a.gif('example',merge='a')     # merge gif image into existing gif file
    a.gif('example',orientation='l') # merge gif image into existing gif file with landscape orientation
    a.gif('example',orientation='p') # merge gif image into existing gif file with portrait orientation
    a.gif('example',geometry='600x500') # merge gif image into existing gif file and set the gif geometry
""" % (self._dotdir)
        if orientation is None:
            orientation=self.orientation()[0]
        g = geometry.split('x')
        f1 = f1=float(g[0]) / 1100.0 * 100.0
        f2 = f2=float(g[1]) / 849.85 * 100.0
        geometry = "%4.1fx%4.1f" % (f2,f1)
        nargs = ('gif', filename, merge, orientation, geometry)
        return self.backend.gif(nargs)

    #############################################################################
    #                                                                           #
    # Screen GhostScript (gs) wrapper for VCS.                                  #
    #                                                                           #
    #############################################################################
    def gs(self, filename='noname.gs', device='png256', orientation=None, resolution='792x612'):
        """
 Function: gs

 Description of Function:
    This routine allows the user to save the VCS canvas in one of the many
    GhostScript (gs) file types (also known as devices). To view other
    GhostScript devices, issue the command "gs --help" at the terminal
    prompt. Device names include: bmp256, epswrite, jpeg, jpeggray,
    pdfwrite, png256, png16m, sgirgb, tiffpack, and tifflzw. By default
    the device = 'png256'.

    If no path/file name is given and no previously created gs file has been
    designated, then file

        /$HOME/%s/default.gs

    will be used for storing gs images. However, if a previously created gs
    file exist, then this output file will be used for storage.

    By default, the page orientation is the canvas' orientation.
    To translate the page orientation to portrait mode (p), set the parameter orientation = 'p'.
    To translate the page orientation to landscape mode (l), set the parameter orientation = 'l'.

    The gs command is used to create a single gs file at this point. The user
    can use other tools to append separate image files.

 Example of Use:
    a=vcs.init()
    a.plot(array)
    a.gs('example') #defaults: device='png256', orientation='l' and resolution='792x612'
    a.gs(filename='example.tif', device='tiffpack', orientation='l', resolution='800x600')
    a.gs(filename='example.pdf', device='pdfwrite', orientation='l', resolution='200x200')
    a.gs(filename='example.jpg', device='jpeg', orientation='p', resolution='1000x1000')
""" % (self._dotdir)
        if orientation is None:
            orientation=self.orientation()[0]
        r = resolution.split('x')
        f1 = f1=float(r[0]) / 1100.0 * 100.0
        f2 = f2=float(r[1]) / 849.85 * 100.0
        resolution = "%4.1fx%4.1f" % (f2,f1)
        nargs = (filename, device, orientation, resolution)
        return apply(self.canvas.gs, nargs)

    #############################################################################
    #                                                                           #
    # Screen Encapsulated PostScript wrapper for VCS.                           #
    #                                                                           #
    #############################################################################
    def eps(self, file, mode='r',orientation=None,width=None,height=None,units='inches',left_margin=None,right_margin=None,top_margin=None,bottom_margin=None):
        """
        Function: Encapsulated PostScript

        Description of Function:
        In some cases, the user may want to save the plot out as an Encapsulated
        PostScript image. This routine allows the user to save the VCS canvas output
        as an Encapsulated PostScript file.
        This file can be converted to other image formats with the aid of xv and other
        such imaging tools found freely on the web.


        Example of Use:
        a=vcs.init()
        a.plot(array)
        a.postscript('example')       # Overwrite a postscript file
        a.postscript('example', 'a')  # Append postscript to an existing file
        a.postscript('example', 'r')  # Overwrite an existing file
        a.postscript('example', mode='a')  # Append postscript to an existing file
        a.postscript('example', width=11.5, height= 8.5)  # US Legal (default)
        a.postscript('example', width=21, height=29.7, units='cm')  # A4
        a.postscript('example', right_margin=.2,left_margin=.2,top_margin=.2,bottom_margin=.2)  # US Legal output and control of margins (for printer friendly output), default units 'inches'
        """
        ext = file.split(".")[-1]
        if ext.lower()!='eps':
            file=file+'.eps'
        num = numpy.random.randint(100000000000)
        tmpfile = "/tmp/vcs_tmp_eps_file_%i.ps" % num
        if mode=='a' and os.path.exists(file):
            os.rename(file,tmpfile)
        self.postscript(tmpfile,mode,orientation,width,height,units,left_margin,right_margin,top_margin,bottom_margin)
        os.popen("ps2epsi %s %s" % ( tmpfile, file)).readlines()
        os.remove(tmpfile)

    #############################################################################
    #                                                                           #
    # Show VCS primary and secondary elements wrapper for VCS.                  #
    #                                                                           #
    #############################################################################
    def show(self, *args):
      return vcs.show(*args)
    show.__doc__=vcs.__doc__

    #############################################################################
    #                                                                           #
    # Look if a graphic method is in a file           .                         #
    #                                                                           #
    #############################################################################
    def isinfile(self,GM,file=None):
        """ Checks if a graphic method is stored in a file
        if no file name is passed then looks into the initial.attributes file"""
        nm=GM.name
        gm=GM.g_name
        key=gm+'_'+nm+'('
        if file is None:
            file=os.path.join(os.environ['HOME'],self._dotdir,'initial.attributes')
        f=open(file,'r')
        for ln in f.xreadlines():
            if ln.find(key)>-1:
                f.close()
                return 1
        return 0
    #############################################################################
    #                                                                           #
    # Save VCS initial.attribute file  wrapper for VCS.                         #
    #                                                                           #
    #############################################################################
    def saveinitialfile(self):
        """
 Function: saveinitialfile                      # Save initial.attribute file

 Description of Function:
    At start-up, VCS reads a script file named initial.attributes that
    defines the initial appearance of the VCS Interface. Although not
    required to run VCS, this initial.attributes file contains many
    predefined settings to aid the beginning user of VCS. The path to
    the file must be:

         /$HOME/%s/initial.attributes

    The contents of the initial.attributes file can be customized by
    the user.

 Example of Use:
    a=vcs.init()
    ...

    a.saveinitialfile()

 WARNING: This removes first ALL object genrated automatically (i.e. whose name starts with '__') in order to preserve this, rename objects first
 e.g:
    b=a.createboxfill()
    b.name='MyBoxfill'

 # graphic method is now preserved
""" % (self._dotdir)
        self.clean_auto_generated_objects()
        return vcs.saveinitialfile()


    #############################################################################
    #                                                                           #
    # Script to a file the current state of VCS wrapper for VCS.                #
    #                                                                           #
    #############################################################################
    def scriptstate(self,script_name):
        """
 Function: scriptstate       # Save state of VCS

 Description of Function:
    The VCS scripting capability serves many purposes. It allows one to save the
    system state for replay in a later session; to save primary and secondary
    element attributes for use in later visual presentations; to save a sequence
    of interactive operations for replay; or to recover from a system failure.

 Example of Use:
    a=vcs.init()
    ...

    a.scriptstate(script_filename)
"""
        msg = _vcs.scriptstate(script_name)
        # Now adds the taylordiagram stuff
        for td in vcs.taylordiagrams:
            td.script(script_name)
        return msg

    #############################################################################
    #                                                                           #
    # Raise VCS Canvas to the top of all its siblings.                          #
    #                                                                           #
    #############################################################################
    def canvasraised(self, *args):
        """
 Function: canvasraised                         # Raise the VCS Canvas to the top

 Description of Function:
    This function marks a VCS Canvas as eligible to be displayed and
    positions the window at the top of the stack of its siblings.

 Example of Use:
    a=vcs.init()
    ...

    a.canvasraised()
"""

        return  apply(self.canvas.canvasraised, args)

    #############################################################################
    #                                                                           #
    # Returns 1 if a VCS Canvas is displayed on the screen. Returns a 0 if no   #
    # VCS Canvas is displayed on the screen.                                    #
    #                                                                           #
    #############################################################################
    def iscanvasdisplayed(self, *args):
        """
 Function: iscanvasdisplayed          # Return 1 if a VCS Canvas is displayed

 Description of Function:
    This function returns a 1 if a VCS Canvas is displayed or a 0 if
    no VCS Canvas is displayed on the screen.

 Example of Use:
    a=vcs.init()
    ...

    a.iscanvasdisplayed()
"""

        return  apply(self.canvas.iscanvasdisplayed, args)

    #############################################################################
    #                                                                           #
    # Is VCS's orientation landscape?                                           #
    #                                                                           #
    #############################################################################
    def islandscape(self):
        """
 Function: islandscape

 Description of Function:
    Indicates if VCS's orientation is landscape.

    Returns a 1 if orientation is landscape.
    Otherwise, it will return a 0, indicating false (not in landscape mode).

 Example of Use:
    a=vcs.init()
    ...

    if a.islandscape():
       a.portrait()               # Set VCS's orientation to portrait mode
"""
        if (self.orientation() == 'landscape'):
            return 1
        else:
            return 0

    #############################################################################
    #                                                                           #
    # Is VCS's orientation portrait?                                            #
    #                                                                           #
    #############################################################################
    def isportrait(self):
        """
 Function: isportrait

 Description of Function:
    Indicates if VCS's orientation is portrait.

    Returns a 1 if orientation is portrait.
    Otherwise, it will return a 0, indicating false (not in portrait mode).

 Example of Use:
    a=vcs.init()
    ...

    if a.isportrait():
       a.landscape()               # Set VCS's orientation to landscape mode
"""
        if (self.orientation() == 'portrait'):
            return 1
        else:
            return 0
    #############################################################################
    #                                                                           #
    # Dislplay plot functions for VCS.                                          #
    #                                                                           #
    #############################################################################
    def getplot(self, Dp_name_src='default', template=None):
        """
 Function: getplot                  # Get existing display plot

 Description of Function:
    This function will create a display plot object from an existing display
    plot object from an existing VCS plot. If no display plot name
    is given, then None is returned.

 Example of Use:
    a=vcs.init()
    a.show('template')                  # Show all the existing templates
    plot1=a.getplot('dpy_plot_1')       # plot1 instance of 'dpy_plot_1' display plot
"""
        if not isinstance(Dp_name_src,str):
           raise ValueError, 'Error -  The argument must be a string.'

        Dp_name = None
        display = displayplot.Dp(self, Dp_name, Dp_name_src, 1)
        if template is not None:
            display._template_origin = template
        return display

    #############################################################################
    #                                                                           #
    # Colormap functions for VCS.                                               #
    #                                                                           #
    #############################################################################
    def createcolormap(self,Cp_name=None, Cp_name_src='default'):
        return vcs.createcolormap(Cp_name,Cp_name_src)
    createcolormap.__doc__ = vcs.manageElements.createcolormap.__doc__

    def getcolormap(self,Cp_name_src='default'):
        return vcs.getcolormap(Cp_name_src)
    getcolormap.__doc__ = vcs.manageElements.getcolormap.__doc__


    #############################################################################
    #                                                                           #
    # Font functions.                       #
    #                                                                           #
    #############################################################################
    def addfont(self, path,name=""):
        """
        Add a font to VCS, path then a name you'd like to associate it with
        """
        if not os.path.exists(path):
            raise ValueError, 'Error -  The font path does not exists'
        if os.path.isdir(path):
            dir_files=[]
            files=[]
            if name=="":
                subfiles = os.listdir(path)
                for file in subfiles:
                    dir_files.append(os.path.join(path,file))
            elif name=='r':
                for root,dirs,subfiles in os.walk(path):
                    for file in subfiles:
                        dir_files.append(os.path.join(root,file))
            for f in dir_files:
                if f.lower()[-3:]in ['ttf','pfa','pfb']:
                    files.append([f,""])
        else:
            files=[[path,name],]

        nms = []
        for f in files:
            fnm,name = f
            i = max(vcs.elements["fontNumber"].keys())+1
            vcs.elements["font"][name]=fnm
            vcs.elements["fontNumber"][i]=name
        if len(nms)==0:
            raise vcsError,'No font Loaded'
        elif len(nms)>1:
            return nms
        else:
            return nms[0]


    def getfontnumber(self, name):
        """
        get the font number associated with a font name
        """
        return vcs.getfontnumber(name)

    def getfontname(self, number):
        """
        get the font name associated with a font number
        """
        return vcs.getfontname(number)

    def getfont(self, font):
        """
        get the font name/number associated with a font number/name
        """
        if isinstance(font,int):
            return self.getfontname(font)
        elif isinstance(font,str):
            return self.getfontnumber(font)
        else:
            raise vcsError,"Error you must pass a string or int"

    def switchfonts(self,font1,font2):
        """ Switch 2 font indexes, you can pass either the font names or indexes """
        if isinstance(font1,str):
            index1 = self.getfont(font1)
        elif isinstance(font1,(int,float)):
            index1 = int(font1)
            nm = self.getfont(index1) # make sure font exists
        else:
            raise vcsError,"Error you must pass either a number or font name!, you passed for font 1: %s" % font1
        if isinstance(font2,str):
            index2 = self.getfont(font2)
        elif isinstance(font2,(int,float)):
            index2 = int(font2)
            nm = self.getfont(index2) # make sure font exists
        else:
            raise vcsError,"Error you must pass either a number or font name!, you passed for font 2: %s" % font2

        return apply(self.canvas.switchfontnumbers,(index1,index2))

    def copyfontto(self,font1,font2):
        """ copy name and path of font 1 into font 2, you can pass either the font names or indexes """
        if isinstance(font1,str):
            index1 = self.getfont(font1)
        elif isinstance(font1,(int,float)):
            index1 = int(font1)
            nm = self.getfont(index1) # make sure font exists
        else:
            raise vcsError,"Error you must pass either a number or font name!, you passed for font 1: %s" % font1
        if isinstance(font2,str):
            index2 = self.getfont(font2)
        elif isinstance(font2,(int,float)):
            index2 = int(font2)
            nm = self.getfont(index2) # make sure font exists
        else:
            raise vcsError,"Error you must pass either a number or font name!, you passed for font 2: %s" % font2
        return apply(self.canvas.copyfontto,(index1,index2))

    def setdefaultfont(self,font):
        """Sets the passed font as the default font for vcs"""
        if isinstance(font,str):
            font = self.getfont(font)
        return self.copyfontto(font,1)

    #############################################################################
    #                                                                           #
    # Orientation VCS Canvas orientation wrapper for VCS.                       #
    #                                                                           #
    #############################################################################
    def orientation(self, *args, **kargs):
        """
 Function: orientation

 Description of Function:
    Return VCS's orientation. Will return either Portrait or Landscape.

 Example of Use:
    a=vcs.init()
    a.orientation()      # Return either "landscape" or "portrait"
"""
        return self.backend.orientation(*args,**kargs)

    #############################################################################
    #                                                                           #
    # Get VCS color map cell wrapper for VCS.                                   #
    #                                                                           #
    #############################################################################
    def getcolorcell(self, *args):
        """
 Function: getcolorcell

 Description of Function:
    Get an individual color cell in the active colormap. If default is
    the active colormap, then return an error string.

    If the the visul display is 16-bit, 24-bit, or 32-bit TrueColor, then a redrawing
    of the VCS Canvas is made evertime the color cell is changed.

    Note, the user can only change color cells 0 through 239 and R,G,B
    value must range from 0 to 100. Where 0 represents no color intensity
    and 100 is the greatest color intensity.

 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.setcolormap("AMIP")
    a.getcolorcell(11,0,0,0)
    a.getcolorcell(21,100,0,0)
    a.getcolorcell(31,0,100,0)
    a.getcolorcell(41,0,0,100)
    a.getcolorcell(51,100,100,100)
    a.getcolorcell(61,70,70,70)

"""
        return vcs.getcolorcell(args[0],self)

    #############################################################################
    #                                                                           #
    # Get VCS color map name wrapper for VCS.                                   #
    #                                                                           #
    #############################################################################
    def getcolormapname(self, *args):
        """
 Function: getcolormapcell

 Description of Function:
    Get colormap name of the active colormap.


 Example of Use:
    a=vcs.init()
    a.plot(array,'default','isofill','quick')
    a.getcolormapname()
"""
        return self.colormap

    def dummy_user_action(self,*args,**kargs):
        print 'Arguments:',args
        print 'Keywords:',kargs
        return None

#############################################################################
#                                                                           #
# Primarily used for reseting the animation date and time string.           #
#                                                                           #
#############################################################################
def change_date_time(tv, number):
    timeaxis = tv.getTime()
    if timeaxis is not None:
        try:
            tobj = cdtime.reltime(timeaxis[number], timeaxis.units)
            cobj = tobj.tocomp(timeaxis.getCalendar())
            tv.date = '%s/%s/%s\0'%(cobj.year, cobj.month, cobj.day)
            tv.time = '%s:%s:%s\0'%(cobj.hour, cobj.minute, cobj.second)
        except:
            pass

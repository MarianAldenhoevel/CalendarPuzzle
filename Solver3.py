# -*- coding: utf-8 -*-
'''
@author: Marian Aldenhövel <marian.aldenhoevel@marian-aldenhoevel.de>
'''

from calendar import Calendar
import math
import logging
import shutil
import os
import random
import uuid
import glob
import sys
import time
import copy
#import simpleaudio
import datetime
import argparse 
import math
import json
import calendar
import portalocker
import platform

# Global variables
starttime = datetime.datetime.now().replace(microsecond=0)
options = None
finalpositions = 0

# Given a 2D-array set a True at coords. Resize as required padding
# with None. 
def PolyArrayAdd(polyarray, coords, cell = True):
    # Append rows if required
    while len(polyarray) <= coords[0]:
      polyarray.append([])

    # Append columns if required
    while True:
      appended = False
      for x in range(len(polyarray)):
        if len(polyarray[x]) <= coords[1]:
          polyarray[x].append(None)
          appended = True
      if not appended:
        break

    # Set value
    polyarray[coords[0]][coords[1]] = cell

def PolyArrayValue(polyarray, x, y):
  if x<0 or x>=len(polyarray):
    return (None, None)

  if y<0 or y>=len(polyarray[x]):
    return (None, None)

  if isinstance(polyarray[x][y], tuple):
    return polyarray[x][y][0], polyarray[x][y][1] 
  else:
    return polyarray[x][y], None 

def PolyArrayFormat(polyarray):
  
  rows = []

  maxy = 0
  for r in polyarray:
    if len(r) > maxy:
      maxy = len(r)

  for x in reversed(range(0, maxy)):
    row = ''
    for y in range(0, len(polyarray)):
      v,t = PolyArrayValue(polyarray, y, x) 
      
      if v == None:
        row += ' '
      elif v == False:       
        row += '_'
      elif v == True:
        if (t == None):        
          row += 'X'
        elif (t[0] == 'part'):
          row += t[1]
        else:
          row += 'x'
      else:
        raise ValueError(f'Unsupported cell status value {v}')
      
    rows.append(row)
  
  return rows

def PolyArrayPrint(polyarray):
  for row in PolyArrayFormat(polyarray):
    print(row)

def PolyArrayTrim(polyarray):
  # Empty top rows
  while len(polyarray)>0 and all(p == None for p in polyarray[0]):
    del polyarray[0]

  # Empty left colums
  while True:
    isempty = True
    for row in polyarray:
      if len(row)>0 and row[0]!=None:
        isempty = False
        break # Not empty

    # Column is empty. Delete.
    if isempty:
      for x in range(0, len(polyarray)):
        del polyarray[x][0]
      # And try again for new first column.
    else:
      break

def PolyArrayFill(polyarray, x, y, oldvalue, newvalue):
  result = 0
  if PolyArrayValue(polyarray, x, y)[0] == oldvalue:
    PolyArrayAdd(polyarray, (x, y), (newvalue, 'floodfill'))
    result += 1
    result += PolyArrayFill(polyarray, x-1, y,   oldvalue, newvalue)
    result += PolyArrayFill(polyarray, x+1, y,   oldvalue, newvalue)
    result += PolyArrayFill(polyarray, x,   y-1, oldvalue, newvalue)
    result += PolyArrayFill(polyarray, x,   y+1, oldvalue, newvalue)
  return result

# Part encapsulates a single part in the puzzle. It has geometry as a shapely.geometry.polygon which is
# never transformed after creation. It has separate x/y-offset and rotation members which are set during
# the operation of the solver and a final_polygon method that returns the polygon in the position and
# attitude specified with the separate members.
#
# When a Part is constructed __init__ checks the geometry to see in which of the 90-degree rotations it
# is distinct. This list is also kept with the Part so we can optimize the placement during solving to
# eliminate duplicates.
class Part:
  
  def __init__(self, name, polygon, color, rotationangles, mirror):
    self.name = name
    self.polygon = polygon
    self.rotationangles = rotationangles
    self.color = color
    self.xoffset = 0
    self.yoffset = 0
    self.rotation = 0
    self.mirror = mirror
    self.ismirrored = False
    self.candidatepositions = []

  def __copy__(self):
    clone = Part(self.name, self.polygon, self.color, self.rotationangles, self.mirror)
    clone.xoffset = self.xoffset
    clone.yoffset = self.yoffset
    clone.rotation = self.rotation
    clone.ismirrored = self.ismirrored
    clone.candidatepositions = self.candidatepositions.copy()

    return clone

  def finalpolygon(self):
    p = copy.deepcopy(self.polygon)

    if self.ismirrored:
      for x in range(0, len(p)):
        p[x] = list(reversed(p[x]))
        
    if self.rotation == 0:
      pass
    elif self.rotation == 90:
      rot = []
      for y in range(0, len(p)):  
        for x in range(0, len(p[y])):
          if p[y][x]:
            PolyArrayAdd(rot, (x, len(p)-y-1))
      p = rot 
    elif self.rotation == 180:
      rot = []
      for y in range(0, len(p)):  
        for x in range(0, len(p[y])):
          if p[y][x]:
            PolyArrayAdd(rot, (len(p)-y-1, len(p)-x-1))
      p = rot
    elif self.rotation == 270:
      rot = []
      for y in range(0, len(p)):  
        for x in range(0, len(p[y])):
          if p[y][x]:
            PolyArrayAdd(rot, (len(p)-x-1,y))
      p = rot
    else:
      raise ValueError(f'Unsupported rotation {self.rotation}')

    PolyArrayTrim(p)
    # p = rotate(p, self.rotation)

    for _ in range(0, self.yoffset):
      p.append([])
    
    for _ in range(0, self.xoffset):
      for r in range(0, len(p)):
        p[x] = p[x].insert(0, None)

    return p

monthlabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
weekdaylabels = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

# A configuration is  made up from a name and a target-geometry as a shapely.geometry.polygon.
# The target geometry is created according to the selections for month, day and day of week
# that are to be kept free in the .
class CalendarConfiguration:
  
  def __init__(self, weekday, day, month):
    self.weekday = weekday
    self.day = day
    self.month = month
    self.name = monthlabels[self.month-1] + '-' + str(self.day) + '-' + weekdaylabels[self.weekday]

    self.target = []

    for m in range(0, 12):
      PolyArrayAdd(self.target, (m%6, 7-m//6), (False, ('month', m+1)))

    for d in range(0, 31):
      PolyArrayAdd(self.target, (d%7, 5-d//7), (False, ('day', d+1)))

    for wd in range(0, 4):
      PolyArrayAdd(self.target, (3+wd, 1), (False, ('weekday', wd)))
    for wd in range(4, 7):
      PolyArrayAdd(self.target, (wd, 0), (False, ('weekday', wd)))

    # Which square to leave free for the month
    monthx = (self.month-1) % 6      # 0..5
    monthy = 7 - (self.month-1) // 6  # 7 or 6
    self.target[monthx][monthy] = (True, 'currentmonth')

    # Which square to leave free for the day
    dayx = (self.day-1) % 7 # 0..6
    dayy = 5 - (self.day-1) // 7 # 5..1
    self.target[dayx][dayy] = (True, 'currentday')
    
    # And which square to leave free for the day of week
    weekdaystr = weekdaylabels[self.weekday]
    if (weekdaystr == 'Mon'):
      self.target[4][1] = (True, 'currentweekday')
    elif (weekdaystr == 'Tue'):
      self.target[5][1] = (True, 'currentweekday')
    elif (weekdaystr == 'Wed'):
      self.target[6][1] = (True, 'currentweekday')
    elif (weekdaystr == 'Thu'):
      self.target[4][0] = (True, 'currentweekday')
    elif (weekdaystr == 'Fri'):
      self.target[5][0] = (True, 'currentweekday')
    elif (weekdaystr == 'Sat'):
      self.target[6][0] = (True, 'currentweekday')
    elif (weekdaystr == 'Sun'):
      self.target[3][1] = (True, 'currentweekday')
    else:
      raise ValueError(f'Unsupported weekday {self.weekday}')
  
# BoardState is the main object class for the solver. It carries a reference to the puzzle being solved
# (name, list of parts and the complete geometry of the target). It has a list of parts still available,
# in their default don't-care positions as created in the catalog. It has a list of parts already placed,
# their offset- and rotation-values matter. And the remaining geometry of the target with all the placed
# parts subtracted. Instances of this class are used to maintain the state and modify it as we progress
# down the tree.
class BoardState:

  logger = logging.getLogger('Board')

  def __init__(self, calendarconfiguration, parts_placed, parts_available):
    self.calendarconfiguration = calendarconfiguration
    self.remaining_target = calendarconfiguration.target
    self.parts_placed = parts_placed
    self.parts_available = parts_available
    self.candidateposition = None

    # self.sanity()

  def __copy__(self):
    clone = BoardState(self.remaining_target, self.parts_placed.copy(), self.parts_available.copy())
    clone.calendarconfiguration = self.calendarconfiguration

    return clone 

  def sanity(self):
    # Check wether the geometry-setup makes internal sense
    cc = CalendarConfiguration(0,1,1)
    self.logger.info('Target area={area}'.format(area=cc.target.area))
    self.logger.info('Parts available in descending order of area:')
    totalarea = 0
    for part in BoardState.partscatalog:
      self.logger.info('{name}: area={area}, mirror={mirror}, distinct rotations={rotations}'.format(
          name=part.name, 
          mirror=('Yes' if part.mirror else 'No'),
          area=part.polygon.area, 
          rotations=part.rotations
        ))
      totalarea += part.polygon.area
    self.logger.info('Total area of parts={totalarea}'.format(totalarea=totalarea))
    if totalarea == cc.target.area: # Three squares to remain free
      self.logger.debug('Total parts area matches target area. A valid puzzle.')
    else:
      raise ValueError('Total parts area does not match target area, puzzle is invalid.')

  # Create a list of all the parts that make up the puzzle.

  '''
    A: XXXX

    B: XXXX
          X
        
    C: XXX
         X

    D: XXX
        X
        X

    E: X
       XXX
         X

    F: XXXX
       XXX

    G: XXX
         X
         X

    H: X X
       XXX

    I: XXX
         XX

    J:  XX
         XX      
  '''

  def Polygon(coords):
    # Build a two-dimensional array of booleans with True in all coords and False 
    # everywhere else.
    result = []
    for p in coords:
      PolyArrayAdd(result, p)
    return result

  partscatalog = [
    Part('A', Polygon([(0, 0), (1, 0), (2, 0), (3, 0)]),          'firebrick',  [0, 90],            False),        
    Part('B', Polygon([(0, 0), (1, 0), (2, 0), (3, 0), (0, 1)]),  'green',      [0, 90, 180, 270],  True),    
    Part('C', Polygon([(0, 0), (1, 0), (2, 0), (0, 1)]),          'blue',       [0, 90, 180, 270],  True),
    Part('D', Polygon([(0, 0), (1, 0), (2, 0), (1, 1), (1, 2)]),  'purple',     [0, 90, 180, 270],  False),
    Part('E', Polygon([(0, 0), (1, 0), (1, 1), (1, 2), (2, 2)]),  'yellow',     [0, 90],            True),
    Part('F', Polygon([(0, 0), (1, 0), (0, 1), (1, 1), (2, 1)]),  'firebrick',  [0, 90, 180, 270],  True),    
    Part('G', Polygon([(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]),  'green',      [0, 90, 180, 270],  False),    
    Part('H', Polygon([(0, 0), (1, 0), (2, 0), (0, 1), (2, 1)]),  'blue',       [0, 90, 180, 270],  False),    
    Part('I', Polygon([(0, 0), (1, 0), (2, 0), (2, 1), (3, 1)]),  'purple',     [0, 90, 180, 270],  True),
    Part('J', Polygon([(0, 0), (1, 0), (1, 1), (2, 1)]),          'yellow',     [0, 90],            True)
  ]

  random.shuffle(partscatalog)

  # Save the current board.
  def save(self):
    
    global options

    jsonparts = []
    for part in self.parts_placed:
      jsonpart = {
        'name': part.name,
        'xoffset': part.xoffset,
        'yoffset': part.yoffset,
        'rotation': part.rotation,
        'ismirrored': part.ismirrored
      }
      jsonparts.append(jsonpart)

    jsondata = {
        'configuration': {
            'month': self.calendarconfiguration.month,
            'monthlabel': monthlabels[self.calendarconfiguration.month-1],
            'day': self.calendarconfiguration.day,
            'weekday': self.calendarconfiguration.weekday,
            'weekdaylabel': weekdaylabels[self.calendarconfiguration.weekday]
        },
        'board': PolyArrayFormat(self.remaining_target),
        'parts': jsonparts
    }

    catalogname = f'{self.calendarconfiguration.month:02d}{self.calendarconfiguration.day:02d}{self.calendarconfiguration.weekday:02d}-{monthlabels[self.calendarconfiguration.month-1]}-{self.calendarconfiguration.day:02d}-{weekdaylabels[self.calendarconfiguration.weekday]}'
    destname = options.runfolder + '/../catalog3/' + catalogname + '.json'
        
    with open(destname, 'w') as f:
      json.dump(jsondata, f, sort_keys=True, indent=4)
    
# Main meat of the recursive solver. Called with a board state checks wether it is already solved.
# If not solved it generates candidate positions for available parts and can identify the board 
# as a dead end if none are found. If candidate positions are found recurse for each of them.
def solve(board):

  global finalpositions
  global options
  
  logger = logging.getLogger('solve')

  indent = '  ' * len(board.parts_placed)
  
  if not board.parts_available:
    # No more parts to place. We have a solution!
    finalpositions += 1
    logger.info('Found a solution! Checked {finalpositions} final positions.'.format(
      finalpositions=finalpositions
    ))

    #if options.playfanfare:
    #  wavfilename = os.path.dirname(os.path.realpath(__file__)) + '/fanfare.wav'
    #  if os.path.isfile(wavfilename):
    #    wav = simpleaudio.WaveObject.from_wave_file(wavfilename)
    #    wav.play()

    board.save()
    
    return True

  else:
    # There are parts left to place, we need to recurse further down.
    
    # Optimization: Look at each disjoint part of the remaining target.
    # If the area of one of those is 1, 2 or 3 squares we can never cover 
    # them with parts.
    deadend = False

    fillboard = copy.deepcopy(board.remaining_target)
    for x in range(0, 7):
      if not deadend:
        for y in range(0, 8):
          if PolyArrayValue(fillboard,x,y)[0] == False:
            # Empty square. How big is the contiguous area from here?
            squares = PolyArrayFill(fillboard, x, y, False, True)
            if squares <= 3:
              deadend = True
              break
    
    if deadend:
      finalpositions += 1
      logger.debug('<{level:02d}> {indent}Dead end: Disjoint space too small for minimum piece. Checked {finalpositions} final positions.'.format(
        level=len(board.parts_placed),
        indent=indent,
        finalpositions=finalpositions))
      
      return False

    else:
      # Not a dead-end after the check for minimum disjoint area.

      # Pick the next part to place. We use the area-wise biggest part next and 
      # have sorted the catalog accordingly.
      nextpart = board.parts_available[0]
      
      # Generate all possible legal positions nextpart can go in. This is
      # done in a discrete fashion by scanning the bounding box of the candidate
      # part in steps over the bounds of the target and checking the conditions.
      # The scanning happens in steps and is repeated for each possible 90 degree
      # rotation.
      targetwidth = 7
      targetheight = 8

      nextpart.candidatepositions = []

      mirror = [False]
      if nextpart.mirror:
        mirror.append(True)

      for m in mirror:  
        for rotation in nextpart.rotationangles:
          # Clone (possibly mirrored) part in default position 
          part = copy.copy(nextpart)
          part.rotation = rotation
          part.ismirrored = m
          poly = part.finalpolygon()

          for xoffset in range(0, targetwidth):
            for yoffset in range(0, targetheight):

              fits = True
              for partx in range(0, len(poly)):              
                x = partx + xoffset
                if x<0 or x>=len(board.remaining_target):
                  # Part sticks out
                  fits = False
                  break # partx

                for party in range(0, len(poly[partx])):
                  y = party + yoffset
                  if y<0 or y>=len(board.remaining_target[x]):
                    # Part sticks out
                    fits = False
                    break # party
                  else:
                    # Is there substance to the part here?
                    if poly[partx][party]:
                      # Yes. We need space on the target
                      if board.remaining_target[x][y] == None:
                        # There is no space here on the board
                        fits = False
                        break # party
                      if PolyArrayValue(board.remaining_target,x,y)[0]:
                        # Space on the board already occupied
                        fits = False
                        break # party
                    else:
                      # No, this is empty bit in the part array.
                      pass

                if not fits:
                  break # partx  

              if fits:
                part.polygon = poly
                part.xoffset = xoffset
                part.yoffset = yoffset
                nextpart.candidatepositions.append(copy.copy(part))                

      random.shuffle(nextpart.candidatepositions)

      # If there are no candidate positions for a part, we have hit a dead end.
      if len(nextpart.candidatepositions) == 0:
        finalpositions += 1
        if logger.isEnabledFor(logging.DEBUG):
          logger.debug('<{level:02d}> {indent}Dead end: Found no candidate positions for part {name}. Checked {finalpositions} final positions.'.format(
            level=len(board.parts_placed),
            indent=indent,
            name=nextpart.name,
            finalpositions=finalpositions))

        return False

      else:    
        # For each candidate position prepare a list of next boards by copying 
        # the current one. Remove the part we just (tentatively) placed from the list
        # of available parts. Append it to the placed parts and remove it from the 
        # target area.
        if logger.isEnabledFor(logging.DEBUG):
          logger.debug('<{level:02d}> {indent}Creating next boards for part {name} with {candidatepositions} candidate positions'.format(
            level=len(board.parts_placed),
            indent=indent,
            name=nextpart.name,
            candidatepositions=len(nextpart.candidatepositions)))

        nextboards = []

        for candidate in nextpart.candidatepositions:    
        
          nextboard = copy.deepcopy(board)
          nextboard.parts_available = [part for part in nextboard.parts_available if part.name != nextpart.name]
          nextboard.candidateposition = candidate
          nextboard.parts_placed.append(candidate)
          
          # Place the part here by marking the board with True flags
          poly = candidate.polygon
          
          for partx in range(0, len(poly)):              
            for party in range(0, len(poly[partx])):
              if poly[partx][party]:
                x = partx + candidate.xoffset
                y = party + candidate.yoffset
                nextboard.remaining_target[x][y] = (True, ('part', candidate.name))

          nextboards.append(nextboard)
      
        if logger.isEnabledFor(logging.DEBUG):
          msg = '<{level:02d}> {indent}Try part {name} with {nextboards} candidate positions'.format(
            level=len(board.parts_placed),
            indent=indent,
            name=nextpart.name,
            nextboards=len(nextboards),
            candidatepositions=len(nextpart.candidatepositions)
          )
          if len(nextpart.candidatepositions) != len(nextboards):
            msg += ' (down from {candidatepositions})'.format(candidatepositions=len(nextpart.candidatepositions))
          msg += ' next.'
          logger.debug(msg)

        # Update candidatepositions to include any filtering that has happened.
        nextpart.candidatepositions = list(map(lambda board: board.candidateposition, nextboards))

        # Now recurse down into each candidate board to find solutions.
        i = 1
        for nextboard in nextboards:        
          if logger.isEnabledFor(logging.DEBUG):
            logger.debug('<{level:02d}> {indent}{parts_placed} parts placed. Try next position {i} of {nextboards} for part {name}.'.format(
              level=len(board.parts_placed),
              indent=indent,
              parts_placed=len(board.parts_placed), 
              i=i, 
              nextboards=len(nextboards),
              name=nextpart.name
            ))

          if solve(nextboard):
            # Found a solution. Unwind recursion.
            return True
          
          i += 1
          
# Controller for preparing a puzzle and starting the solver.
def solvefordate(date):

  logger = logging.getLogger('solvefordate')
  logger.info(f'solvefordate({date})')

  # Extract relevant parts from the date. 
  weekday = date.weekday() # 0 = Monday matches weekdaylabels
  day = date.day # 1..31
  month = date.month # 1..12

  solvefor(month, day, weekday)

def solvefor(month, day, weekday):

  global finalpositions
  global options
    
  finalpositions = 0
  
  logger = logging.getLogger('solvefor')
  logger.info(f'solvefor({month}, {day}, {weekday} \"{weekdaylabels[weekday]}\")')
  
  cc = CalendarConfiguration(weekday, day, month)

  # Create the initial board state. Start with no parts placed, and all parts available.
  board = BoardState(cc, [], BoardState.partscatalog)

  # Try to solve it

  start = datetime.datetime.now()

  solve(board)

  end = datetime.datetime.now()
  duration = end - start
  logger.info(f'solvefor({month}, {day}, {weekday} \"{weekdaylabels[weekday]}\") - finished after {duration}')
  
# Conversion function for argparse booleans
def str2bool(v):
  if v.lower() in ('yes', 'true', 't', 'y', '1'):
    return True
  elif v.lower() in ('no', 'false', 'f', 'n', '0'):
    return False
  else:
    raise argparse.ArgumentTypeError('Boolean value expected.')

# Set up argparse and get the command line options.
def parse_commandline():

  global options

  parser = argparse.ArgumentParser(
      description = 'Solve Calendar-puzzles.'
  )

  parser.add_argument('-ll', '--log-level',
    action = 'store',
    default = 'INFO',
    help ='Set the logging output level to CRITICAL, ERROR, WARNING, INFO or DEBUG (default: %(default)s)',
    dest ='log_level',
    metavar = 'level'
  )

  parser.add_argument('-of', '--output-folder',
    action = 'store',
    default = '',
    help = 'Folder for output artefacts (default: timestamp)',
    dest = 'runfolder',
    metavar = 'folder'
  )

  parser.add_argument('-rs', '--random-seed',
    action = 'store',
    default = None,
    help = 'Seed to use for random generator (default: use entropy source to randomize)',
    dest = 'seed',
    metavar = 'seed'
  )

  parser.add_argument('-pf', '--play-fanfare',
    action = 'store',
    default = True,
    type = str2bool,
    help = 'Play a fanfare whenever a solution is found (default: %(default)s)',
    dest = 'playfanfare',
    metavar = 'flag'
  )

  options = parser.parse_args()
  options.log_level_int = getattr(logging, options.log_level, logging.INFO)

  if not options.runfolder:
    options.runfolder = os.path.dirname(os.path.realpath(__file__)) + '/' + time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())

# Set up a logger each for a file in the output folder and the console.      
def setup_logging():
  
  global options
  
  os.makedirs(options.runfolder, exist_ok = True)

  fh = logging.FileHandler(options.runfolder + '/Solver.log')
  fh.setLevel(options.log_level_int)

  ch = logging.StreamHandler()
  ch.setLevel(options.log_level_int)

  ch.setFormatter(logging.Formatter('{asctime} [{levelname:5}] {name} - {message}', '%H:%M:%S', style='{'))
  fh.setFormatter(logging.Formatter('{asctime} [{levelname:5}] {name} - {message}', style='{'))

  root = logging.getLogger()
  root.addHandler(ch)
  root.addHandler(fh)
  root.setLevel(logging.DEBUG)

def main():
  
  global options
  
  parse_commandline()
  setup_logging()

  logger = logging.getLogger('main')
  logger.info('Starting. Output goes to {runfolder}'.format(runfolder=options.runfolder))

  # Initialize random generator. This is here so that we can copy the seed and
  # put it into the code to repeat a run.
  if not options.seed:
      options.seed = str(uuid.uuid4())
  
  logger.info('Random seed in use: {0}.'.format(options.seed))
  random.seed(options.seed)

  #solvefor(2, 29, 4)
  #quit()

  #date = datetime.date(2022, 7, 6)
  #solvefordate(date)
  #quit()

  # I have determined that the years 2022 to 2048 (inclusive) use all possible
  # configurations of month, day and weekday. Solve for each of them:
  for year in range(2022, 2049):    
    # Just regular:
    months = range(1,13)
    days = range(1,32)

    # Starting on a certain date:
    startmonth = 1
    startday = 1
    months = list(range(startmonth,13)) + list(range(1,startmonth))
    days = list(range(startday,32)) + list(range(1,startday))
    
    for month in months:
      for day in days:

        # Skip invalid dates:
        if (month == 2) and (day > (29 if calendar.isleap(year) else 28)):
          continue
        elif (month in [4,6,9,11]) and (day > 30):
          continue

        weekday = datetime.datetime(year, month, day).weekday() # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
            
        # Attempt to clean up stale lock files
        lockfiles = glob.glob(options.runfolder + '/../catalog3/*.lck')
        for lockfile in lockfiles:
            try:
              os.remove(lockfile)
            except:
              pass # Most propably still locked

        catalogname = f'{month:02d}{day:02d}{weekday:02d}-{monthlabels[month-1]}-{day:02d}-{weekdaylabels[weekday]}'
      
        # Already solved?
        if glob.glob(options.runfolder + '/../catalog3/' + catalogname + '.json'):
          logger.info(f'Already done {catalogname}')
        else:
          # No solution exists yet. Create a lock file so other processes know we are working on this.
          lockfilename = options.runfolder + '/../catalog3/' + catalogname + '.lck'
          try:
            with portalocker.Lock(lockfilename, 'wt', timeout = 1) as lockfile:              
              lockfile.write(f'PID {os.getpid()}, started {datetime.datetime.now()}')
              lockfile.flush()
              os.fsync(lockfile.fileno())

              # In Windows rename the shell title.
              if platform.system() == 'Windows':
                os.system(f'cmd.exe /C title {year:04d}-{month:02d}-{day:02d}')
                              
              logger.info(f'Now solving for {catalogname}')        
              os.makedirs(options.runfolder, exist_ok = True)                            
              solvefor(month, day, weekday)
        
          except portalocker.exceptions.LockException:
              logger.info(f'{catalogname} locked, being solved by concurrent process')

          finally:
            try:
              os.remove(lockfilename)
            except:
              pass
    
  endtime = datetime.datetime.now().replace(microsecond=0)
  runtime = (endtime-starttime)
  logger.info('Finished. Total runtime: {runtime}'.format(runtime=runtime))
    
if __name__ == '__main__':
    main()
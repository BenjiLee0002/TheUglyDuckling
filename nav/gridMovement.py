# GridMovement class 
# Handles all grid based navigation for the robot

from .grid import Grid
from . import grassfire as gf 
import queue, time, math

NORTH = 90
SOUTH = 270
EAST = 0
WEST = 180
HOME = (4,4)

class GridMovement:

	def __init__(self, grid, serial):
		# direction bytes
		self.fwd = b'\xA0'
		self.rev = b'\x0A'
		self.rotl = b'\x00'
		self.rotr = b'\xAA'
		self.strl = b'\x22'
		self.strr = b'\x88'

		# motion bytes
		self.allmotors = b'\x55'
		self.right = b'\x05'
		self.left = b'\x50'
		self.front = b'\x11'
		self.rear = b'\x44'
		self.left45 = b'\x14'
		self.right45 = b'\x41'
	
		self.grid = grid
		self.serial = serial
		self.current = HOME
		self.goal = (7,7) #Hardcoded for now. Should be generated by find_goal()
		self.facing = NORTH
		self.path = []
		self.movement = {
			(0,1): [self.fwd, self.allmotors, 0], (0, -1): [self.rev, self.allmotors, 180],
			(1,0): [self.strr, self.allmotors, -90], (-1, 0): [self.strl, self.allmotors, 90],
			(1,1): [self.fwd, b'\x00', -45], (-1, 1): [self.fwd, b'\x00', 45],
			(1,-1): [self.fwd, b'\x00', -135], (-1,-1): [self.fwd, b'\x00', 135]
			}
		
	def get_obstacles(self):
		return self.grid.get_obstacles()

	# Not yet implemented
	# If we haven't aquired a block yet, set closest block as goal.
	# Otherwise we set mothership as goal.
	def find_goal(self):
		pass

	# Generates shortest path to goal using grassfire algorithim
	def find_path(self):
		visited = gf.search(self.grid, self.current, self.goal)
		self.path = gf.construct_path(self.grid, visited, self.current)

	# Follows the generated path by subtracting the next location
	# from self.current and using translate_dir() and self.movement
	# to determine the proper movement
	def follow_path(self):
		dist = 12 # Default distance we want to move
		# Loop with index so that we can check the next movement
		# along with curent move
		for index, mov in enumerate(self.path):
			currentResult = (mov[0] - self.current[0], mov[1] - self.current[1])
			currentResult = self.translate_dir(currentResult)
			diagonal = gf.is_diagonal(self.current, mov)
			end_of_path = index == len(self.path) - 1

			# Don't bother checking next move if it doesn't exist
			if (not end_of_path):
				nextMov = self.path[index+1]
				nextResult = (nextMov[0] - mov[0], nextMov[1] - mov[1])
				nextResult = self.translate_dir(nextResult)
				# If next move request is the same as current 
				# increase distance moved
				if (currentResult == nextResult):
					self.face(mov)	
					dist = dist +12
					self.current = mov
					# We want to skip over the rest of the loop
					# We're not ready to push a movement call to queue
					continue

			# if dist > 12 then we have duplicate movements
			# We will accelerate
			if(dist > 12):
				self.accelerate(self.movement[currentResult][0], dist)
			# Otherwise normal movement
			else:
				# if mov is diagonal turn towards it first
				if(diagonal):
					self.face(mov)

				self.move(self.movement[currentResult][0], dist)
				# if mov was diagonal and we're not at end of path
				# turn towards the next mov
				if(diagonal and not end_of_path):
					self.face(self.path[index + 1])

			# reset distance in case there was a stacked call 
			dist = 12
			self.current = mov
		
		# face goal after following path
		self.face(self.goal)

	def follow_next_step(self):
		dist = 12
		checking_dup = True
		result = None
		is_diagonal = False
		mov = None
		while checking_dup and self.path:
			mov = self.path.pop(0)
			result = (mov[0] - self.current[0], mov[1] - self.current[1])
			if self.path:
				nextMov = self.path[0]
				nextResult = (nextMov[0] - mov[0], nextMov[1] - mov[1])
				if nextResult == result:
					dist = dist + 12
					self.current = mov
				else:
					checking_dup = False

		if dist > 12:
			self.face(mov)
			self.accelerate(dist, is_diagonal)
			if is_diagonal and self.path:
				self.face(self.path[0])
		elif is_diagonal:
			self.face(mov)
			result = self.translate_dir(result)
			self.move(self.movement[result][0], dist)
			if self.path:
				self.face(self.path[0])
		else:
			result = self.translate_dir(result)
			self.move(self.movement[result][0], dist)

	# Face a tile connected to current tile
	def face(self, obj):
		result = (obj[0] - self.current[0], obj[1] - self.current[1])
		result = self.translate_dir(result)
		degrees = self.movement[result][2]
		self.turn(degrees)

	# Should be called anytime facing is updated
	# Keeps facing between 0 and 360 
	def trim_facing(self):
		if self.facing < 0:
			self.facing = self.facing + 360
		elif self.facing >= 360:
			self.facing = self.facing - 360

	# Use facing to translate proper movement
	def translate_dir(self,mov):
		angle = self.facing - self.movement[mov][2]
		is_diagonal = angle is not 0 and angle % 90 is not 0
		angle = math.radians(angle)
		x = math.cos(angle)
		y = math.sin(angle)
		if is_diagonal:
			x = x/abs(x)
			y = y/abs(y)

		x = x*-1

		x = math.ceil(x) if x < 0 else math.floor(x)
		y = math.ceil(y) if y < 0 else math.floor(y)
		return (x,y)

	def map(self,obj, angle, dist):
		offset = 6
		diag_offset = math.sqrt(288) / 2
		angle_rads = math.radians((angle* -1) + self.facing)

		o_length = math.sin(angle_rads) * dist
		a_length = math.cos(angle_rads) * dist

		if self.facing == EAST or self.facing == WEST:
			x = a_length/12
			if -offset<o_length<offset:
				y= 0
			else:
				y = o_length is (o_length + offset)/12 if o_length < 0 else (o_length - offset)/12

		elif self.facing == NORTH or self.facing == SOUTH:
			if -offset<a_length<offset:
				x = 0
			else:
				x = a_length is (a_length + offset)/12 if a_length < 0 else (a_length - offset)/12
			y = o_length/12

		else:
			x = (a_length + diag_offset)/math.sqrt(288) if a_length < 0 else (a_length - diag_offset)/math.sqrt(288)
			y = (o_length + diag_offset)/math.sqrt(288) if o_length < 0 else (o_length - diag_offset)/math.sqrt(288)
			

		x = math.ceil(x) if x > 0 else math.floor(x)
		y = math.ceil(y) if y > 0 else math.floor(y)
		result = (self.current[0] + x, self.current[1] + y)
		print(result)
		if obj == 8:
			self.grid.add_obstacle(result)
		elif obj > 1 and obj < 7:
			self.grid.add_target(result)
	# Communicates movement calls to Arduino
	# MOVEMENT FUNCTIONS #

	def turn(self,degrees):
		turn_dir = self.rotl
		if(degrees < 0):
			turn_dir = self.rotr

		byteArr = b'\x01' + turn_dir +bytes([abs(degrees)])+b'\x00'
		self.serial.write(byteArr)
		# Update current orientation 
		self.facing = self.facing + degrees
		self.trim_facing()

	def move(self,dir, dist):
		byteArr = b'\x00' + dir +bytes([dist])+b'\x00'
		self.serial.write(byteArr)

	def accelerate(self,dist, is_diagonal=False):
		byte = b'\x00' if is_diagonal else b'\x01'
		byteArr = b'\x02' + self.fwd + bytes([dist]) + byte

	def pickup(self): 
		byteArr = b'\x03'  + b'\x00' + b'\x00' + b'\x00'
		self.serial.write(byteArr)

	def drop(self): 
		byteArr = b'\x04'  + b'\x00' + b'\x00' + b'\x00'
		self.serial.write(byteArr)

	def reset_servo(self): 
		byteArr = b'\x05'  + b'\x00' + b'\x00' + b'\x00'
		self.serial.write(byteArr)

	def cam_up(self): 
		byteArr = b'\x06'  + b'\x00' + b'\x00' + b'\x00'
		self.serial.write(byteArr)

	def cam_down(self): 
		byteArr = b'\x07'  + b'\x00' + b'\x00' + b'\x00'
		self.serial.write(byteArr)

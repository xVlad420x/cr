import ctypes
import time
import datetime
#import win32api
import pynput

#constants
bagtimer = 300
bedtimer = 120

class User():
    #Create the user with the appropriate key binds
    #Mouse settings can be computed from python
    #We assume certain buttons in the console are at certain coordinates, these can be changed with methods
    #Vision and Location get updated frequently
    #Death Status gets checked whenever console is used
    def __init__(self, fow, bac, lef, rig, use, duc, spr, con):
        self.sens = None
        self.cursor_speed = None
        self.dpi = None
        self.map_zoom = None
        self.forward = fow
        self.backward = bac
        self.left = lef
        self.right = rig
        self.use = use
        self.crouch = duc
        self.sprint = spr
        self.console = con
        self.console_input_cord = [100, 100]
        self.console_copy_cord = [200, 200]
        self.console_clear_cord = [300, 300]
        self.map_location = None
        self.map_vision = None
        self.is_killed_code = True
        self.is_killed_player = False
        self.is_killed_animal = False

    #Use console to find in game sensitivity
    def get_ingame_sens(self):
        #temp
        self.sens = None

    #Get windows cursor speed using ctypes
    def get_cursor_speed(self):
        #temp
        #get_mouse_speed = 112
        #speed = ctypes.c_int()
        #ctypes.windll.user32.SystemParametersInfoA(get_mouse_speed, 0, ctypes.byref(speed), 0)
        self.cursor_speed = None

    #Get mouse dpi if necessary
    def get_dpi(self):
        #temp
        self.dpi = None

    #Scroll in and out of the map to get the desired zoom, set by programmer
    def get_zoom(self):
        #temp
        self.map_zoom = None

    #This is used if the default console cords were incorrect
    def set_console_cords(self, input_cord, copy_cord, clear_cord):
        self.console_input_cord = input_cord
        self.console_copy_cord = copy_cord
        self.console_clear_cord = clear_cord

    #Turn the character to the desired vector
    def face_direction(self, target_vision):
        #temp
        self.map_vision = None

    #Run in game to coordinate (not super precise)
    def move_directly_to_cord(self, target_cord):
        #temp
        target_vision = None
        self.face_direction(target_vision)
        self.map_location = None

    #Crouch to coordinate for better precision
    def move_precisely_to_cord(self, target_cord):
        # temp
        target_vision = None
        self.face_direction(target_vision)
        self.map_location = None

    #Uses both move functions to get precisely to the door and look at the lock in a timely manner
    #Takes a path object as an input
    def get_to_door_and_face_lock(self, path_object):
        #temp
        self.map_vision = None
        self.map_location = None

    #Perform the coderaid on the door with 5 codes, update the door object accordingly, being mindful of a code overload ban
    def punch_in_5_codes(self, door_object):
        #move_mouse and use pynput
        #check after 2 codes if died to codelock, if yes than is blocked
        is_banned = False
        door_object.update_after_5_codes(is_banned)

    #Uses the zoom parameter and current location to select a bag/bed and spawns there
    #Returns true if sucessfully spawned
    def spawn(self, spawn_object):
        self.map_location = None
        successful_spawn = True
        if(successful_spawn):
            pass
        else:
            pass
        spawn_object.update_after_spawn(successful_spawn)


class Door():
    #location and angle are where the player should stand and look when code raiding
    #the available parameter will be set to true in the driver function after the 1 minute time period is up
    def __init__(self, location, angle, door_id):
        self.door_id = door_id
        self.location = location
        self.angle = angle
        self.time_of_last_code = 0.0
        self.available_for_5_codes = True
        self.is_red_and_banned = False

    #Updated the parameters when punch_in_5_codes is called
    def update_after_5_codes(self, is_banned):
        self.available_for_5_codes = False
        self.is_red_and_banned = is_banned
        self.time_of_last_code = datetime.datetime.now().timestamp()

class Spawn():
    def __init__(self, location, is_bed, door_id, spawn_id):
        self.location = location
        self.associated_door = door_id
        self.spawn_id = spawn_id
        self.is_bed = is_bed
        self.time_of_last_spawn = 0
        self.available_for_spawn = True
        self.failed_spawn_count = 0
        self.is_destroyed = False

    #Updated the parameters after spawn and is called in the spawn function for player
    #If we miss a spawn we still set the timer and increment the failed spawn count
    #If we failed spawning too many times then the spawn point is destroyed
    def update_after_spawn(self, successful_spawn):
        self.available_for_spawn = False
        if(successful_spawn):
            self.time_of_last_spawn = datetime.datetime.now().timestamp()
            self.failed_spawn_count = 0
        else:
            if(self.failed_spawn_count >= 2):
                self.is_destroyed = True
            else:
                self.failed_spawn_count = self.failed_spawn_count + 1
                if(not self.is_bed):
                    self.time_of_last_spawn = datetime.datetime.now().timestamp() - (bagtimer/2)
                else:
                    self.time_of_last_spawn = datetime.datetime.now().timestamp() - (bedtimer/2)

class Location():
    def __init__(self,x,y,z):
        self.xcoord = x
        self.ycoord = y
        self.zcoord = z

class Vision():
    def __init__(self,x,y,z):
        self.xcoord = x
        self.ycoord = y
        self.zcoord = z

#Contains the spawn, door and any intermediary coordinates
class Path():
    def __init__(self,spawn,door):
        self.spawn = spawn
        self.locationlist = []
        self.door = door

#the main function
def driver():
    #We begin with tutples with door and spawn information, door tuple has location, vision and id
    #spawn tuple has location, whether its a bed, and the associated door
    doors = [(Location(1,2,3),Vision(1,2,3),1),(Location(2,3,5),Vision(6,3,1),2)]
    spawns = [(Location(8,9,10),False,1),(Location(83,92,101),False,1), (Location(38,39,103),False,2), (Location(418,329,1320),False,2)]


    doorlist = []
    for tup in doors:
        doorlist.append(Door(tup[0],tup[1],tup[2]))
    spawnlist = []
    for i in range(1,len(spawns)):
        spawnlist.append(Spawn(spawns[0],spawns[1],spawns[3],i))

    #get the door object from a doorid
    def getdoor(id):
        for door in doorlist:
            if(door.door_id == id):
                return door
        raise KeyError("Door id not found, doorid: " + id)

    #Construct a path dictionary easily accessible from a spawnid
    path_dict = {}
    for spawn in spawnlist:
        temppath = Path(spawn,getdoor(spawn.associated_door))
        path_dict[spawn.spawn_id] = temppath

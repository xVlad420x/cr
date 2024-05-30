import ctypes
import time
import datetime
#import win32api
import pynput
import os
import sys
import pandas as pd

#constants
bagtimer = 300
bedtimer = 120

#keyboard IO functions
from pynput.keyboard import Key, Controller
keyboard = Controller()
def usekey(mykey):
    keyboard.press(mykey)
    keyboard.release(mykey)

def type(string):
    for character in string:
        keyboard.press(character)
        keyboard.release(character)

pynput_key_dict = {"space": Key.space, "shift_left": Key.shift_l, "shift_right": Key.shift_r, "alt_left": Key.alt_l, "alt_right": Key.alt_r,
                   "control_left": Key.ctrl_l, "control_right": Key.ctrl_r, "enter": Key.enter, "backspace": Key.backspace,
                   "delete": Key.delete, "tab": Key.tab, "escape": Key.esc, "up": Key.up, "down": Key.down, "left": Key.left,
                   "right": Key.right, "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4, "f5": Key.f5, "f6": Key.f6,
                   "f7": Key.f7, "f8": Key.f8, "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12}

def getkey(string):
    if(len(string) > 1):
        string = pynput_key_dict[string]
    return string

def str_to_bool(string):
    if(string == "True"):
        return True
    elif(string == "False"):
        return False
    else:
        raise Warning

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

#Contains the spawn, door and any intermediary coordinates
class Path():
    def __init__(self,spawn,door):
        self.spawn = spawn
        self.locationlist = []
        self.door = door

    def updatepath(self,locationlist):
        self.locationlist = locationlist

#Keeps track of player movement and state
class User:
    class PlayerInput:
        def __init__(self,fow, bac, lef, rig, use, duc, spr, con, jum):
            self.forward = fow
            self.backward = bac
            self.left = lef
            self.right = rig
            self.use = use
            self.crouch = duc
            self.sprint = spr
            self.console = con
            self.jump = jum

    class StandardInfo:
        def __init__(self):
            self.map_location = None
            self.map_vision = None
            self.current_code_count = 0

        def setlocation(self,location):
            self.map_location = location

        def getlocation(self):
            return self.map_location

        def setvision(self,eyes):
            self.map_vision = eyes

        def getvision(self):
            return self.getvision()

        def setcount(self,ccount):
            self.current_code_count = ccount

        def getcount(self):
            return self.current_code_count

    class PlayerCriticalStatus:
        def __init__(self):
            self.is_killed_code = True
            self.is_killed_player = False
            self.is_killed_animal = False
            self.successfull_code = False
            self.destroyed_bag = False
            self.door_banned = False

        def update_death(self,deathid):
            if(deathid == 2):
                self.is_killed_player = True
                self.is_killed_animal = False
                self.is_killed_code = False
            if(deathid == 1):
                self.is_killed_player = False
                self.is_killed_animal = True
                self.is_killed_code = False
            if(deathid == 0):
                self.is_killed_player = False
                self.is_killed_animal = False
                self.is_killed_code = True

        def set_success(self,bool):
            self.successfull_code = bool

        def set_destroyed(self,bool):
            self.destroyed_bag = bool

        def set_banned(self,bool):
            self.door_banned = bool

    class CodeRaidTools:
        def __init__(self):
            self.spawnlist = None
            self.doorlist = None
            self.path_dict = None

        def update(self,bags,doors,paths):
            self.spawnlist = bags
            self.doorlist = doors
            self.path_dict = paths



    #Create the user with the appropriate key binds
    #Mouse settings can be computed from python
    #We assume certain buttons in the console are at certain coordinates, these can be changed with methods
    #Vision and Location get updated frequently
    #Death Status gets checked whenever console is used

    def __init__(self, fow, bac, lef, rig, use, duc, spr, con,jum,code_flag,player_death_flag,animal_death_flag,destroyed_bag_flag,door_ban_flag):
        self.sens = None
        self.cursor_speed = None
        self.dpi = None
        self.map_zoom = None
        self.player_input = self.PlayerInput(fow, bac, lef, rig, use, duc, spr, con, jum)
        self.standard_info = self.StandardInfo()
        self.console_input_cord = [100, 100]
        self.console_copy_cord = [200, 200]
        self.console_clear_cord = [300, 300]
        self.status = self.PlayerCriticalStatus()
        self.should_stop = False
        self.tools = self.CodeRaidTools()
        self.autopause_tuple = (code_flag,player_death_flag,animal_death_flag,destroyed_bag_flag,door_ban_flag)
        self.codes_df = None

    def read_config(self):
        code_f = True
        pd_f = True
        ad_f  = True
        db1_f = True
        db2_f = True
        config_path = sys.argv[1]
        if os.path.exists(config_path):
            with open(config_path, "r") as file:
                for line in file:
                    myline = line.strip()
                    if("Forward" in myline):
                        self.player_input.forward = getkey(myline[(myline.index("=")+1):len(myline)].strip())
                    elif("Backward" in myline):
                        self.player_input.backward = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Left" in myline):
                        self.player_input.left = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Right" in myline):
                        self.player_input.right = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Use" in myline):
                        self.player_input.use = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Crouch" in myline):
                        self.player_input.crouch = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Sprint" in myline):
                        self.player_input.sprint = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Console" in myline):
                        self.player_input.console = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Jump" in myline):
                        self.player_input.jump = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif("Code_Found" in myline):
                        code_f = str_to_bool(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Player_Death" in myline):
                        pd_f = str_to_bool(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Animal_Death" in myline):
                        ad_f = str_to_bool(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Spawn_Destroyed" in myline):
                        db1_f = str_to_bool(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Door_Ban" in myline):
                        db2_f = str_to_bool(myline[(myline.index("=") + 1):len(myline)].strip())
                self.autopause_tuple = (code_f,pd_f,ad_f,db1_f,db2_f)
            #print(os.path.basename(config_path))
        else:
            raise FileNotFoundError

    def read_codefile(self):
        code_table = sys.argv[2]
        codes = pd.read_csv(code_table)
        self.codes_df = codes
        '''
        print(codes.to_string())
        a = self.codes_df["Code"].values[0].astype(str)
        sum = 0
        for i in range(len(self.codes_df["Code"])):
            print(self.codes_df["Entries"].values[i].astype(int))
            sum+= self.codes_df["Entries"].values[i].astype(int)
        print(sum)
        s = codes['Entries'].sum()
        print(s)
        '''


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

    #This is used if the default console screen cords were incorrect
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

    #check 5 things: vision, eyes, killed by player, animal, code
    def read_console(self):
        killedplayer = False
        killedanimal = False
        killedcode = False
        wasplayereyes = False
        newplayereyes = None
        wasplayerpos = False
        newplayerpos = None
        if(wasplayereyes):
            self.map_vision = newplayereyes
        if(wasplayerpos):
            self.map_location = newplayerpos
        if(killedplayer):
            self.status.update_death(2)
        elif(killedanimal):
            self.status.update_death(1)
        elif(killedanimal):
            self.status.update_death(0)

    def update_location(self,must_open_console,must_close_console):
        if(must_open_console):
            usekey(self.player_input.console)
        #type in client.printpos
        self.read_console()
        if(must_close_console):
            usekey(self.player_input.console)

    def update_vision(self,must_open_console,must_close_console):
        if(must_open_console):
            usekey(self.player_input.console)
        #type in client.printeyes
        self.read_console()
        if(must_close_console):
            usekey(self.player_input.console)

    def check_stop_warnings(self):
        pass

    def create_tools(self):
        # We begin with tutples with door and spawn information, door tuple has location, vision and id
        # spawn tuple has location, whether its a bed, and the associated door, updated paths has the spawnid and then corresponding location stoppages to the door
        doors = [(Location(1, 2, 3), Vision(1, 2, 3), 1), (Location(2, 3, 5), Vision(6, 3, 1), 2)]
        spawns = [(Location(8, 9, 10), False, 1), (Location(83, 92, 101), False, 1), (Location(38, 39, 103), False, 2),
                  (Location(418, 329, 1320), False, 2)]

        doorlist = []
        for tup in doors:
            doorlist.append(Door(tup[0], tup[1], tup[2]))
        spawnlist = []
        for i in range(1, len(spawns)):
            spawnlist.append(Spawn(spawns[0], spawns[1], spawns[3], i))

        # get the door object from a doorid
        def getdoor(id):
            for door in doorlist:
                if (door.door_id == id):
                    return door
            raise KeyError("Door id not found, doorid: " + id)

        # Construct a path dictionary easily accessible from a spawnid
        path_dict = {}
        for spawn in spawnlist:
            temppath = Path(spawn, getdoor(spawn.associated_door))
            path_dict[spawn.spawn_id] = temppath

        self.tools.update(spawnlist,doorlist,path_dict)

    #Main Drivercode
    def coderaid(self):
        while(not self.should_stop):
            time.sleep(0.5)
            self.update_door_timers()
            self.update_spawn_timers()
            current_door = self.choose_available_door() #choose random available door
            if(current_door == None):
                continue
            current_spawn = self.choose_best_bag(current_door) #best based on availability and closeness
            if(current_spawn == None):
                continue
            current_path = self.tools[current_spawn.spawn_id]
            self.perform_run(current_path)





test = User("w","s","a","d","z",Key.cmd_l,Key.shift_l,Key.f1,Key.space, True,True,False,True,True)
print("testing")
test.read_config()
test.read_codefile()
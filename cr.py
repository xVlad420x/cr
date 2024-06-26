#Todo: If median path time is the same, choose based on distance to door (including detours)
#Todo: Start reading console after crack to determine if you successfully got the code
#Todo: read console to determine if killed by player, cold, animal
#Todo: implement checks to see if door is locked or spawn is destroyed
#Todo: implement time based stop
#Todo: implement 1 min suicide timer
#Todo: config variable codes to put in ex: 5 or 6
#Todo: Move mouse to bag function too inaccurate for zoom of 5, make more accurate

import ctypes
import statistics
import math
import time
import datetime
import pynput
import threading
import os
import sys
import pandas as pd
import pyperclip as pc
import win32api, win32con, win32gui
#pip install pywin32
#constants
bagtimer = 300
bedtimer = 120
initialization_over = False


#keyboard IO functions
from pynput.keyboard import Key, Controller, Listener
outputkeyboard = Controller()
from pynput.mouse import Controller, Button
outputmouse = Controller()
def usekey(mykey):
    outputkeyboard.press(mykey)
    outputkeyboard.release(mykey)


pynput_key_dict = {"space": Key.space, "shift_left": Key.shift_l, "shift_right": Key.shift_r, "alt_left": Key.alt_l, "alt_right": Key.alt_r,
                   "control_left": Key.ctrl_l, "control_right": Key.ctrl_r, "enter": Key.enter, "backspace": Key.backspace,
                   "delete": Key.delete, "tab": Key.tab, "escape": Key.esc, "up": Key.up, "down": Key.down, "left": Key.left,
                   "right": Key.right, "f1": Key.f1, "f2": Key.f2, "f3": Key.f3, "f4": Key.f4, "f5": Key.f5, "f6": Key.f6,
                   "f7": Key.f7, "f8": Key.f8, "f9": Key.f9, "f10": Key.f10, "f11": Key.f11, "f12": Key.f12}

def getkey(string):
    if(len(string) > 1):
        string = pynput_key_dict[string]
    return string

def timestamp():
    return datetime.datetime.now().timestamp()

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

    def __str__(self):
        return str(self.xcoord) + ", " + str(self.ycoord) + ", " + str(self.zcoord)

class Vision():
    def __init__(self,x,y,z):
        self.xcoord = x
        self.ycoord = y
        self.zcoord = z

    def __str__(self):
        return str(self.xcoord) + ", " + str(self.ycoord) + ", " + str(self.zcoord)

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
            if self.failed_spawn_count >= 2:
                self.is_destroyed = True
            else:
                self.failed_spawn_count = self.failed_spawn_count + 1
                if(not self.is_bed):
                    self.time_of_last_spawn = datetime.datetime.now().timestamp() - (bagtimer/2)
                else:
                    self.time_of_last_spawn = datetime.datetime.now().timestamp() - (bedtimer/2)

#Contains the spawn, door and any intermediary coordinates
class Path():
    def __init__(self,spawn : Spawn,door : Door):
        self.spawn = spawn
        self.locationlist = []
        self.door = door
        self.path_duration_list = []

    def updatepath(self,location : Location):
        self.locationlist.append(location)

    def push_duration(self,start_time,end_time):
        duration = end_time - start_time
        if len(self.path_duration_list) >= 5:
            self.path_duration_list.pop(0)
        self.path_duration_list.append(duration)

    def get_median_duration(self):
        if len(self.path_duration_list) == 0:
            return 3.0
        else:
            return statistics.median(self.path_duration_list)


#Keeps track of player movement and state
class User:
    class PlayerInput:
        def __init__(self):
            self.forward = None
            self.backward = None
            self.left = None
            self.right = None
            self.use = None
            self.map = None
            self.crouch = None
            self.sprint = None
            self.console = None
            self.jump = None
            self.killswitch = None
            self.console_delay = 1
            self.add_door = None
            self.add_bag = None
            self.add_bed = None
            self.add_detour = None


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
            self.kill_switch = False

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
            self.path_list = None

        def update(self,bags,doors,paths_di,paths_li):
            self.spawnlist = bags
            self.doorlist = doors
            self.path_dict = paths_di
            self.path_list = paths_li

    class ConsoleWindowCords:
        def __init__(self):
            self.input_cord = None
            self.copy_cord = None
            self.clear_cord = None



    #Create the user with the appropriate key binds
    #Mouse settings can be computed from python
    #We assume certain buttons in the console are at certain coordinates, these can be changed with methods
    #Vision and Location get updated frequently
    #Death Status gets checked whenever console is used

    def __init__(self):
        self.sens = None
        self.map_zoom = None
        self.player_input = self.PlayerInput()
        self.standard_info = self.StandardInfo()
        self.console_cords = self.ConsoleWindowCords()
        self.status = self.PlayerCriticalStatus()
        self.should_stop = False
        self.tools = self.CodeRaidTools()
        self.autopause_tuple = (None,None,None,None,None)
        self.codes_df = None

    def type(self,string1):
        time.sleep(self.player_input.console_delay)
        for character in string1:
            time.sleep(self.player_input.console_delay/10)
            outputkeyboard.press(character)
            outputkeyboard.release(character)

    def release_all(self):
        keylist = [self.player_input.sprint,self.player_input.crouch,self.player_input.use, self.player_input.map,
                   self.player_input.jump, self.player_input.forward, self.player_input.backward, self.player_input.left,
                   self.player_input.right]
        for key1 in keylist:
            outputkeyboard.release(key1)

    def wait(self,time1):
        iterations_per_second = 20 #how many times a second we want to check the killswitch key
        # if(self.should_stop_warnings()):
        #     #self.release_all()?
        #     sys.exit(0)
        iterations = math.floor(time1 * iterations_per_second)
        remainder = ((time1 * iterations_per_second) - math.floor(time1 * iterations_per_second))/iterations_per_second
        for i in range(iterations):
            time.sleep(1.0/iterations_per_second)
            if(self.should_stop_warnings()):
                print("Killswitch toggled")
                self.should_stop = True
                self.release_all() #incase we are running
                sys.exit(0)
        time.sleep(remainder)
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
                    elif ("Map" in myline):
                        self.player_input.map = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Crouch" in myline):
                        self.player_input.crouch = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Sprint" in myline):
                        self.player_input.sprint = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Console " in myline):
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
                    elif ("Copy" in myline):
                        tempstr = myline[(myline.index("=") + 1):len(myline)].strip()
                        x = tempstr[(tempstr.index("(") + 1):tempstr.index(",")]
                        y = tempstr[(tempstr.index(",") + 1):(len(tempstr) - 1)]
                        self.console_cords.copy_cord = (x,y)
                    elif ("Clear" in myline):
                        tempstr = myline[(myline.index("=") + 1):len(myline)].strip()
                        x = tempstr[(tempstr.index("(") + 1):tempstr.index(",")]
                        y = tempstr[(tempstr.index(",") + 1):(len(tempstr) - 1)]
                        self.console_cords.clear_cord = (x,y)
                    elif ("Input" in myline):
                        tempstr = myline[(myline.index("=") + 1):len(myline)].strip()
                        x = tempstr[(tempstr.index("(") + 1):tempstr.index(",")]
                        y = tempstr[(tempstr.index(",") + 1):(len(tempstr) - 1)]
                        self.console_cords.input_cord = (x,y)
                    elif ("Killswitch" in myline):
                        self.player_input.killswitch = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Add_door" in myline):
                        self.player_input.add_door = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Add_bag" in myline):
                        self.player_input.add_bag = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Add_bed" in myline):
                        self.player_input.add_bed = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Add_detour" in myline):
                        self.player_input.add_detour = getkey(myline[(myline.index("=") + 1):len(myline)].strip())
                    elif ("Cons_Delay" in myline):
                        self.player_input.console_delay = float(myline[(myline.index("=") + 1):len(myline)].strip())
                self.autopause_tuple = (code_f,pd_f,ad_f,db1_f,db2_f)
            #print(os.path.basename(config_path))
        else:
            raise FileNotFoundError

    def read_codefile(self):
        code_table = sys.argv[2]
        codes = pd.read_csv(code_table, converters={'Code': str})
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


    #Use console to find in game sensitivity, starting from regular game state
    def get_ingame_sens(self):
        usekey(self.player_input.console)
        self.wait(self.player_input.console_delay)
        outputmouse.position = (self.console_cords.clear_cord[0],self.console_cords.clear_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        outputmouse.position = (self.console_cords.input_cord[0], self.console_cords.input_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.type("input.sensitivity")
        usekey(Key.enter)
        self.wait(self.player_input.console_delay)
        outputmouse.position = (self.console_cords.copy_cord[0], self.console_cords.copy_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        output = pc.paste()
        cut = output[output.index("vity: \""):len(output)]
        cut2 = cut[7:len(cut)]
        cut3 = float(cut2[0:(cut2.index("\""))])
        usekey(self.player_input.console)
        self.sens = cut3


    #Scroll in and out of the map to get the desired zoom, set by programmer
    def set_zoom(self):
        self.suicide(True,True)
        print("setting zoom")
        scrolltofullzoomin = 20
        set_map_zoom = 5
        for i in range(scrolltofullzoomin):
            self.wait(0.02)
            mouse.scroll(0, 1)
        for i in range(set_map_zoom):
            self.wait(0.02)
            mouse.scroll(0, -1)
        self.map_zoom = set_map_zoom

    def movemousetobag(self,bagloc : Location, currentlocation : Location):
        bagx = bagloc.xcoord
        bagy = bagloc.ycoord
        #mapzoom greater than 5 is untested
        x = self.map_zoom
        mapzoom_multiplier = 1.646 - 0.1561 * x + (0.005282 * (x * x))
        currentposition = currentlocation
        centercord = mouse.position
        bag_change = (bagx-currentposition.xcoord,bagy-currentposition.ycoord)
        outputmouse.position = (centercord[0] + (bag_change[0] * 1.35 * mapzoom_multiplier), centercord[1] + -(bag_change[1] * 1.35 * mapzoom_multiplier))

    def turnx(self, xdegreesingame):
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(7.4075 * (1.0/self.sens) * xdegreesingame), 0, 0, 0)

    def turny(self, ydegreesingame):
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, 0, int(7.4075 * (1.0/self.sens)* ydegreesingame), 0, 0)

    def turn(self, xdegreesingame, ydegreesingame):
        win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(7.4075 * (1.0/self.sens) * xdegreesingame), - int(7.4075 * (1.0 / self.sens) * ydegreesingame), 0, 0)

    #They take in vision objects
    #Turn the character to the desired vector
    def face_direction(self, current_eyes : Vision, target_eyes : Vision):
        #convert x-coordinates:
        inputx = current_eyes.xcoord
        if inputx > 180:
            inputx -= 360
        outputx = target_eyes.xcoord
        if outputx > 180:
            outputx -= 360
        xdegs = (outputx - inputx) % 360
        if xdegs > 180:
            xdegs -= 360

        def standardize_ycoord(ycoord):
            #These should be the only 2 possible scenarios according to rust console
            if(ycoord >= 270):
                ycoord = -(ycoord - 360)
            elif(ycoord <= 90):
                ycoord = -ycoord
            return ycoord
        inputy = standardize_ycoord(current_eyes.ycoord)
        outputy = standardize_ycoord(target_eyes.ycoord)
        ydegs = outputy - inputy
        self.turn(xdegs,ydegs)
        #print("XDEGS: " + str(xdegs) + ", YDEGS: " + str(ydegs))
        self.map_vision = target_eyes

    def face_location(self, current_eyes : Vision, current_location : Location, target_location : Location):
        deltaX = target_location.xcoord - current_location.xcoord
        deltaY = target_location.ycoord - current_location.ycoord
        rad = math.atan2(deltaX, deltaY)
        xdegs = rad * (180/math.pi)
        print(xdegs)
        deltaD = math.sqrt((deltaX * deltaX) + (deltaY * deltaY))
        deltaH = target_location.zcoord - current_location.zcoord
        rad2 = math.atan2(deltaH, deltaD)
        ydegs = rad2 * (180 / math.pi)
        print(ydegs)
        self.face_direction(current_eyes,Vision(0,0,0))
        self.turn(xdegs,ydegs)


    #Run in game to coordinate (not super precise)
    def move_directly_to_cord(self, current_eyes : Vision, current_location : Location, target_location : Location):
        self.face_location(current_eyes,current_location,target_location)
        absx = abs(target_location.xcoord - current_location.xcoord)
        absy = abs(target_location.ycoord - current_location.ycoord)
        absz = abs(target_location.zcoord - current_location.zcoord)
        duration = (0.142 * absx) + (0.142 * absy) + (0.04 * absz) + 0.2
        outputkeyboard.press(self.player_input.sprint)
        outputkeyboard.press(self.player_input.forward)
        self.wait(duration)
        outputkeyboard.release(self.player_input.forward)
        outputkeyboard.release(self.player_input.sprint)

    #Crouch to coordinate for better precision
    def move_precisely_to_cord(self, current_eyes : Vision, current_location : Location, target_location : Location):
        self.face_location(current_eyes, current_location, target_location)
        absx = abs(target_location.xcoord - current_location.xcoord)
        absy = abs(target_location.ycoord - current_location.ycoord)
        absz = abs(target_location.zcoord - current_location.zcoord)
        duration = (0.435 * absx) + (0.435 * absy) + (0.12 * absz)
        outputkeyboard.press(self.player_input.crouch)
        outputkeyboard.press(self.player_input.forward)
        self.wait(duration)
        outputkeyboard.release(self.player_input.forward)
        outputkeyboard.release(self.player_input.crouch)

    #Uses both move functions to get precisely to the door and look at the lock in a timely manner
    #Takes a path object as an input
    def get_to_door_and_face_lock(self, path_object: Path, departure_time: float):
        for location in path_object.locationlist:
            self.update_vision(True, False)
            self.update_location(False, True)
            self.move_directly_to_cord(self.standard_info.map_vision, self.standard_info.map_location,
                                       location)

        distance = 999999
        self.update_vision(True, False)
        self.update_location(False, True)
        while (distance >= 0.8):
            if (distance > 4.5):
                self.move_directly_to_cord(self.standard_info.map_vision, self.standard_info.map_location,path_object.door.location)
            else:
                self.move_precisely_to_cord(self.standard_info.map_vision, self.standard_info.map_location,
                                            path_object.door.location)
            self.update_vision(True, False)
            self.update_location(False, True)
            distance = math.sqrt(((path_object.door.location.xcoord - self.standard_info.map_location.xcoord) *
                       (path_object.door.location.xcoord - self.standard_info.map_location.xcoord)) +
                      ((path_object.door.location.ycoord - self.standard_info.map_location.ycoord) * (
                                  path_object.door.location.ycoord - self.standard_info.map_location.ycoord)) +
                      ((path_object.door.location.zcoord - self.standard_info.map_location.zcoord) * (
                                  path_object.door.location.zcoord - self.standard_info.map_location.zcoord)))
        #exited while loop so we arrived
        arrival_time = timestamp()
        path_object.push_duration(departure_time,arrival_time)
        self.face_direction(self.standard_info.map_vision, path_object.door.angle)

    #Perform the coderaid on the door with 5 codes, update the door object accordingly, being mindful of a code overload ban
    def punch_in_5_codes(self, door_object):
        while(timestamp() - door_object.time_of_last_code <= 61.0):
            self.wait(0.2)

        for i in range(6):
            outputkeyboard.press(self.player_input.use)
            self.wait(self.player_input.console_delay * 4)
            win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(7.4075 * (1.0 / self.sens) * 3), int(7.4075 * (1.0 / self.sens) * 5), 0, 0)
            self.wait(self.player_input.console_delay * 2)
            outputmouse.click(Button.left,1)
            self.wait(self.player_input.console_delay)
            outputkeyboard.release(self.player_input.use)
            self.wait(self.player_input.console_delay * 2)
            print(self.codes_df.iloc[self.standard_info.current_code_count, 0])
            self.type(str(self.codes_df.iloc[self.standard_info.current_code_count,0]))
            self.standard_info.current_code_count += 1
            self.wait(self.player_input.console_delay * 8)

        door_object.update_after_5_codes(False)
        print(door_object.time_of_last_code)

        #one or the other
        self.wait(40 * self.player_input.console_delay)

        #move_mouse and use pynput
        #check after 2 codes if died to codelock, if yes than is blocked
        #is_banned = False
        #door_object.update_after_5_codes(is_banned)

    #Uses the zoom parameter and current location to select a bag/bed and spawns there
    #Returns true if sucessfully spawned
    def spawn(self, spawn_object: Spawn, current_location: Location):
        self.movemousetobag(spawn_object.location, current_location)
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(25 * self.player_input.console_delay)
        spawn_object.time_of_last_spawn = timestamp()
        usekey(self.player_input.jump)
        self.wait(self.player_input.console_delay * 3)

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
        elif(killedcode):
            self.status.update_death(0)

    def update_location(self,must_open_console,must_close_console):
        if (must_open_console):
            usekey(self.player_input.console)
            self.wait(self.player_input.console_delay)

        outputmouse.position = (self.console_cords.clear_cord[0], self.console_cords.clear_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        outputmouse.position = (self.console_cords.input_cord[0], self.console_cords.input_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        self.type("client.printpos")
        usekey(Key.enter)
        self.wait(self.player_input.console_delay)
        outputmouse.position = (self.console_cords.copy_cord[0], self.console_cords.copy_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        cut = pc.paste()
        cut2 = cut[cut.index("printpos"):len(cut)]
        x = float(cut2[(cut2.index("(") + 1):cut2.index(",")])
        cut3 = cut2[cut2.index(",") + 1:len(cut2)]
        cut4 = cut3[cut3.index(",") + 1:len(cut3)]
        #print(cut4)
        z = float(cut3[1:cut3.index(",")])
        y = float(cut4[1:cut4.index(")")])
        self.standard_info.map_location = Location(x,y,z)

        if (must_close_console):
            usekey(self.player_input.console)
            self.wait(self.player_input.console_delay)

    def update_vision(self,must_open_console,must_close_console):
        if (must_open_console):
            usekey(self.player_input.console)
            self.wait(self.player_input.console_delay)

        outputmouse.position = (self.console_cords.clear_cord[0], self.console_cords.clear_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        outputmouse.position = (self.console_cords.input_cord[0], self.console_cords.input_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        self.type("client.printeyes")
        usekey(Key.enter)
        self.wait(self.player_input.console_delay)
        outputmouse.position = (self.console_cords.copy_cord[0], self.console_cords.copy_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        cut = pc.paste()
        cut2 = cut[cut.index("printeyes"):len(cut)]
        y = float(cut2[(cut2.index("(") + 1):cut2.index(",")])
        cut3 = cut2[cut2.index(",") + 1:len(cut2)]
        cut4 = cut3[cut3.index(",") + 1:len(cut3)]
        #print(cut4)
        x = float(cut3[1:cut3.index(",")])
        z = float(cut4[1:cut4.index(")")])
        self.standard_info.map_vision = Vision(x,y,z)

        if (must_close_console):
            usekey(self.player_input.console)
            self.wait(self.player_input.console_delay)

    def suicide(self,must_open_console,must_close_console):
        self.wait(self.player_input.console_delay)
        if(must_open_console):
            usekey(self.player_input.console)
            self.wait(self.player_input.console_delay)
        outputmouse.position = (self.console_cords.input_cord[0], self.console_cords.input_cord[1])
        self.wait(self.player_input.console_delay)
        outputmouse.click(Button.left, 1)
        self.wait(self.player_input.console_delay)
        self.type("kill")
        self.wait(self.player_input.console_delay * 2)
        usekey(Key.enter)
        self.wait(self.player_input.console_delay * 2)
        if (must_close_console):
            usekey(self.player_input.console)
            self.wait(5)

    def should_stop_warnings(self) -> bool:
        if(self.status.kill_switch == True):
            print("Killswitch toggled")
            return True
        if(self.status.successfull_code):
            print("Found Code")
            if(self.autopause_tuple[0] == True):
                return True
        if(self.status.is_killed_player):
            print("Warning: Killed By Player")
            if(self.autopause_tuple[1] == True):
                return True
        if (self.status.is_killed_animal):
            print("Warning: Killed By Animal")
            if (self.autopause_tuple[2] == True):
                return True
        if (self.status.destroyed_bag):
            print("Warning: Destroyed Spawn")
            if (self.autopause_tuple[3] == True):
                return True
        if (self.status.door_banned):
            print("Warning: Door Got Banned")
            if (self.autopause_tuple[4] == True):
                return True
        return False

    def create_tools(self):
        # We begin with tutples with door and spawn information, door tuple has location, vision and id
        # spawn tuple has location, whether its a bed, and the associated door, updated paths has the spawnid and then corresponding location stoppages to the door
        self.read_config()
        self.read_codefile()

        from pynput import keyboard

        def listentoendinitialization():
            doorid = 1
            spawnid = 1
            doorlist = []
            spawnlist = []
            # Construct a path dictionary easily accessible from a spawnid
            path_dict = {}
            path_list = []
            def on_press(key):
                pass

            def on_release(key):
                nonlocal doorid
                nonlocal spawnid
                nonlocal doorlist
                nonlocal spawnlist
                nonlocal path_dict
                nonlocal path_list
                if key == self.player_input.killswitch:
                    self.tools.update(spawnlist, doorlist, path_dict, path_list)
                    self.set_zoom()
                    self.get_ingame_sens()
                    print("Ended initialization")
                    return False
                elif key == self.player_input.add_door:
                    print("Added door: " + str(doorid))
                    self.update_vision(True,False)
                    self.update_location(False,True)
                    door_vision = self.standard_info.map_vision
                    door_location = self.standard_info.map_location
                    print("At vision: " + str(door_vision))
                    print("At location: " + str(door_location))
                    newdoor = Door(door_location,door_vision,doorid)
                    doorid+=1
                    doorlist.append(newdoor)
                elif key == self.player_input.add_bag:
                    print("Added spawn (bag): " + str(spawnid))
                    self.update_location(True,True)
                    bag_location = self.standard_info.map_location
                    print("At location: " + str(bag_location))
                    newspawn = Spawn(bag_location,False,doorlist[-1].door_id,spawnid)
                    spawnid+=1
                    spawnlist.append(newspawn)
                    newpath = Path(newspawn,doorlist[-1])
                    path_dict[newspawn.spawn_id] = newpath
                    path_list.append(newpath)
                elif key == self.player_input.add_bed:
                    print("Added spawn (bed): " + str(spawnid))
                    self.update_location(True, True)
                    bed_location = self.standard_info.map_location
                    newspawn = Spawn(bed_location, True, doorlist[-1].door_id, spawnid)
                    print("At location: " + str(bed_location))
                    spawnid += 1
                    spawnlist.append(newspawn)
                    newpath = Path(newspawn, doorlist[-1])
                    path_dict[newspawn.spawn_id] = newpath
                    path_list.append(newpath)
                elif key == self.player_input.add_detour:
                    print("Added detour to spawn: " + str(spawnid - 1))
                    self.update_location(True, True)
                    detour_location = self.standard_info.map_location
                    print("At location: " + str(detour_location))
                    currentpath = path_dict[spawnid - 1]
                    currentpath.updatepath(detour_location)

            # Collect events until released
            with keyboard.Listener(
                    on_press=on_press,
                    on_release=on_release) as listener:
                listener.join()

        t1 = threading.Thread(target=listentoendinitialization, args=())
        t1.start()
        t1.join()

    def listenforkillswitch(self,shutdown_bool):
        from pynput import keyboard

        def on_press(key):
            pass

        def on_release(key):
            if key == self.player_input.killswitch:
                if(shutdown_bool):
                    self.status.kill_switch = True
                return False

        # Collect events until released
        with keyboard.Listener(
                on_press=on_press,
                on_release=on_release) as listener:
            listener.join()

    def wait_for_start(self):
        t1 = threading.Thread(target=self.listenforkillswitch(False), args=())
        t1.start()
        t1.join()

    # sort all paths by shortest duration
    # iterate through each in order, checking if (now - door_last_touched) + path_duration >= 61 seconds
    # if yes we have the path, if no return None
    def getbestpath(self):
        self.tools.path_list.sort(key = lambda x : x.get_median_duration()) #sorting by smallest median duration using anon func
        for path in self.tools.path_list:
            mytime = timestamp()
            if (mytime - path.door.time_of_last_code + path.get_median_duration() >= 61.0 and
                    ((path.spawn.is_bed == False and (mytime - path.spawn.time_of_last_spawn) >= bagtimer) or
                    (path.spawn.is_bed == True and (mytime - path.spawn.time_of_last_spawn) >= bedtimer))):
                return path
        return None



    #Coderaid
    def coderaidtest(self):
        while(self.standard_info.current_code_count <= 10000):
            print("REEE")
            self.wait(0.5)

    def coderaid(self):
        while (self.standard_info.current_code_count <= 10000):
            self.wait(0.5)
            print("waiting")
            optimalpath = self.getbestpath()
            if optimalpath is None: #we did find a suitable spawn point because of timers
                continue #wait till the timers allow for a spawn
            initial_mouse_pos = list(outputmouse.position)
            self.update_location(True, True)
            outputmouse.position = (initial_mouse_pos[0], initial_mouse_pos[1])
            self.wait(self.player_input.console_delay)
            startrun_time = timestamp()
            self.spawn(optimalpath.spawn,self.standard_info.map_location)
            self.get_to_door_and_face_lock(optimalpath, startrun_time)
            self.punch_in_5_codes(optimalpath.door)
            #print("REEE")
            #sys.exit(0)






            #update current location
            #choose best bag and spawn at bag
            #get to door and face lock
            #punch in 5 codes
            #process and wait death screen

    #Main Drivercode
    def main(self):
        self.create_tools()
        self.wait_for_start()
        t1 = threading.Thread(target=self.coderaid, args=())
        t2 = threading.Thread(target=self.listenforkillswitch, args=(True,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()




from pynput.mouse import Controller
mouse = Controller()
'''
for i in range(20):
    time.sleep(0.02)
    mouse.scroll(0, 1)
for i in range(5):
    time.sleep(0.02)
    mouse.scroll(0, -1)
'''
'''
from pynput import mouse

def on_move(x, y):
    print('Pointer moved to {0}'.format(
        (x, y)))

def on_click(x, y, button, pressed):
    print('{0} at {1}'.format(
        'Pressed' if pressed else 'Released',
        (x, y)))
    if not pressed:
        # Stop listener
        return False

def on_scroll(x, y, dx, dy):
    print('Scrolled {0} at {1}'.format(
        'down' if dy < 0 else 'up',
        (x, y)))

 Collect events until released
with mouse.Listener(
        on_move=on_move,
        on_click=on_click,
        on_scroll=on_scroll) as listener:
    listener.join()
'''
#copy: 1625,900
#clear: 1700,900

def testkillswitch():
    from pynput import keyboard

    def listenforfail():

        def on_press(key):
            try:
                print('alphanumeric key {0} pressed'.format(
                    key.char))
            except AttributeError:
                print('special key {0} pressed'.format(
                    key))

        def on_release(key):
            global kill_switch
            print('{0} released'.format(
                key))
            if key == keyboard.Key.esc:
                # Stop listener
                #sys.exit(0)
                kill_switch = True
                return False

        # Collect events until released
        with keyboard.Listener(
                on_press=on_press,
                on_release=on_release) as listener:
            listener.join()

    def printtest2(b):
        while(True):
            global kill_switch
            print(kill_switch)
            time.sleep(5)
            if(kill_switch):
                return True
                #sys.exit(0)


    import threading
    t1 = threading.Thread(target=printtest2, args = (10,))
    t2 = threading.Thread(target=listenforfail, args = ())
    t1.start()
    t2.start()
    t1.join()
    t2.join()

def testkillswitch2(user: User):
    from pynput import keyboard

    def listenforfail(x):

        def on_press(key):
            try:
                #print('alphanumeric key {0} pressed'.format(
                    #key.char))
                pass
            except AttributeError:
                #print('special key {0} pressed'.format(
                    #key))
                pass

        def on_release(key):
            print(x)
            #print('{0} released'.format(
                #key))
            if key == user.player_input.killswitch:
                # Stop listener
                #sys.exit(0)
                user.status.kill_switch = True
                return False

        # Collect events until released
        with keyboard.Listener(
                on_press=on_press,
                on_release=on_release) as listener:
            listener.join()

    def test3():
        time.sleep(0.5)
        print("WOOHOO")

    def printtest5():
        #user.get_ingame_sens()
        #user.set_zoom()
        #spawn1 = Spawn(Location(-1975.92,1512.50,3.75),False,1,1)
        door1 = Door(Location(-2037.60,1547.71,8.67),Vision(342.31,316.31,0),1)
        #path1 = Path(spawn1,door1)
        #print("STARTED GET TO DOOR")
        #user.get_to_door_and_face_lock(path1)

        #print((user.codes_df.iloc[2,0]))
        #user.punch_in_5_codes(door1)
        while(True):
            print("hi")
            user.wait(0.5)


    t1 = threading.Thread(target=printtest5, args = ())
    t2 = threading.Thread(target=listenforfail, args = ("REEE",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

def testmouse():
    from pynput import mouse

    def on_move(x, y):
        print('Pointer moved to {0}'.format(
            (x, y)))

    def on_click(x, y, button, pressed):
        print('{0} at {1}'.format(
            'Pressed' if pressed else 'Released',
            (x, y)))
        if not pressed:
            # Stop listener
            return False

    def on_scroll(x, y, dx, dy):
        print('Scrolled {0} at {1}'.format(
            'down' if dy < 0 else 'up',
            (x, y)))

    # Collect events until released
    with mouse.Listener(
            on_move=on_move,
            on_click=on_click,
            on_scroll=on_scroll) as listener:
        listener.join()

test = User()
test.main()

# test.read_config()
# test.read_codefile()
# testkillswitch2(test)







#outputkeyboard.press(test.player_input.crouch)
#time.sleep(0.3)
#outputkeyboard.press("d")
#time.sleep(0.03)
#outputkeyboard.release("d")
#outputkeyboard.release(test.player_input.crouch)
#test.get_ingame_sens()





#testmouse()
#test.map_zoom = 10
#test.movemousetobag(472.71,175.9)
#print(test.sens)



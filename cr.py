import ctypes
import math
import time
import datetime
import pynput
import os
import sys
import pandas as pd
import pyperclip as pc
import win32api, win32con, win32gui
#pip install pywin32
#constants
bagtimer = 300
bedtimer = 120

#keyboard IO functions
from pynput.keyboard import Key, Controller, Listener
outputkeyboard = Controller()
from pynput.mouse import Controller, Button
outputmouse = Controller()
def usekey(mykey):
    outputkeyboard.press(mykey)
    outputkeyboard.release(mykey)

def type(string):
    for character in string:
        time.sleep(0.05)
        outputkeyboard.press(character)
        outputkeyboard.release(character)


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

        def update(self,bags,doors,paths):
            self.spawnlist = bags
            self.doorlist = doors
            self.path_dict = paths

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

    def wait(self,time1):
        iterations_per_second = 5.0 #how many times a second we want to check the killswitch key
        if(self.should_stop_warnings()):
            sys.exit(0)
        iterations = math.floor(time1 * iterations_per_second)
        remainder = ((time1 * iterations_per_second) - math.floor(time1 * iterations_per_second))/iterations_per_second
        for i in range(iterations):
            time.sleep(1.0/iterations_per_second)
            if(self.status.kill_switch == True):
                print("Killswitch toggled")
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
                    elif ("Cons_Delay" in myline):
                        self.player_input.console_delay = float(myline[(myline.index("=") + 1):len(myline)].strip())
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
        type("input.sensitivity")
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
        self.sens = cut3


    #Scroll in and out of the map to get the desired zoom, set by programmer
    def get_zoom(self):
        #temp
        self.map_zoom = None

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
        elif(killedcode):
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
            self.check_stop_warnings()


#win32api.mouse_event(win32con.MOUSEEVENTF_MOVE, int(9.259 * 50), 0, 0, 0)

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
#input: 1600,925
copy= (1625,900)
clear = (1700,900)
input = (1600,925)
def testconsole():
    mouse.position = (copy[0],copy[1])
    mouse.click(Button.left, 1)
    time.sleep(0.5)
    mouse.position = (clear[0],clear[1])
    mouse.click(Button.left, 1)
    time.sleep(0.5)
    mouse.position = (input[0],input[1])
    mouse.click(Button.left, 1)
    print("moved mouse")
    type("client.printpos")
    usekey(Key.enter)
    mouse.position = (copy[0],copy[1])
    mouse.click(Button.left, 1)
    time.sleep(0.5)
    mouse.position = (clear[0],clear[1])
    mouse.click(Button.left, 1)
    time.sleep(0.5)

kill_switch = False
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

    def printtest5():
        user.get_ingame_sens()


    import threading
    t1 = threading.Thread(target=printtest5, args = ())
    t2 = threading.Thread(target=listenforfail, args = ())
    t1.start()
    t2.start()
    t1.join()
    t2.join()


test = User()
print("testing")
test.read_config()
test.read_codefile()
#pywin32.moveTo()
print("sus: ")
time.sleep(1)
#test.get_ingame_sens()
testkillswitch2(test)
print(test.sens)

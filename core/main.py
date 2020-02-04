import time
import cv2
import core.display as display
from calibration.calibrate import colors
from core.core_algorithm import core

from core.display import Display
from utils.classes import PointHolder
from utils.dataclass import DataClass
from utils.mycv2_utils import paint_lines
from utils.path_cutout import CutOutCropper


def iteration(displayer, cams, state):
    front, top, menu = cams

    ##
    # Read Frames
    ##
    r, top_frame = top.camera.read()
    assert r

    r, front_frame = front.camera.read()
    assert r

    ##
    # Crop frames
    ##
    front_c = front.cropper.cutout(front_frame)
    top_c = top.cropper.cutout(top_frame)
    menu_c = menu.cropper.cutout(front_frame)

    ##
    # Core Operations
    ##
    contours, (menu_location, board_location) = core(front_c, top_c, menu_c, displayer, state)

    ##
    # Display Frames
    ##
    drawn = displayer.draw(state.ph.paths)
    if board_location is not None:
        drawn = display.draw_point(drawn, *displayer.place_point(*board_location), color=(128, 0, 128), radius=10)
    cv2.imshow('Board Drawing', drawn)

    cv2.drawContours(top_c, contours, -1, display.GREEN, cv2.FILLED)
    cv2.imshow('Top Camera', top_c)

    paint_lines(menu_c, menu_c.shape[0], state.menu['lines'])
    if menu_location is not None:
        menu_c = display.draw_point(menu_c, *menu_location, *(0, 0))
    cv2.imshow('Menu Camera', menu_c)

    display.draw_polygon(front_frame, front.points)
    if board_location is not None:
        front_frame = display.draw_point(front_frame, *board_location, *front.cropper.startpoint)
    elif menu_location is not None:
        front_frame = display.draw_point(front_frame, *menu_location, *menu.cropper.startpoint, color=(0xFF, 0, 0))
    cv2.imshow('Board Live', front_frame)


def main_loop(period, displayer, cams, state):
    while all(cam.camera.isOpened() for cam in cams if cam is not None):
        start_time = time.time()

        iteration(displayer, cams, state)

        end_time = time.time()
        loop_duration = round((end_time - start_time) * 1000)
        loop_duration_ms = period - int(loop_duration)
        time_left = loop_duration_ms if loop_duration_ms > 0 else 1

        key = cv2.waitKey(time_left)
        if key == ord('q'):
            break
        elif key == ord('c'):
            state.ph.clear()


def camera_setup(camera, calib):
    shape = calib['height'], calib['width'], calib['channels']
    pnts = calib['points']

    cropper = CutOutCropper(shape, pnts)

    return DataClass({
        'cropper': cropper,
        'shape': shape,
        'camera': camera,
        'points': [tuple(lst) for lst in pnts]
    })


def do(conf, caps):
    ##
    # Extract cameras
    ##
    front = camera_setup(caps['front_camera'], conf['calibration']['front_camera'])
    top = camera_setup(caps['top_camera'], conf['calibration']['top_camera'])
    menu = camera_setup(caps['top_camera'], conf['calibration']['menu_camera'])

    ##
    # Init Menu
    ##
    menu_conf = conf['menu']

    menu_buttons = {
        (button['bottom'], button['upper']): None if button['color'] is None else tuple(button['color'])
        for button in menu_conf
    }

    menu_lines = {
        button['upper'] for button in menu_conf
    }
    menu_lines.remove(max(menu_lines))

    ##
    # Init display
    ##
    state = DataClass({
        'ph': PointHolder(),
        'color': colors['black'],
        'setcolor': None,
        'menu': {
            'buttons': menu_buttons,
            'lines': menu_lines
        }
    })

    def colorset(c):
        nonlocal state
        state.color = c
        state.ph.color = c

    state.setcolor = colorset

    displayer = Display(front.cropper.dimensions, state)

    ##
    # Main Loop
    ##
    fps = 30
    period = 1000 // fps
    main_loop(period, displayer, (front, top, menu), state)

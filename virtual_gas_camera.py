# partly based on:
# https://stackoverflow.com/questions/76725481/streaming-video-from-opencv-through-gstreamer-to-vlc-via-rtsp
# the simplebgc library is taken from:
# https://github.com/maiermic/robot-cameraman/tree/master
import simplebgc.gimbal
from simplebgc.gimbal import ControlMode
import laserfalcon.device
import logging
import json
import threading
import serial
from time import sleep, time
from datetime import datetime
import cv2
import numpy as np
import select
import sys

def live_stream(capture: cv2.VideoCapture, out_writer: cv2.VideoWriter):
    """Streams live video via the out_writer. Used in separate thread."""
    
    global frame_current
    next_frame_time = 0
    fps = int(capture.get(cv2.CAP_PROP_FPS))
    
    logger.debug("starting live stream")
    mythread = threading.current_thread()
    while getattr(mythread, "streaming", True) and capture.isOpened() and out_writer.isOpened():
        ret, frame = capture.read()
        if ret:
            # save frame to global variable for wait_video_motion()
            frame_current = frame
            # wait for correct time to send frame 
            while time() < next_frame_time:
                sleep(0.001)
            out_writer.write(frame) # send frame to stream pipeline
            next_frame_time = time() + (1/fps) # save at what time next frame is due
        else:
            logger.error(f"error getting frame. Return value from capture.read() was {ret}")
            break
    logger.debug("stopping live stream")

def wait_angle_error(gimbal_device: simplebgc.gimbal.Gimbal, threshold: float, check_delay: float):
    """
    Waits until the gimbal has settled using the difference between target angle and current angle as indicator.
    If the angle error on all axes is below threshold (in degrees), the function returns. Else it blocks.
    The check_delay specifies how often to query the gimbal angles.
    """    
    degree_factor = 0.02197265625 # conversion factor for values returned by simplebgc

    diff1 = threshold + 10
    diff2 = diff1
    diff3 = diff1
    
    while diff1 > threshold or diff2 > threshold or diff3 > threshold:
        sleep(check_delay)
        angles = gimbal_device.get_angles()
        diff1 = (angles.target_angle_1 - angles.imu_angle_1) * degree_factor
        diff2 = (angles.target_angle_2 - angles.imu_angle_2) * degree_factor
        diff3 = (angles.target_angle_3 - angles.imu_angle_3) * degree_factor

        logger.debug(f"target angle error [deg]: {diff1}, {diff2}, {diff3}")

def wait_video_settle(threshold: float,  check_delay: float):
    """
    Waits until the video input has settled (motion, automatic gain and white balance) using the difference between consecutive frames from the camera.
    Currently, two global frame variables are used which are updated by the livestream thread.
    Should probably be changed to something less hacky than global frames in the future.
    The check_delay specifies with which delay to compare the frames. As a cosnequence this is also the loop delay.
    """
    difference_value = None
    
    while difference_value == None or difference_value > threshold:
            frame_previous = frame_current # get current frame (filled by livestream thread)
            sleep(check_delay)

            # convert last two frames  to grayscale
            gray1 = cv2.cvtColor(frame_current, cv2.COLOR_BGR2GRAY) # frame current contains most recent frame at this point
            gray2 = cv2.cvtColor(frame_previous, cv2.COLOR_BGR2GRAY) # frame saved previously above

            # Calculate absolute difference between the two frames
            diff = cv2.absdiff(gray1, gray2)

            # Calculate the mean of the absolute differences
            difference_value = diff.mean()  # or diff.sum()

            logger.debug(f"difference between frames: {difference_value}")
            
def extract_and_insert(source_frame, destination_frame, x, y, width, height, dest_x, dest_y):
    """
    Extracts a rectangular area from the source frame and inserts it into the destination frame.

    Parameters:
    - source_frame: The source frame (numpy array) from which to extract the pixels.
    - destination_frame: The destination frame (numpy array) into which to insert the pixels.
    - x, y: The top-left corner coordinates of the rectangular area in the source frame.
    - width, height: The width and height of the rectangular area to extract.
    - dest_x, dest_y: The top-left corner coordinates in the destination frame where the pixels will be inserted.
    """
    # Extract the rectangular area from the source frame
    extracted_region = source_frame[y:y+height, x:x+width]

    # Insert the extracted region into the destination frame
    destination_frame[dest_y:dest_y+height, dest_x:dest_x+width] = extracted_region

def save_overlay(assembled_image,column_densities,x_steps, y_steps, subframe_width, subframe_height, filename):
    """
    Creates an overlay image on assembled_image, using the data in column_denisties. The overlay is written to filename.
    The data is distributed on the image using the steps and subframe parameters.
    """
    # create overlay
    # convert assembled image to grayscale and then to HSV
    overlay = cv2.cvtColor(assembled_image, cv2.COLOR_BGR2HSV)
    # set same hue everwhere
    overlay[:, :, 0] = 5
    # set saturation in each subframe region based on column density
    max_column_density = np.max(column_densities)
    min_column_density = np.min(column_densities)
    span_column_density = max_column_density - min_column_density
    for y_step in range(y_steps):
        for x_step in range(x_steps):
            # scale and offset values so max = 255, min = 0 saturation
            subframe_saturation = int ( (column_densities[y_step][x_step] - min_column_density) / span_column_density * 255)
            subframe_x = subframe_width * x_step
            subframe_y = subframe_height * y_step
            overlay[subframe_y:subframe_y+subframe_height, subframe_x:subframe_x+subframe_width, 1] = subframe_saturation # set saturation
    #save overlay 
    overlay = cv2.cvtColor(overlay, cv2.COLOR_HSV2BGR) # convert overlay back to RGB
    cv2.imwrite(filename, overlay, [cv2.IMWRITE_PNG_COMPRESSION, 0])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

experiment = {} # dict for holding all experiment data

# open laser falcon
logger.info("opening laser falcon")
laserfalcon = laserfalcon.device.Device(connection = serial.Serial('/dev/ttyUSB1', baudrate=19200, timeout=2))

if laserfalcon.get_version() != "SA3C30A":
    logger.warn("unexpected version for laser falcon device")

lf_settings = laserfalcon.get_settings()
experiment["laserfalcon_settings"] = lf_settings

# open gimbal
logger.info("opening gimbal")
gimbal = simplebgc.gimbal.Gimbal(connection = serial.Serial('/dev/ttyUSB0', baudrate=115200, timeout=2))
PITCH_SPEED = 720
YAW_SPEED = 720

# Open video device, get video dimensions and fps
cap = cv2.VideoCapture(0) #TODO parameterize device or autodetect
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
fps = int(cap.get(cv2.CAP_PROP_FPS))
logger.debug(f"video width, height, fps: {frame_width},{frame_height},{fps}")

# prepare stream pipeline
pipeline = 'appsrc is_live=1 ! videoconvert !x264enc key-int-max=12 byte-stream=true tune=zerolatency bitrate=500 speed-preset=superfast ! mpegtsmux ! tcpserversink port=5000 host=0.0.0.0'
out = cv2.VideoWriter(pipeline, cv2.CAP_GSTREAMER, 0, fps, (frame_width, frame_height))

# start separate thread for live video
frame_current = None # global variable for holding most current from livestream (TODO: find less hacky solution)
stream_task = threading.Thread(target=live_stream, args=(cap, out))
stream_task.start()

# configuration/placeholders
FOV_YAW = 22.7 # degrees full field of view, 0,0473 deg/pixel * 480
FOV_PITCH = 18.0 # degrees full field of view, 0,0563 deg/pixel * 320

X_STEPS = 15
Y_STEPS = X_STEPS
SUBFRAME_FOV_YAW = FOV_YAW / X_STEPS # FOV (degrees) of the subframes to acquire
SUBFRAME_FOV_PITCH = FOV_PITCH / Y_STEPS
SUBFRAME_WIDTH = int(frame_width/X_STEPS) # pixels
SUBFRAME_HEIGHT = int(frame_height/Y_STEPS) # pixels
SUBFRAME_X_SHIFT = -28 # pixels, shifts the subframe to match measured position (measurement beam and camera have a slight x/y offset)
SUBFRAME_Y_SHIFT = +5 # pixels
YAW_LEFT_EDGE = 0 - (FOV_YAW/2) # degrees, image center at left edge of full frame
PITCH_TOP_EDGE = 0 - (FOV_PITCH/2) # degrees, image center at top edge of full frame
YAW_STEP = SUBFRAME_FOV_YAW # degrees
PITCH_STEP = SUBFRAME_FOV_PITCH # degrees

column_densities_mean = [[0] * X_STEPS for _ in range(Y_STEPS)]
column_densities_median = [[0] * X_STEPS for _ in range(Y_STEPS)]

ASSEMBLED_HEIGHT = Y_STEPS * SUBFRAME_HEIGHT
ASSEMBLED_WIDTH = X_STEPS * SUBFRAME_WIDTH
assembled_image = np.zeros((ASSEMBLED_HEIGHT, ASSEMBLED_WIDTH, 3), np.uint8) # prepare frame for holding pixel saved during measurement

# video and angle error settling settings
ANGLE_SETTLE_THRESHOLD = 0.1 # degrees
ANGLE_SETTLE_DELAY = 0.025 # seconds
VIDEO_SETTLE_THRESHOLD = 10.0 # mean pixel difference of frames
VIDEO_SETTLE_DELAY = 0.2 # seconds


# wait for start of experiment while keeping gimbal at neutral
logger.info("press enter to start measurement")
while True:
    gimbal.control(
        pitch_mode=ControlMode.angle_rel_frame, pitch_speed=PITCH_SPEED, pitch_angle=0,
        yaw_mode=ControlMode.angle_rel_frame, yaw_speed=YAW_SPEED, yaw_angle=0)
    # Check if there is data ready to be read on sys.stdin (keyboard)
    rlist, _, _ = select.select([sys.stdin], [], [], 0.1)
    if rlist:
        key = sys.stdin.read(1)
        break


# genrate identifier for experiment files
identifier_string = str(datetime.now().strftime('%Y-%m-%dT%H.%M.%S'))

# return gimbal to neutral and save current view image
logger.info("saving reference view image")
gimbal.control(
    pitch_mode=ControlMode.angle_rel_frame, pitch_speed=PITCH_SPEED, pitch_angle=0,
    yaw_mode=ControlMode.angle_rel_frame, yaw_speed=YAW_SPEED, yaw_angle=0)
wait_angle_error(gimbal, ANGLE_SETTLE_THRESHOLD, ANGLE_SETTLE_DELAY)
wait_video_settle(VIDEO_SETTLE_THRESHOLD, VIDEO_SETTLE_DELAY)
neutral_image = frame_current #TODO: this breaks if livestream is not started/active

logger.info("starting measurement sweep")
experiment["start"] =datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')
for y_step in range(Y_STEPS):
    curr_pitch = PITCH_TOP_EDGE + (SUBFRAME_FOV_PITCH/2) + (PITCH_STEP * y_step) # we want to point at the middle of the subframe
    for x_step in range(X_STEPS):
        curr_yaw = YAW_LEFT_EDGE + (SUBFRAME_FOV_YAW/2) + (YAW_STEP * x_step) # we want to point at the middle of the subframe
        
        logger.info(f"moving to pitch {curr_pitch:.2f} deg, yaw {curr_yaw:.2f} deg")
        gimbal.control(
            pitch_mode=ControlMode.angle_rel_frame, pitch_speed=PITCH_SPEED, pitch_angle=curr_pitch,
            yaw_mode=ControlMode.angle_rel_frame, yaw_speed=YAW_SPEED, yaw_angle=curr_yaw)
        
        logger.info("waiting for gimbal/video to settle")
        wait_angle_error(gimbal, ANGLE_SETTLE_THRESHOLD, ANGLE_SETTLE_DELAY) # wait until controller has reached target angle
        wait_video_settle(VIDEO_SETTLE_THRESHOLD, VIDEO_SETTLE_DELAY)# wait until video movement has settled
        
        logger.info("saving pixels")
        # save the pixels/region of interest (roi) we are looking at
        roi_x = int(frame_width/2) - int(SUBFRAME_WIDTH/2) + SUBFRAME_X_SHIFT #TODO move these calculations into function, also prevent off-by-one errors
        roi_y = int(frame_height/2) - int(SUBFRAME_HEIGHT/2) + SUBFRAME_Y_SHIFT
        roi_width = SUBFRAME_WIDTH # chance of off-by-one errors here
        roi_height = SUBFRAME_HEIGHT # chance of off-by-one errors here
        dest_x = SUBFRAME_WIDTH * x_step
        dest_y = SUBFRAME_HEIGHT * y_step
        extract_and_insert(frame_current, assembled_image, roi_x,roi_y, roi_width, roi_height, dest_x, dest_y)

        # # save current view/pixels for debugging
        # cv2.imwrite(f'frame_{x_step:03d}_{y_step:03d}_{identifier_string}.png', frame_current, [cv2.IMWRITE_PNG_COMPRESSION, 0])
        # subframe = frame_current[roi_y:roi_y+roi_height, roi_x:roi_x+roi_width]
        # cv2.imwrite(f'frame_{x_step:03d}_{y_step:03d}_{identifier_string}.png', subframe, [cv2.IMWRITE_PNG_COMPRESSION, 0])

        logger.info("measuring")

        measure_success = False
        while not measure_success:
            measurement = laserfalcon.get_measurement()
            error_code = measurement["error"]
            if error_code == 1:
                measure_success = True
                main_value = measurement["main_value"]
                subsamples = [sub_val_dict["value"] for sub_val_dict in measurement["sub_values"]] # get the ppm*m values for all subsamples as a list
            else:
                logger.error(f"measurement failed with error code {error_code}. Retrying")
                gimbal.control( # reposition gimbal in hopes of clearing optically related errors
                    pitch_mode=ControlMode.angle_rel_frame, pitch_speed=PITCH_SPEED, pitch_angle=curr_pitch,
                    yaw_mode=ControlMode.angle_rel_frame, yaw_speed=YAW_SPEED, yaw_angle=curr_yaw)

        
        logger.info(f"main value is {main_value}")
        logger.info(f"collected {len(subsamples)} subsamples: {subsamples}")
        column_density_median = np.median(subsamples)
        column_density_mean = np.mean(subsamples)
        logger.info(f"column density is {column_density_mean} ppm*m mean, {column_density_median} ppm*m median")
        column_densities_mean[y_step][x_step] = column_density_mean # use matplotlib comaptible axis order
        column_densities_median[y_step][x_step] = column_density_median # use matplotlib comaptible axis order

# return gimbal to neutral
gimbal.control(
    pitch_mode=ControlMode.angle_rel_frame, pitch_speed=PITCH_SPEED, pitch_angle=0,
    yaw_mode=ControlMode.angle_rel_frame, yaw_speed=YAW_SPEED, yaw_angle=0)

experiment["end"] =datetime.now().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

#save experiment to disk
experiment["column_densities_mean"] = column_densities_mean
experiment["column_densities_median"] = column_densities_median

with open(f"{identifier_string}.json", 'w') as jsonfile:
    json.dump(experiment, jsonfile, indent=2)

cv2.imwrite(f'{identifier_string}_neutral.png', neutral_image, [cv2.IMWRITE_PNG_COMPRESSION, 0])
cv2.imwrite(f'{identifier_string}_assembled.png', assembled_image, [cv2.IMWRITE_PNG_COMPRESSION, 0])

# create and save overlays
filename_mean = f'{identifier_string}_overlay_mean.png'
save_overlay(assembled_image, column_densities_mean, X_STEPS,Y_STEPS,SUBFRAME_WIDTH, SUBFRAME_HEIGHT, filename_mean)

filename_median = f'{identifier_string}_overlay_median.png'
save_overlay(assembled_image, column_densities_median, X_STEPS,Y_STEPS,SUBFRAME_WIDTH, SUBFRAME_HEIGHT, filename_median)

# stop streaming and wait for it to finish
sleep(1) # allow buffer on receiver side to get final image
stream_task.streaming = False
stream_task.join()


# Release everything if job is finished
cap.release()
out.release()

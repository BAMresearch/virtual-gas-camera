# Virtual Gas Camera Repository
This is the software repository for the so-called 'virtual gas camera' associated with the paper 'Robotic Scanning Absorption Spectroscopy for Methane Leak Detection: the Virtual Gas Camera'.

**If you use code from this repo or base your work on it**, we kindly ask you to include a citation to our paper 'Robotic Scanning Absorption Spectroscopy for Methane Leak Detection: the Virtual Gas Camera'. Detailed reference information along with the final version of the paper can be found on [IEEE Xplore](https://ieeexplore.ieee.org/document/10556012). The accepted submitted (not final) version is available in conformance with IEEE policies [here](Lohrke_ISOEN_2024_accepted_repo_copyright_notice.pdf).

Please consider this repo a proof-of-concept example. The code is experimental and comes with no warranty whatsoever.

In case of bugs, problems, or questions feel free to open an [issue](https://github.com/BAMresearch/virtual-gas-camera/issues/new).

# Overview
The virtual gas camera is a software project which allows users of typical gas tomography systems, e.g. gimbal-mounted tunable diode laser absorption spectroscopy (TDLAS) sensors with a video camera, to extend their setup with gas-camera-like capabilities. Below is an example of a measurement where the virtual gas camera identifies two bags filled with methane (yellow). The middle bag (red) is a control with air.

<p align="center">
<img src="./docs/example_measurement_bags.png" height=240>
<img src="./docs/example_measurement_overlay.png" height=240>
</p>

Apart from the generation of overlay images in the field, the virtual gas camera also provides a live video feed. For details please see the paper. *(TODO: add link when paper is published)*. A typical field measurement is shown below.

<p align="center">
<img src="./docs/example_measurement_setup.png"  height= 300 >
</p>


# Getting Started
## Files Overview
* `virtual_gas_camera.py`: implements the virtual gas camera
* `test_lf.py`: simple script to test the Laser Falcon connection 
* `plot_column_density.py`: simple script to plot experimental results in more detail
* `laserfalcon`: folder containing TDLAS sensor library
* `simplebgc`: folder containing gimbal control library

## Prerequisites
* Laser Falcon TDLAS methane sensor (or rewrite the laserfalcon library for your own sensor)
* SimpleBGC Gimbal Controller (or rewrite the simplebgc library for your own gimbal controller)
* Video Grabber connected to you camera and compatible with OpenCV
* Linux PC on the robot side (we used Ubuntu 22.04.3)
* VLC player and SSH access from a second PC for monitoring and control

## Setup

### Install Requirements
* Install OpenCV for python on the robot side (see their [documentation](https://docs.opencv.org/4.x/df/d65/tutorial_table_of_content_introduction.html)) and test it in connection with your camera with some [example scripts](https://docs.opencv.org/3.4/dd/d43/tutorial_py_video_display.html)
* Pull this repository to a folder on the robot side
* Install the Python packages used in the scripts on the robot side e.g. by doing `pip install -r requirements.txt`
* Install VLC player or any other player capable of playing TCP video streams on the control PC
* Install an SSH terminal program on the control PC (included on Linux, on Windows use e.g. putty)

### Connecting and Measuring
* Make sure the control PC and the robot are in the same network and can see each other e.g. via 'ping'.
* Connect your terminal program to the robot.
* Launch the Virtual Gas Camera via the remote terminal: `python ./virtual_gas_camera.py`, the gimbal should travel to neutral.
* Open VLC player, choose, 'open network stream', and enter the address of the robot e.g. `tcp://192.168.1.42:5000`, reduce the buffer under advanced options to get better latency, e.g. 200 ms, you should now see live video.
* Press enter in the remote terminal to start the measurement, you will see the live video of the scan in VLC and results will be written to disk on the robot side.
* Setup a network share on the robot (e.g. using [Samba](https://ubuntu.com/tutorials/install-and-configure-samba)) if you want to access the experiment data and overlay images immediately.
* You can adjust the parameters of the measurement using the constants defined in the Python script.

# Acknowledgements
This code uses the simplebgc library which is Copyright (c) 2019 Michael Maier under MIT license. See readme in the subfolder and/or https://github.com/maiermic/robot-cameraman/tree/master for more information.

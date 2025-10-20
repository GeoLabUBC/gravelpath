# Description: This script is used to process images of a light table and identify
# particles in subsequent images. It is used to measure the size of particles and ultimately
# to count the number of particles in each image for sediment transport studies.
# 2024-03-10: Tobias Mueller, initial version
# 2024-09-17: Sol Leader-cole, adjusted version
# 2024-11-04: Kellen Malek, modified to run w/ multiprocessing
# 2024-12-27: Sol Leader-Cole, incorporated no_filter analysis into this file to improve efficiency

import logging
from pathlib import Path
import time

# database for storing results
import sqlite3

# image processing
import cv2
import numpy as np
import skimage

#storing results
import pandas as pd

#warning
import tkinter as tk
import sys

#multiprocessing & multithreading
import multiprocessing as mp
import threading

#logger = logging.getLogger(__name__)


class ImageLooper:
    def __init__(self, config):
        self.images = list(Path(config["images"]["path"]).rglob("*.tif"))

        self.file_background = Path(config["images"]["file_background"])
        self.debug = config["debugging"]["debug"]
        self.config = config

        self.db_file = Path(
            config["output"]["path"],
            f'{config["config"]["run_name"]}{config["output"]["file_db_append"]}',
        )

        #saving run name
        self.run_name = config["config"]["run_name"]

        #crop the images
        self.crop = True

        # create database
        self.create_db(self.db_file)

        # load calibration image
        self.img_cal = self.load_image_gray(
            Path(config["images"]["file_calibration"]), crop=True
        )

        # TODO: use calibration image to calculate pixel to mm ratio
        # need to decide if this is needed, lighttable camera shouldn't change position too much between experiments, can measure manually before running
        # in alex's experiments dots are 45 pixels apart

        self.csv_file = (
            f'{config["config"]["run_name"]}{config["output"]["file_csv_append"]}'
        )

        # setting the pixel value threshold for particles to be detected
        self.bin_threshold = config["cost_parameters"]["binary_threshold"]

    def show_warning_popup(self):
        #Warns the user that if they continue they will overwrite the existing sqlite database

        #create temporary pop-up window
        popup = tk.Toplevel()
        popup.title("Warning")

        #button to continue operation
        def continue_button_click():
            popup.quit()
            popup.destroy()
            

        #button to stop operation
        def stop_button_click():
            print("Operation Cancelled")
            sys.exit()

        #description of the warning
        label = tk.Label(popup, anchor = "center", wraplength= 400, 
                         text="If you continue you will overwrite the existing SQlite database and lose any stored data. \n Do you still wish to continue?")
        label.grid(row =0, column = 0, columnspan=2, pady=10, sticky='nsew')

        #creaing a frame to hold the buttons
        button_frame = tk.Frame(popup)
        button_frame.grid(row=1, column=0, columnspan=2, pady=10, sticky='nsew')

        #creating a button to close the warning
        continue_button = tk.Button(button_frame, text="Erase Existing SQlite Database", command=continue_button_click)
        continue_button.pack(side=tk.RIGHT, padx=10)

        #creating a button to stop the code
        stop_button = tk.Button(button_frame, text="Cancel", command=stop_button_click)
        stop_button.pack(side=tk.LEFT, padx=10)

        #configuring grid
        popup.grid_rowconfigure(0, weight=1)
        popup.grid_rowconfigure(1, weight=1)
        popup.grid_columnconfigure(0, weight=1)
        popup.grid_columnconfigure(1, weight=1)

        # Center the popup window
        popup.geometry("500x150+500+300")

        # Make the pop-up modal (must interact with it before returning to main code)
        popup.grab_set()

        # Run the pop-up window's event loop
        popup.mainloop()


    def create_db(self, db_file):
        
        #check if tables already exist in the sqlite dabase before 
        def table_exists(db, table_name):
            cursor = db.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master WHERE type='table' AND name=?;
                 """, (table_name,))
            return cursor.fetchone() is not None

        db = sqlite3.connect(db_file)
    
        #if a table exists show user a warning before deleting existing data
        if table_exists(db, "images"):
            self.show_warning_popup()

        # clear database
        db.execute("DROP TABLE IF EXISTS particles")
        db.execute("DROP TABLE IF EXISTS images")
        db.execute("DROP TABLE IF EXISTS no_filter")
        
        # create table to append particle recognitions
        db.execute(
            "CREATE TABLE particles (id INTEGER PRIMARY KEY, image TEXT, time REAL, x REAL, y REAL, width REAL, length REAL, area REAL)"
        )
        # create table to append per image data
        db.execute(
            "CREATE TABLE images (id INTEGER PRIMARY KEY, image TEXT, time REAL, particles INTEGER)"
        )
        #create table to append no_filter particle properties
        db.execute(
            "CREATE TABLE no_filter (id INTEGER PRIMARY KEY, x_init REAL, y_init REAL, area REAL, a_axis REAL, b_axis REAL, x_final REAL, y_final REAL, first_frame REAL, last_frame REAL)"
        )

        # close database
        db.commit()
        db.close()

    def load_image_gray(self, path, crop=False):
        # load image and convert to grayscale
        img = cv2.imread(path.as_posix())
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img = self.noise_filter(img)
        img = self.sharpen_image(img)

        # crop image to background-image area
        if crop:
            crop_left = int(self.config["images"]["crop_left"])
            crop_right = int(self.config["images"]["crop_right"])
            crop_top = int(self.config["images"]["crop_top"])
            crop_bottom = int(self.config["images"]["crop_bottom"])
            img = img[
                crop_top : img.shape[0] - crop_bottom,
                crop_left : img.shape[1] - crop_right,
            ]

        return img

    def noise_filter(self, img, pixels=3):
        # filter out noise
        img = cv2.GaussianBlur(img, (pixels, pixels), 0)
        img = cv2.medianBlur(img, pixels)
        return img

    def sharpen_image(self, img):
        kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
        img = cv2.filter2D(img, -1, kernel)
        return img

    # threshold image to isolate particles
    def threshold_image(self, img_before):
        # threshold image to isolate particles
        img = cv2.threshold(img_before, self.bin_threshold, 255, cv2.THRESH_BINARY_INV)[
            1
        ]
        # TODO: make threshold value configurable
        img = cv2.morphologyEx(img, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        # TODO: make threshold value configurable
        img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))

        return img

    def write_to_sqlite(self, db, img_data, no_filter_data):

        # add image data to sqlite database
        db.execute(
            "INSERT INTO images (image, time, particles) VALUES (?, ?, ?)",
            (img_data[0][0], img_data[0][1], len(img_data)),
        )

        #add particle data to sqlite database
        db.executemany(
            '''
            INSERT INTO particles (image, time, x, y, width, length, area) VALUES
            (?, ?, ?, ?, ?, ?, ?)
            ''',
            img_data,
        )

        #add no_filter data to sqlite database
        db.executemany(
            '''
            INSERT INTO no_filter (x_init, y_init, area, a_axis, b_axis, x_final, y_final, first_frame, last_frame) VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            no_filter_data,
        )

    def analyze_image(self, image_path, img_bg, pixel_length):
        particles = []

        # load image
        img = self.load_image_gray(image_path, crop=self.crop)

        # subtract background
        img = cv2.subtract(img_bg, img)

        # stretch greyscale between 0 and 255
        img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)

        # threshold image to isolate particles
        img = self.threshold_image(img)

        # moving the greyscale inversion to end because it was resulting in the whole image being white when testing
        img = cv2.bitwise_not(img)

        # find consecutive areas of white pixels
        particles = skimage.measure.label(img, background=0)
        particles = skimage.measure.regionprops(particles)

        #storing the particle information in a list
        particle_data = []
        for particle in particles:
            data = (image_path.as_posix(),
                    image_path.stem, 
                    particle.centroid[1], 
                    particle.centroid[0],
                    particle.axis_minor_length * pixel_length,
                    particle.axis_major_length * pixel_length,
                    particle.area * (pixel_length**2))
            particle_data.append(data)
        
        return img, particle_data

    # TODO finish this work
    def calc_pixel_size(self, img_cal):

        # invert grayscale and stretch greyscale between 0 and 255
        img_cal = cv2.bitwise_not(img_cal)
        img_cal = cv2.normalize(img_cal, None, 0, 255, cv2.NORM_MINMAX)

        # find consecutive areas of white pixels
        dots = skimage.measure.label(img_cal, background=0)
        dots = skimage.measure.regionprops(dots)

        df_cal = pd.DataFrame(
            [{"x": dot.centroid[1], "y": dot.centroid[0]} for dot in dots]
        )

        return None

    def chunk(self, images, numImagesPerProc):
        '''
        Break image paths into seperate chunks that can be served to each processor
        '''
        for i in range(0, len(images), numImagesPerProc):
            yield images[i : i + numImagesPerProc]

    def listener_thread(self, q):
        '''
        Create a thread that listens to the queue and when a record appears
        an INSERT command is created from the image data passed in the record
        and info is logged on the progress and speed of processing
        '''
        db = sqlite3.connect(self.db_file)
        # data is commited to the database once all images have been analyzed
        # disabling journal mode for performance gain
        db.executescript(
            '''
            PRAGMA synchronous = OFF;
            PRAGMA journal_mode = OFF;
            '''
        )
        frame_count = 0 
        frame_count_total = 0
        tic = time.perf_counter()
        while True:
            img_data = q.get()
            if img_data is None:
                break
            if len(img_data) > 0:
                no_filter_data = []
                for item in img_data:
                    no_filter_data.append((item[2], item[3], item[6], item[5], item[4], item [2], item[3], item[1], item[1]))
                self.write_to_sqlite(db, img_data, no_filter_data)
            frame_count += 1
            frame_count_total += 1
            toc = time.perf_counter()
            fps = frame_count / (toc - tic)
            #log every 120th frame that is processed
            logger = logging.getLogger(__name__)
            if frame_count_total % 60 == 0:
                logger.info(
                    f"{self.run_name}, "
                    f"fps: {fps:.2f}, "
                    f"total frames: {frame_count_total}/{len(self.images)}, "
                    f"time left: {((len(self.images) - frame_count_total) / fps) / 60:.2f} min"
                )
                tic = time.perf_counter()
                frame_count = 0

        db.commit()
        db.close()


    def worker_process(self, queue, payload, img_bg, pixel_length):
        '''
        Pass a chunk of image paths to each processor to be analyzed
        '''
        for image_path in payload['image_paths']:
            particle_data = self.analyze_image(image_path, img_bg, pixel_length)[1]
            queue.put(particle_data)

        print(f"processor {payload['id']} done!")


    def run(self, payloads):
        # TODO: write code to obtain pixel to mm size
        pixel_length = self.calc_pixel_size(self.img_cal)

        pixel_length = 20 / 55

        frame_count = 0

        images = sorted(self.images)

        # load background image
        img_bg = self.load_image_gray(self.file_background, crop=self.crop)

        # img_time_start = float(images[0].stem)
        # img_time_before = img_time_start
        img_prev = None
        # df_part_prev = None

        # loop through images
        for image_path in images:
            # img_time = float(image_path.stem)
            img = self.analyze_image(image_path, img_bg, pixel_length)[0]

            frame_count += 1

            # displays overlay of particle if "debug" is True, else not needed
            if self.debug:

                if img_prev is not None:
                    
                    #using the original image and the thresholded particles
                    original_image = self.load_image_gray(image_path, crop=True)
                    thresholded_image = img.copy()

                    #convert the original image to color
                    original_image = cv2.cvtColor(original_image, cv2.COLOR_GRAY2BGR)

                    #convert the thresholded particles to red
                    thresholded_image = cv2.cvtColor(thresholded_image, cv2.COLOR_GRAY2BGR)
                    kernel = np.ones((5,5),np.uint8)
                    thresholded_image = cv2.morphologyEx(thresholded_image, cv2.MORPH_CLOSE, kernel)
                    thresholded_image[:, :, 0:2] = 0

                    #create overlay image to see how the particle sizes are detected
                    overlay_image = cv2.addWeighted(thresholded_image, 0.5, original_image, 1-0.5, 0)

                    # display the image
                    # cv2.imshow("thresholded_image", thresholded_image)
                    # cv2.imshow("original_image", original_image)
                    cv2.imshow("particle_overlay", overlay_image)

                    key = cv2.waitKey(1000)
                    cv2.waitKey(0)

                    # input("Press Enter to see next image")

                if (frame_count) > int(self.config["debugging"]["images_to_view"]):
                    cv2.destroyAllWindows()
                    cv2.waitKey(1)
                    self.debug = False
                    break

                img_prev = img
            
            #breaks the loop if there is no debugging to improve efficiency
            else:
                break

        #creating multiprocessing queue for communication between processes and listener
        queue = mp.Queue()

        #creating listener thread to listen for messages form the queue 
        lp = threading.Thread(target=self.listener_thread, args = (queue,))
        lp.start()

        #empty list to store worker processes
        workers = []
        
        #loop through the payloads and creater a worker process for each payload
        for payload in payloads:
            try:
                worker = mp.Process(
                    target=self.worker_process,
                    args=(queue, payload, img_bg, pixel_length))
                workers.append(worker)
                worker.start()
            except Exception as e:
                print(f"failed to start worker for payload {payload}: {e}")

        #wait for the worker processes to finish
        for w in workers:
            w.join()

        #stop the listener thread
        queue.put_nowait(None)

        #wait for the listener thread to finish
        lp.join()

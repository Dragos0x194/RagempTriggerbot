import tkinter as tk
from tkinter import ttk
import threading
import time
import logging
import sys
import winsound  # For beep sound on Windows
import pyautogui
import cv2
import numpy as np
from pynput import keyboard, mouse
import win32api
import win32con

# ===================== LOGGING CONFIGURATION =====================
logging.basicConfig(
    filename='monitor_pixel.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ===================== GENERAL CONFIG ============================
SCREEN_WIDTH, SCREEN_HEIGHT = pyautogui.size()
x, y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2  # Pixel in the center of the screen

# 1) INITIAL COLOR (e.g., normal reticle)
INITIAL_COLOR_RGB = (224, 224, 224)

# Convert to HSV (OpenCV uses BGR)
def rgb_to_hsv(rgb_color):
    color_bgr = np.uint8([[rgb_color[::-1]]])  
    color_hsv = cv2.cvtColor(color_bgr, cv2.COLOR_BGR2HSV)[0][0]
    return tuple(int(v) for v in color_hsv)

INITIAL_COLOR_HSV = rgb_to_hsv(INITIAL_COLOR_RGB)

# Tolerances for detecting the initial color
TOLERANCE_H = 10
TOLERANCE_S = 10
TOLERANCE_V = 10

CHECK_INTERVAL = 0.1   # Time interval between checks (seconds)
SHOOT_INTERVAL = 0.1   # Time interval between shots (seconds)

# Global flags
clicking_enabled = False
stop_script = False
right_button_pressed = False

# Lock for global variables (thread-safe)
lock = threading.Lock()

# ================== KEYBOARD / MOUSE LISTENERS ==================
def on_press(key):
    """
    Keyboard listener: toggling with Insert + beep.
    """
    global clicking_enabled
    try:
        if key == keyboard.Key.insert:
            with lock:
                clicking_enabled = not clicking_enabled
                state = "Enabled" if clicking_enabled else "Disabled"
                logging.info(f"[Keyboard] 'Insert' => {state}")
                print(f"[Keyboard] 'Insert' => {state}")

                # Beep for ON/OFF
                if clicking_enabled:
                    # Beep ON
                    winsound.Beep(1000, 150) 
                else:
                    # Beep OFF
                    winsound.Beep(500, 150)
    except AttributeError:
        pass

def on_click(x_click, y_click, button, pressed):
    """
    Mouse listener: used if we only want to shoot
    when the right mouse button is pressed (optional).
    """
    global right_button_pressed
    if button == mouse.Button.right:
        with lock:
            right_button_pressed = pressed
            st = "pressed" if pressed else "released"
            logging.info(f"[Mouse] Right button {st}")
            print(f"[Mouse] Right button {st}")

def start_keyboard_listener():
    """
    Dedicated thread for keyboard listening.
    """
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

def start_mouse_listener():
    """
    Dedicated thread for mouse listening.
    """
    with mouse.Listener(on_click=on_click) as listener:
        listener.join()

# =============== PIXEL COLOR DETECTION FUNCTIONS ===============
def get_pixel_color_hsv(px, py):
    try:
        color_rgb = pyautogui.pixel(px, py)
        bgr = np.uint8([[color_rgb[::-1]]])
        color_hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)[0][0]
        return tuple(int(v) for v in color_hsv)
    except Exception as e:
        logging.error(f"get_pixel_color_hsv({px}, {py}) - Error: {e}")
        return None

def is_color_initial(color_hsv):
    """
    Checks if the pixel still has the initial color.
    """
    if color_hsv is None:
        return False
    c_h, c_s, c_v = color_hsv
    i_h, i_s, i_v = INITIAL_COLOR_HSV

    # Hue difference (HSV has 0..179 for H)
    hue_diff = abs(c_h - i_h)
    hue_diff = min(hue_diff, 180 - hue_diff)

    sat_diff = abs(c_s - i_s)
    val_diff = abs(c_v - i_v)

    # Return True if all differences are within tolerance
    if (hue_diff <= TOLERANCE_H and
        sat_diff <= TOLERANCE_S and
        val_diff <= TOLERANCE_V):
        return True
    return False

# ====================== SHOOT FUNCTION ==========================
def shoot():
    """
    Executes a shot (left-click).
    """
    try:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.01)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
        logging.debug("[Shoot] Shot fired (left-click).")
    except Exception as e:
        logging.error(f"[Shoot] Error: {e}")

# ========================== MAIN LOOP ===========================
def main_loop():
    """
    Monitors the pixel color and fires if changed,
    runs in a separate thread.
    """
    global stop_script

    logging.info("=== Script Start ===")
    print("=== Script: Reticle Color Change Detection ===")
    print("- 'Insert' => Enable/Disable script (beep).")
    print("- Right mouse button => (optional) only shoot while pressed.")
    print("- Close the GUI window => Completely stop the script.\n")

    # Start listeners
    kb = threading.Thread(target=start_keyboard_listener, daemon=True)
    ms = threading.Thread(target=start_mouse_listener, daemon=True)
    kb.start()
    ms.start()

    try:
        while not stop_script:
            with lock:
                local_on = clicking_enabled
                local_rp = right_button_pressed

            if local_on:
                if local_rp:
                    current_hsv = get_pixel_color_hsv(x, y)
                    if current_hsv is None:
                        time.sleep(CHECK_INTERVAL)
                        continue

                    # If the pixel NO longer has the initial color => shoot
                    if not is_color_initial(current_hsv):
                        shoot()
                        time.sleep(SHOOT_INTERVAL)
                    else:
                        logging.debug("[Info] Still initial color, no shot.")
                else:
                    logging.debug("[Info] Right button not pressed, no shot.")
            else:
                logging.debug("[Info] Script disabled (Insert=Off).")

            time.sleep(CHECK_INTERVAL)

    except KeyboardInterrupt:
        logging.info("Script stopped with Ctrl+C.")
        print("\nScript stopped with Ctrl+C.")
        stop_script = True
    except Exception as e:
        logging.error(f"[Error] Exception: {e}")
        print(f"[Error] Exception: {e}")
        stop_script = True
    finally:
        logging.info("=== Script End ===")
        print("=== Script closed. ===")

# ========================== GUI CLASS ===========================
class PixelHunter:
    def __init__(self, root):
        """
        Constructor for the graphical interface.
        """
        self.root = root
        self.root.title("PixelHunter")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)  # When user closes the window

        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Info label
        self.label_info = ttk.Label(
            main_frame, 
            text=(
                "Script for detecting a change in the pixel color (reticle).\n"
                "- Press 'Insert' => Enable/Disable .\n"
                "- Hold the right mouse button to shoot.\n"
                "- Close this window to completely stop the script."
            ),
            justify="left"
        )
        self.label_info.grid(row=0, column=0, columnspan=2, pady=(0, 10))

        # Status label (Enabled / Disabled)
        self.label_status = ttk.Label(main_frame, text="Status: Disabled", font=("Arial", 12, "bold"))
        self.label_status.grid(row=1, column=0, columnspan=2, pady=(5, 5))

        # Quit button
        self.btn_quit = ttk.Button(main_frame, text="Quit", command=self.on_closing)
        self.btn_quit.grid(row=2, column=0, columnspan=2, pady=(10, 0), sticky="ew")

        # The thread in which the main loop will run
        self.script_thread = None

        # Automatically start the script
        self.start_script()

        # Periodically update the status label
        self.update_status()

    def start_script(self):
        """
        Creates and starts the main monitoring thread.
        """
        global stop_script
        if self.script_thread is None or not self.script_thread.is_alive():
            stop_script = False
            self.script_thread = threading.Thread(target=main_loop, daemon=True)
            self.script_thread.start()
            logging.info("Thread 'main_loop' started.")

    def update_status(self):
        """
        Updates the status label based on clicking_enabled.
        """
        with lock:
            local_on = clicking_enabled

        if local_on:
            self.label_status.config(text="Status: Enabled")
        else:
            self.label_status.config(text="Status: Disabled")

        # If the script is not stopped, call update_status again in ~0.5s
        if not stop_script:
            self.root.after(500, self.update_status)

    def on_closing(self):
        """
        Event handler for closing the GUI window.
        Ensures threads stop properly, then destroys the window.
        """
        self.stop_script()
        self.root.destroy()

    def stop_script(self):
        """
        Stops the main monitoring loop by setting stop_script = True.
        """
        global stop_script
        stop_script = True
        logging.info("stop_script = True set from the GUI.")

def main():
    """
    Entry point of the application - creates the Tk window and the PixelHunter GUI.
    """
    root = tk.Tk()
    PixelHunter(root)
    root.mainloop()

if __name__ == "__main__":
    main()

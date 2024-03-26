import json
import matplotlib.pyplot as plt
import numpy as np
import tkinter as tk
from tkinter import filedialog

root = tk.Tk()
root.withdraw()  # Hide the main window

while True:
    file_path = filedialog.askopenfilename(
        title="Select experiment data, cancel to exit",
        filetypes=(("JSON files", "*.json"), ("All files", "*.*"))
    )

    if not file_path:
        print("No filepath returned, exiting.")
        exit()
    
    print(f"Opening file: {file_path}")

    with open(file_path, 'r') as json_file:
        experiment_data = json.load(json_file)

    column_densities_median = experiment_data["column_densities_median"]
    column_densities_mean = experiment_data["column_densities_mean"]


    fig, (ax2) = plt.subplots(1, 1, )
    fig.set_dpi(300)
    fig.set_size_inches(8.5/2.54, 4.6/2.54)

    # im1 = ax1.imshow(column_densities_mean, cmap='viridis', extent=[0, 480, 0, 320] )
    # ax1.set_title('mean')
    # colorbar = fig.colorbar(im1)
    # colorbar.set_label("Column Density [ppm*m]")

    im2 = ax2.imshow(column_densities_median, cmap='viridis', extent=[0, 480, 0, 320], vmin = 0, vmax = 800 )
    #ax2.set_title('median')
    ax2.set_title("Column Density (ppm$\cdot$m)", fontsize=10)
    colorbar = fig.colorbar(im2)
    #colorbar.set_label("Column Density (ppm*m)")
    #colorbar.ax.tick_params(labelsize=8)
    
    plt.savefig("plot.png",dpi=600)
    #plt.show()

    
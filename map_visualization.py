import folium
from folium.features import DivIcon
import webbrowser
import string
from pathlib import Path
import pandas as pd
from disney_lp import format_model_data, instantiate_model, run_model
from selenium import webdriver
import time
from PIL import Image
import numpy as np
import pprint

def build_polyline_lat_lon(disney_summary, locations):
	sequence = []
	for ride in disney_summary.path:
		sequence.append([
			locations.loc[locations.ride==ride, "latitude"].item(),
			locations.loc[locations.ride==ride, "longitude"].item()
			])
	return sequence


def build_map(disney_summary, locations, map_path):
	map_center = locations.loc[:, ['latitude', 'longitude']].mean().tolist()
	m = folium.Map(location=map_center, zoom_start=17)
	polyline_locs = build_polyline_lat_lon(disney_summary, locations)
	folium.PolyLine(
	    locations=polyline_locs,
	    color="red",
	    weight=5,
	).add_to(m)
	for i in range(len(locations)): 
		folium.Marker([locations.latitude[i], locations.longitude[i]], icon=DivIcon(
		        icon_size=(150,36),
		        icon_anchor=(7,20),
		        html=f'<div style="font-size: 18pt; color : black">{locations.label[i]}</div>',
		        )).add_to(m)
	# map_path = "./images/test_map.html"
	m.save(map_path)


def screenshot(folium_map_path, screenshot_path, driver):
	try:
	    file_url = Path(folium_map_path).resolve().as_uri()
	    driver.get(file_url)
	    driver.maximize_window()
	    time.sleep(2)
	    driver.save_screenshot(screenshot_path)
	    print("Screenshot saved successfully!")
	finally:
	    driver.quit()


def crop_and_concatenate(paths4, save):
	h,w = 1300, 1560
	skip_cols, skip_rows = 1366,455
	imgs = []
	for path in paths4:
		img = Image.open(path)
		img_array = np.asarray(img)
		img_array = img_array[skip_rows:skip_rows + h, skip_cols:skip_cols+w]
		imgs.append(img_array)
	big = np.concatenate([np.concatenate(imgs[:2], axis=1), np.concatenate(imgs[2:], axis=1)], axis=0)
	bigImg = Image.fromarray(big)
	bigImg.save(save)


def cycle_stats(cycle, data, locations, MAX_DISNEY_TIME):
	proposed_path = list(cycle)
	utility_proposed = sum((data.utilities[(locations.ride[locations.label == proposed_path[i]].item(),
		locations.ride[locations.label == proposed_path[i+1]].item())]) for i in range(len(proposed_path) - 1))
	wait_proposed = sum((data.wait_times[(locations.ride[locations.label == proposed_path[i]].item(),
		locations.ride[locations.label == proposed_path[i+1]].item())]) for i in range(len(proposed_path) - 1))
	transit_proposed = sum((data.transit_times[(locations.ride[locations.label == proposed_path[i]].item(),
		locations.ride[locations.label == proposed_path[i+1]].item())]) for i in range(len(proposed_path) - 1))
	obj_proposed = utility_proposed - transit_proposed / (2 * MAX_DISNEY_TIME)
	ride_time = sum((data.ride_lengths[(locations.ride[locations.label == proposed_path[i]].item(),
		locations.ride[locations.label == proposed_path[i+1]].item())]) for i in range(len(proposed_path) - 1))
	return {"utility":utility_proposed, 
			"wait_time":wait_proposed, 
			"transit_time":transit_proposed,
			"ride_time": ride_time,
			'objective':obj_proposed}



if __name__ == "__main__":

	# Load data & convert to pyomo friendly formatting
	df = pd.read_csv("./data/lp_data.csv", index_col=0)
	df.loc[df.index != "Entrance", "utility"] = (df.loc[df.index != "Entrance", "utility"] - 3.1) * 12/8.9
	walk_times = pd.read_csv("./data/walk_times.csv")
	locations = pd.read_csv("./data/ride_locations.csv")
	locations.loc[:, "label"] = list(string.ascii_uppercase)[:len(locations)]
	data = format_model_data(df, walk_times)


	disney_times = [300,360,420,480]
	paths4 = []
	for MAX_DISNEY_TIME in disney_times:
		model = instantiate_model(df, data, max_disney_time=MAX_DISNEY_TIME)
		disney_summary = run_model(model, data, df, max_disney_time=MAX_DISNEY_TIME)

		# Save Folium map 
		folium_map_path = "./images/tmp_map.html"
		m = build_map(disney_summary, locations, map_path = folium_map_path)
		# webbrowser.open(Path(folium_map_path).resolve().as_uri())

		# Screenshot Map 
		# screenshot_path = f"./images/dca_time_{MAX_DISNEY_TIME}.png"
		screenshot_path = f"./images/dca_time_{MAX_DISNEY_TIME}_revised.png"
		paths4.append(screenshot_path)
		screenshot(folium_map_path=folium_map_path, 
			screenshot_path=screenshot_path,
			driver=webdriver.Safari())


	Path(folium_map_path).unlink(missing_ok=True)
	# crop_and_concatenate(paths4, "./images/big.png")
	crop_and_concatenate(paths4, "./images/big_revised.png")


	pprint.pprint(cycle_stats("UOBAKGLSPMQJNDTU", data, locations, 420)) #lower left: not self intersecting
	pprint.pprint(cycle_stats("UODNJQMPSLGKABTU", data, locations, 420)) #lower left: optimal



	print(locations.loc[:, ['ride', 'label']].to_markdown(index=False))
	print(walk_times.sample(n=5).to_markdown(index=False))
	print(df.sample(n=5).to_markdown(index=True))








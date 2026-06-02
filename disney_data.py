"""
Disney California Adventure Wait Times Dataset from 
https://www.kaggle.com/datasets/tivory27/disney-california-adventure-wait-times?resource=download

Walk times from google maps
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import matplotlib.dates as mdates
import calendar
from itertools import combinations

def load_data():
	"""
	DCA dataset has all single rider wait times set at 0 minutes unfortunately. 
	"""
	df = pd.read_csv("./data/dca_wait_times.csv")
	df['Local Time'] = pd.to_datetime(df['Local Time'], format = "%Y-%m-%d %H:%M:%S.%f%z", utc=True)
	df['Local Time'] = df['Local Time'].dt.tz_convert('US/Pacific')
	df['Ride'] = ["Soarin' Around the World" if 'Soarin' in x else x for x in df['Ride'] ]
	ratings = pd.read_csv("./data/ratings.tsv", sep = "\t")
	ratings.loc[len(ratings)] = ["Entrance", "no", 0,0,0,0]
	fltr = df.Ride.isin(ratings.Ride)
	walk_times = pd.read_csv('./data/walk_times.csv')
	entrance = [] # time from entrance to {ride} is set to be 1 + time(Red Car Trolley -> {ride}) because red car trolley is right by the entrance. 
	for i in range(len(walk_times)):
		if walk_times.loc[i, "to"] == "Red Car Trolley":
			dct = {"from":"Entrance", "to":walk_times.loc[i, "from"], "time":walk_times.loc[i, "time"] + 1}
			entrance.append(dct)
		elif walk_times.loc[i, "from"] == "Red Car Trolley":
			dct = {"from":"Entrance", "to":walk_times.loc[i, "to"], "time":walk_times.loc[i, "time"] + 1}
			entrance.append(dct)
	entrance.append({"from":"Entrance", "to":"Red Car Trolley", "time": 1})
	entrance_df = pd.DataFrame(entrance)
	walk_times2 = pd.concat([walk_times, entrance_df])
	return df.loc[fltr, :].reset_index(drop=True), ratings, walk_times2


def get_mean_wait_time_by_ride_and_month(df):
	mwt = df.groupby(by=["Ride",df['Local Time'].dt.month_name()])["Wait Time"].mean().unstack()
	mwt = mwt.loc[:, [calendar.month_name[i] for i in range(1,13)]].fillna(0)
	order = mwt.mean(axis=1).argsort()[::-1]
	return mwt.iloc[order, :]


def define_lin_prog_dataset(mwt, ratings, ride_length=5):
	row = pd.DataFrame({calendar.month_name[i]:0. for i in range(1,13)}, index = ["Entrance"])
	mwt = pd.concat([mwt, row])
	standby = mwt.max(axis=1)
	ratings.index = ratings.Ride
	utility = ratings.Total
	rl = pd.Series([0 if ride == "Entrance" else 5 for ride in utility.index], index=utility.index)
	data = pd.concat([utility, standby, rl], axis=1)
	data.columns = ['utility', 'wait', 'ride_length']
	return data


if __name__ == "__main__":
	df, ratings, walk_times = load_data()
	mwt = get_mean_wait_time_by_ride_and_month(df)
	data = define_lin_prog_dataset(mwt, ratings)
	# data.to_csv("./data/lp_data.csv")



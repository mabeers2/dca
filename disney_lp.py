import numpy as np
import pandas as pd
import pyomo.environ as pyo
from dataclasses import dataclass


@dataclass
class ModelData:
	S: set[tuple[str, str]]
	utilities: dict[[str, str], float]
	transit_times: dict[[str, str], float]
	wait_times: dict[[str, str], float]
	ride_lengths: dict[[str, str], float]


def format_model_data(df, walk_times):
	S = {(i,j) for i,j in walk_times.loc[:, ["from", "to"]].to_numpy()}
	S.update({(j,i) for i,j in walk_times.loc[:, ["from", "to"]].to_numpy()})
	utilities = dict()
	transit_times = dict()
	wait_times = dict()
	ride_lengths = dict()
	for i,j in S:
		u1 = df.utility[df.index==i].item()
		u2 = df.utility[df.index==j].item()
		utilities[(i,j)] = (u1 + u2) / 2
		w1 = df.wait[df.index==i].item()
		w2 = df.wait[df.index==j].item()
		wait_times[(i,j)] = (w1 + w2) / 2		
		r1 = df.ride_length[df.index==i].item()
		r2 = df.ride_length[df.index==j].item()
		ride_lengths[(i,j)] = (r1 + r2) / 2		
		f1 = (walk_times['from'] == i) & (walk_times['to'] == j)
		f2 = (walk_times['from'] == j) & (walk_times['to'] == i)
		if np.sum(f1) > np.sum(f2):
			transit_times[(i,j)] = walk_times.time[f1].item()
		else:
			transit_times[(i,j)] = walk_times.time[f2].item()
	return ModelData(S, utilities, transit_times, wait_times, ride_lengths)




def instantiate_model(df: pd.DataFrame, data: ModelData, max_disney_time: float):
	model = pyo.ConcreteModel()
	model.M = len(df)
	model.max_disney_time = max_disney_time
	model.rides = pyo.Set(dimen = 1, initialize=df.index.tolist())
	model.edges = pyo.Set(dimen = 2, initialize=data.S)
	model.utility = pyo.Param(model.edges, initialize=data.utilities)
	model.walk_times = pyo.Param(model.edges, initialize=data.transit_times)
	model.wait_times = pyo.Param(model.edges, initialize=data.wait_times)
	model.ride_lengths = pyo.Param(model.edges, initialize=data.ride_lengths)
	model.y = pyo.Var(model.edges, domain = pyo.Binary)
	model.u = pyo.Var(model.rides, domain=pyo.NonNegativeIntegers, bounds=(1,len(df)))
	# model.u = pyo.Var(model.rides, domain=pyo.PositiveIntegers)

	@model.Objective(sense=pyo.maximize) 
	def objective_rule(model):
		return sum((model.utility[e] - model.walk_times[e] / (2 * model.max_disney_time) ) * model.y[e] for e in model.edges)


	@model.Constraint()
	def max_tour_time_constraint(model):
		return sum((model.walk_times[e] + model.wait_times[e] + model.ride_lengths[e]) * model.y[e] for e in model.edges) <= model.max_disney_time


	@model.Constraint()
	def leave_entrance_rule(model):
		return sum(model.y["Entrance", ride] for ride in model.rides if ride != "Entrance") == 1


	@model.Constraint()
	def enter_entrance_rule(model):
		return sum(model.y[ride, "Entrance"] for ride in model.rides if ride != "Entrance") == 1


	@model.Constraint(model.rides)
	def enter_exit_rule(model, ride):
		return sum(model.y[ride, different_ride] for different_ride in model.rides if ride != different_ride) == sum(model.y[different_ride, ride] for different_ride in model.rides if ride != different_ride)


	@model.Constraint(model.rides)
	def exit_rule(model, ride):
		return sum(model.y[ride, different_ride] for different_ride in model.rides if ride != different_ride) <= 1

	@model.Constraint()
	def u1(model):
		return model.u["Entrance"] == 1

	@model.Constraint(model.rides, model.rides)
	def mtz_rule(model, r1, r2):
	    if r1 != r2  and r2 != "Entrance" : # and r1 != "Entrance"
	        return model.u[r1] - model.u[r2] + 1 <= (model.M-1) * (1 - model.y[r1, r2])
	    return pyo.Constraint.Skip


	return model



@dataclass
class ModelResult:
	path: list[str]
	utility: int | float
	max_time: int | float
	total_time: int | float
	wait_time: int | float
	ride_time: int | float
	transit_time: int | float
	obj: float


def summarize_results(model, data, max_disney_time):
	obj = pyo.value(model.objective_rule)
	total_time = pyo.value(model.max_tour_time_constraint)
	soln = [key for key, value in model.y.extract_values().items() if value > .5]
	time_on_rides = sum(data.ride_lengths[t] for t in soln)
	time_waiting = sum(data.wait_times[t] for t in soln)
	time_walking_between_rides = sum(data.transit_times[t] for t in soln)
	utility = sum(data.utilities[t] for t in soln)
	path = ["Entrance"]
	soln2 = soln.copy()
	while soln2:
		current_index = [e[0] for e in soln2].index(path[-1])
		path.append(soln2[current_index][1])
		soln2.remove(soln2[current_index])
	return ModelResult(
		path=path, 
		utility=utility, 
		max_time=max_disney_time, 
		total_time=total_time, 
		wait_time=time_waiting,
		ride_time=time_on_rides,
		transit_time=time_walking_between_rides,
		obj=obj)



def run_model(model, data, df, max_disney_time, disp = False):
	# Solve Linear Program, HiGHS works fine too 
	solver = pyo.SolverFactory('gurobi')
	solver.options['Symmetry'] = 2
	solver.options["MIPFocus"] = 2
	solver.options['Presolve'] = 2
	solver.options['PreSparsify'] = 1
	solver.options['NumericFocus'] = 3
	solver.options['MIPGap'] = 1e-8
	results = solver.solve(model, tee=disp, warmstart=False)

	# Extract Results from model
	disney_summary = summarize_results(model, data, max_disney_time)

	# Print Results
	print("\n\nPath\n-----------------------")
	print("\n".join(disney_summary.path))
	print("-----------------------")
	print(f"Utility = {	sum(df.utility[df.index == p].item() for p in disney_summary.path)}")
	print(f"total time = {pyo.value(model.max_tour_time_constraint):.02f}/{model.max_disney_time} minutes")
	print(f"f(x) = {disney_summary.obj}")
	return disney_summary


git remote add origin git@github.com:mabeers2/dca.git

if __name__ == "__main__":

	# Load data & convert to pyomo friendly formatting
	df = pd.read_csv("./data/lp_data.csv", index_col=0)
	walk_times = pd.read_csv("./data/walk_times.csv")
	data = format_model_data(df, walk_times)

	# Instantiate model
	MAX_DISNEY_TIME = 300#691 # Minutes
	model = instantiate_model(df, data, max_disney_time=MAX_DISNEY_TIME)

	# Run Model
	summary = run_model(model, data, df, max_disney_time=MAX_DISNEY_TIME)



